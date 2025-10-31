from django.shortcuts import render, redirect, get_object_or_404
from django.views.generic import CreateView, UpdateView, DeleteView, View
from django.contrib.auth.mixins import LoginRequiredMixin
from django.urls import reverse_lazy
from django.contrib.auth.decorators import login_required
from django.views.decorators.http import require_POST
from django.contrib import messages

from .models import QuerySet, UniversalKeywords, CurrentKeywords, RelatedKeywords
from .forms import QuerySetForm
from django.http import JsonResponse
from django.db import IntegrityError

from .services import (
    fetch_articles_for_queryset, send_digest_email, log_sent_articles,
    fetch_articles_for_preview
)


class QuerySetListView(LoginRequiredMixin, View):
    def get(self, request, *args, **kwargs):
        querysets = QuerySet.objects.filter(user=request.user).order_by('name')
        context = {'querysets': querysets}
        return render(request, 'subscriptions/queryset_list.html', context)


def generate_query_str(form):
    parts = []

    # 大分類
    large_category = form.cleaned_data.get('large_category')
    if large_category:
        parts.append(large_category.name)

    # 普遍キーワード
    for keyword in form.cleaned_data.get('universal_keywords', []):
        parts.append(keyword.name)

    # 時事キーワード
    for keyword in form.cleaned_data.get('current_keywords', []):
        parts.append(keyword.name)

    # 関連キーワード
    for keyword in form.cleaned_data.get('related_keywords', []):
        parts.append(keyword.name)

    # OR追加キーワード
    additional_or_keywords = form.cleaned_data.get('additional_or_keywords', '')
    if additional_or_keywords:
        parts.extend(additional_or_keywords.split())

    or_part = " OR ".join(parts)
    if or_part:
        or_part = f"({or_part})"

    refinement_part = form.cleaned_data.get('refinement_keywords', '')
    if not refinement_part:
        return or_part

    if not or_part:
        return refinement_part
    
    return f"{or_part} {refinement_part}"


class QuerySetCreateView(LoginRequiredMixin, CreateView):
    model = QuerySet
    form_class = QuerySetForm
    template_name = 'subscriptions/queryset_form.html'
    success_url = reverse_lazy('subscriptions:queryset_list')

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs['user'] = self.request.user
        return kwargs

    def form_valid(self, form):
        queryset = form.save(commit=False)
        queryset.user = self.request.user
        queryset.query_str = generate_query_str(form)
        try:
            queryset.save()
            form.save_m2m()
        except IntegrityError:
            form.add_error('name', '同じ名前のQuerySetが既に存在します。')
            return self.form_invalid(form)
        return redirect(self.success_url)




class QuerySetUpdateView(LoginRequiredMixin, UpdateView):
    model = QuerySet
    form_class = QuerySetForm
    template_name = 'subscriptions/queryset_form.html'
    success_url = reverse_lazy('subscriptions:queryset_list')

    def get_queryset(self):
        return QuerySet.objects.filter(user=self.request.user)

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs['user'] = self.request.user
        return kwargs

    def form_valid(self, form):
        queryset = form.save(commit=False)
        queryset.query_str = generate_query_str(form)
        try:
            queryset.save()
            form.save_m2m()
        except IntegrityError:
            form.add_error('name', '同じ名前のQuerySetが既に存在します。')
            return self.form_invalid(form)
        return redirect(self.success_url)




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
    
    # querysetに設定された値で記事を取得
    new_articles = fetch_articles_for_queryset(queryset, request.user)

    if new_articles:
        querysets_with_articles = [{
            'queryset_name': queryset.name,
            'articles': new_articles,
        }]
        
        try:
            send_digest_email(request.user, querysets_with_articles)
            log_sent_articles(request.user, new_articles)
            messages.success(request, f'「{queryset.name}」のニュース（{len(new_articles)}件）を {request.user.email} に送信しました。')
        
        except Exception as e:
            messages.error(request, f'メールの送信中にエラーが発生しました: {e}')
            
    else:
        messages.info(request, f'「{queryset.name}」に関する新しい記事は見つかりませんでした。')

    return redirect('subscriptions:queryset_list')


class UniversalKeywordsApiView(LoginRequiredMixin, View):
    def get(self, request, *args, **kwargs):
        large_category_id = request.GET.get('large_category_id')
        if not large_category_id:
            return JsonResponse({'error': 'large_category_id is required'}, status=400)

        keywords = UniversalKeywords.objects.filter(large_category_id=large_category_id).order_by('name')
        data = list(keywords.values('id', 'name', 'description'))
        return JsonResponse(data, safe=False)


class CurrentKeywordsApiView(LoginRequiredMixin, View):
    def get(self, request, *args, **kwargs):
        large_category_id = request.GET.get('large_category_id')
        if not large_category_id:
            return JsonResponse({'error': 'large_category_id is required'}, status=400)

        keywords = CurrentKeywords.objects.filter(large_category_id=large_category_id).order_by('name')
        data = list(keywords.values('id', 'name', 'description'))
        return JsonResponse(data, safe=False)


class RelatedKeywordsApiView(LoginRequiredMixin, View):
    def get(self, request, *args, **kwargs):
        large_category_id = request.GET.get('large_category_id')
        if not large_category_id:
            return JsonResponse({'error': 'large_category_id is required'}, status=400)

        keywords = RelatedKeywords.objects.filter(large_category_id=large_category_id).order_by('name')
        data = list(keywords.values('id', 'name', 'description'))
        return JsonResponse(data, safe=False)


class NewsPreviewApiView(LoginRequiredMixin, View):
    def get(self, request, *args, **kwargs):
        query = request.GET.get('q')
        if not query:
            return JsonResponse({'error': 'Query parameter "q" is required'},
                                status=400)
        
        try:
            after_days = int(request.GET.get('after_days', 2))
            max_articles = int(request.GET.get('max_articles', 20))
        except (ValueError, TypeError):
            return JsonResponse({'error': 'Invalid after_days or max_articles'}, status=400)

        articles = fetch_articles_for_preview(
            query_str=query,
            after_days=after_days,
            max_articles=max_articles
        )

        # 未保存のArticleオブジェクトを辞書に変換
        articles_data = [
            {
                'title': article.title,
                'link': article.url,
                'published': article.published_date.strftime('%Y-%m-%d %H:%M:%S') if article.published_date else 'N/A'
            }
            for article in articles
        ]

        return JsonResponse({'articles': articles_data}, safe=False)
