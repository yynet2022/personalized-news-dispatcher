from django.shortcuts import redirect, get_object_or_404
from django.views.generic import (
    ListView, CreateView, UpdateView, DeleteView, View)
from django.contrib.auth.mixins import LoginRequiredMixin
from django.urls import reverse_lazy
from django.contrib.auth.decorators import login_required
from django.views.decorators.http import require_POST
from django.contrib import messages
from django.http import JsonResponse
from django.db import IntegrityError
from django.conf import settings
from datetime import datetime
import logging

from .models import (
    QuerySet, UniversalKeywords, CurrentKeywords, RelatedKeywords,
    # ArXivKeywords
)
from .forms import QuerySetForm
from .services import (
    fetch_articles_for_subscription, send_articles_email
)
from subscriptions.fetchers import FeedFetchError
from core.services import log_sent_articles

logger = logging.getLogger(__name__)


class QuerySetListView(LoginRequiredMixin, ListView):
    model = QuerySet
    template_name = 'subscriptions/queryset_list.html'
    context_object_name = 'querysets'

    def get_queryset(self):
        return QuerySet.objects.filter(
            user=self.request.user).order_by('source', 'name')


class QuerySetCreateView(LoginRequiredMixin, CreateView):
    model = QuerySet
    form_class = QuerySetForm
    template_name = 'subscriptions/queryset_form.html'
    success_url = reverse_lazy('subscriptions:queryset_list')

    def form_valid(self, form):
        form.instance.user = self.request.user
        try:
            return super().form_valid(form)
        except IntegrityError:
            form.add_error('name', '同じ名前のQuerySetが既に存在します。')
            return self.form_invalid(form)


class QuerySetUpdateView(LoginRequiredMixin, UpdateView):
    model = QuerySet
    form_class = QuerySetForm
    template_name = 'subscriptions/queryset_form.html'
    success_url = reverse_lazy('subscriptions:queryset_list')

    def get_queryset(self):
        return QuerySet.objects.filter(user=self.request.user)

    def form_valid(self, form):
        try:
            return super().form_valid(form)
        except IntegrityError:
            form.add_error('name', '同じ名前のQuerySetが既に存在します。')
            return self.form_invalid(form)


class QuerySetDeleteView(LoginRequiredMixin, DeleteView):
    model = QuerySet
    template_name = 'subscriptions/queryset_confirm_delete.html'
    success_url = reverse_lazy('subscriptions:queryset_list')

    def get_queryset(self):
        return QuerySet.objects.filter(user=self.request.user)


@login_required
@require_POST
def send_manual_email(request, pk):
    """
    指定されたQuerySetに基づいてニュースダイジェストを手動で送信するビュー
    """
    queryset = get_object_or_404(QuerySet, pk=pk, user=request.user)

    try:
        _, new_articles = fetch_articles_for_subscription(
            queryset,
            request.user,
            dry_run=False,
            enable_translation=settings.TRANSLATION_AT_MANUAL_EMAIL)
    except FeedFetchError as e:
        s = f"ニュースの取得に失敗しました: {e}"
        logger.error(s)
        messages.error(request, s)
        return redirect('subscriptions:queryset_list')

    if new_articles:
        querysets_with_articles = [{
            'queryset': queryset,
            'queryset_name': queryset.name,
            'query_str': queryset.query_str,
            'articles': new_articles,
        }]

        try:
            subject = (
                f'[{queryset.get_source_display()}] '
                f'Manual Send - {queryset.name}')
            logger.debug(f'mail subject: {subject}')
            template_name = 'news/email/news_digest_email'
            send_articles_email(
                user=request.user,
                querysets_with_articles=querysets_with_articles,
                subject=subject,
                template_name=template_name,
                enable_translation=False  # 手動送信では翻訳しない
            )
            log_sent_articles(request.user, new_articles)
            messages.success(
                request,
                f'「{queryset.name}」のニュース（{len(new_articles)}件）を '
                f'{request.user.email} に送信しました。')

        except Exception as e:
            s = f'メールの送信中にエラーが発生しました: {e}'
            logger.error(s)
            messages.error(request, s)
    else:
        messages.info(
            request,
            f'「{queryset.name}」に関する新しい記事は見つかりませんでした。')

    return redirect('subscriptions:queryset_list')


class _KeywordsApiView(LoginRequiredMixin, View):
    _KeywordsModel = None

    def get(self, request, *args, **kwargs):
        large_category_id = request.GET.get('large_category_id')
        if not large_category_id:
            return JsonResponse({'error': 'large_category_id is required'},
                                status=400)

        keywords = self._KeywordsModel.objects.filter(
            large_category_id=large_category_id).order_by('name')
        data = list(keywords.values('id', 'name', 'description'))
        return JsonResponse(data, safe=False)


class UniversalKeywordsApiView(_KeywordsApiView):
    _KeywordsModel = UniversalKeywords


class CurrentKeywordsApiView(_KeywordsApiView):
    _KeywordsModel = CurrentKeywords


class RelatedKeywordsApiView(_KeywordsApiView):
    _KeywordsModel = RelatedKeywords


'''
class ArXivKeywordsApiView(LoginRequiredMixin, View):
    def get(self, request, *args, **kwargs):
        keywords = ArXivKeywords.objects.order_by('name')
        data = list(keywords.values('id', 'name', 'description'))
        return JsonResponse(data, safe=False)
'''


class NewsPreviewApiView(LoginRequiredMixin, View):
    def get(self, request, *args, **kwargs):
        query = request.GET.get('q')
        source = request.GET.get('source', QuerySet.SOURCE_GOOGLE_NEWS)

        if not query:
            return JsonResponse(
                {'error': 'Query parameter "q" is required'}, status=400)

        try:
            max_articles = int(request.GET.get('max_articles', 20))

            logger.debug(f'source={source}')
            if source == QuerySet.SOURCE_CINII:
                # --- CiNii Preview Logic ---
                after_days = int(request.GET.get('after_days', 180))
                logger.debug(f'after_days={after_days}')

                dummy_queryset = QuerySet(
                    query_str=query,
                    after_days=after_days,
                    max_articles=max_articles,
                    source=QuerySet.SOURCE_CINII
                )

            elif source == QuerySet.SOURCE_ARXIV:
                # --- arXiv Preview Logic ---
                after_days = int(request.GET.get('after_days', 30))
                logger.debug(f'after_days={after_days}')

                dummy_queryset = QuerySet(
                    query_str=query,
                    after_days=after_days,
                    max_articles=max_articles,
                    source=QuerySet.SOURCE_ARXIV
                )

            else:
                # --- Google News Preview Logic (Default) ---
                after_days = int(request.GET.get('after_days', 2))
                logger.debug(f'after_days={after_days}')
                country_code = request.GET.get('country', 'JP')

                dummy_queryset = QuerySet(
                    query_str=query,
                    country=country_code,
                    after_days=after_days,
                    max_articles=max_articles,
                    source=QuerySet.SOURCE_GOOGLE_NEWS
                )

            query_with_date, articles = fetch_articles_for_subscription(
                queryset=dummy_queryset,
                user=request.user,
                dry_run=True,
                enable_translation=settings.TRANSLATION_AT_PREVIEW
            )
            articles_data = [
                {'title': x.title, 'link': x.url, 'published': (
                    x.published_date.strftime('%Y-%m-%d %H:%M:%S')
                    if x.published_date else 'N/A')}
                for x in articles
            ]
            return JsonResponse({'query_str': query_with_date,
                                 'articles': articles_data}, safe=False)

        except (ValueError, TypeError):
            return JsonResponse({'error': 'Invalid parameter format'},
                                status=400)
        except (FeedFetchError, Exception) as e:
            return JsonResponse(
                {'error': f'Failed to fetch news feed: {e}'}, status=502)


class SendManualEmailApiView(LoginRequiredMixin, View):
    def post(self, request, *args, **kwargs):
        pk = self.kwargs.get('pk')
        queryset = get_object_or_404(QuerySet, pk=pk, user=request.user)

        try:
            _, new_articles = fetch_articles_for_subscription(
                queryset,
                request.user,
                dry_run=False,
                enable_translation=settings.TRANSLATION_AT_MANUAL_EMAIL)
        except FeedFetchError as e:
            tstr = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            s = f"{tstr}: ニュースの取得に失敗しました: {e}"
            logger.error(s)
            return JsonResponse({'status': 'error', 'message': s}, status=500)

        if new_articles:
            querysets_with_articles = [{
                'queryset': queryset,
                'queryset_name': queryset.name,
                'query_str': queryset.query_str,
                'articles': new_articles,
            }]

            try:
                subject = (
                    f'[{queryset.get_source_display()}] '
                    f'Manual Send - {queryset.name}')
                logger.debug(f'mail subject: {subject}')
                template_name = 'news/email/news_digest_email'
                send_articles_email(
                    user=request.user,
                    querysets_with_articles=querysets_with_articles,
                    subject=subject,
                    template_name=template_name,
                    enable_translation=False  # 手動送信では翻訳しない
                )
                log_sent_articles(request.user, new_articles)

                tstr = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                msg = (f'{tstr}: '
                       f'「{queryset.name}」の記事（{len(new_articles)}件）を '
                       f'{request.user.email} に送信しました。')
                return JsonResponse({'status': 'success', 'message': msg})

            except Exception as e:
                tstr = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                s = f'{tstr}: メールの送信中にエラーが発生しました: {e}'
                logger.error(s)
                return JsonResponse({'status': 'error', 'message': s},
                                    status=500)
        else:
            tstr = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            msg = (f'{tstr}: 「{queryset.name}」に関する'
                   '新しい記事は見つかりませんでした。')
            return JsonResponse({'status': 'info', 'message': msg})


class ToggleAutoSendView(LoginRequiredMixin, View):
    def post(self, request, *args, **kwargs):
        try:
            queryset = get_object_or_404(
                QuerySet, pk=self.kwargs['pk'], user=request.user)
            queryset.auto_send = not queryset.auto_send
            queryset.save(update_fields=['auto_send'])
            return JsonResponse({
                'status': 'success',
                'auto_send': queryset.auto_send
            })
        except QuerySet.DoesNotExist:
            return JsonResponse({'status': 'error', 'message': 'Not Found'},
                                status=404)
        except Exception as e:
            return JsonResponse({'status': 'error', 'message': str(e)},
                                status=500)
