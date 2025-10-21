from django.shortcuts import render, redirect
from django.views.generic import CreateView, UpdateView, DeleteView, View
from django.contrib.auth.mixins import LoginRequiredMixin
from django.urls import reverse_lazy
from .models import QuerySet, MediumCategory, RelatedKeywords
from .forms import QuerySetForm
from django.http import JsonResponse
from django.db import IntegrityError
import feedparser
import requests
from urllib.parse import quote


class QuerySetListView(LoginRequiredMixin, View):
    def get(self, request, *args, **kwargs):
        querysets = QuerySet.objects.filter(user=request.user).order_by('name')
        context = {'querysets': querysets}
        return render(request, 'subscriptions/queryset_list.html', context)


def generate_query_str(form):
    large_cat_name = form.cleaned_data['large_category'].name
    
    medium_category_parts = []
    for medium_cat in form.cleaned_data['medium_categories']:
        medium_cat_name = f'"{medium_cat.name}"'
        
        # その中分類に紐づく関連キーワード
        related_keywords_for_medium = [
            f'"{kw.name}"' for kw in form.cleaned_data['related_keywords']
            if kw.medium_category == medium_cat
        ]
        
        # カスタムキーワード
        custom_keywords_for_medium = [
            kw.keywords for kw in form.cleaned_data['custom_keywords']
        ]
        
        # 中分類内のOR結合部分
        medium_or_parts = []
        if related_keywords_for_medium:
            medium_or_parts.extend(related_keywords_for_medium)
        if custom_keywords_for_medium:
            medium_or_parts.extend(custom_keywords_for_medium)
            
        if medium_or_parts:
            medium_category_parts.append(f'{medium_cat_name} AND ({ " OR ".join(medium_or_parts) })')
        else:
            medium_category_parts.append(medium_cat_name)

    # 大分類と中分類の結合
    if medium_category_parts:
        print(">>>", medium_category_parts)
        return f'"{large_cat_name}" AND ({ " OR ".join(medium_category_parts) })'
    else:
        return f'"{large_cat_name}"'


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

    def post(self, request, *args, **kwargs):
        self.object = None
        form = self.get_form()

        large_category_id = form.data.get('large_category')
        # IDに有効な値がある場合のみ、DBに問い合わせる
        if large_category_id:
            try:
                form.fields['medium_categories'].queryset = \
                    MediumCategory.objects.filter(
                        large_category_id=large_category_id)
            except (ValueError, TypeError):
                pass

        if form.is_valid():
            return self.form_valid(form)
        else:
            return self.form_invalid(form)


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

    def post(self, request, *args, **kwargs):
        self.object = self.get_object()
        form = self.get_form()

        large_category_id = form.data.get('large_category')
        if large_category_id:
            try:
                form.fields['medium_categories'].queryset = \
                    MediumCategory.objects.filter(
                        large_category_id=large_category_id)
            except (ValueError, TypeError):
                pass

        if form.is_valid():
            return self.form_valid(form)
        else:
            return self.form_invalid(form)


class QuerySetDeleteView(LoginRequiredMixin, DeleteView):
    model = QuerySet
    template_name = 'subscriptions/queryset_confirm_delete.html'
    success_url = reverse_lazy('subscriptions:queryset_list')

    def get_queryset(self):
        return QuerySet.objects.filter(user=self.request.user)


class MediumCategoryApiView(LoginRequiredMixin, View):
    def get(self, request, *args, **kwargs):
        large_category_id = request.GET.get('large_category_id')
        if not large_category_id:
            return JsonResponse({'error': 'large_category_id is required'},
                                status=400)

        medium_categories = MediumCategory.objects.filter(
            large_category_id=large_category_id)
        data = list(medium_categories.values('id', 'name'))
        return JsonResponse(data, safe=False)


class RelatedKeywordsApiView(LoginRequiredMixin, View):
    def get(self, request, *args, **kwargs):
        medium_category_ids = request.GET.getlist('medium_category_ids')
        if not medium_category_ids:
            return JsonResponse({'error': 'medium_category_ids is required'},
                                status=400)

        related_keywords = RelatedKeywords.objects.filter(
            medium_category__id__in=medium_category_ids).order_by('name')
        data = list(related_keywords.values('id', 'name', 'medium_category_id'))
        return JsonResponse(data, safe=False)


class NewsPreviewApiView(LoginRequiredMixin, View):
    def get(self, request, *args, **kwargs):
        query = request.GET.get('q')
        if not query:
            return JsonResponse({'error': 'Query parameter "q" is required'},
                                status=400)

        encoded_query = quote(query)
        base_url = ("https://news.google.com/rss/search?"
                    "q={query}&hl=ja&gl=JP&ceid=JP:ja")
        rss_url = base_url.format(query=encoded_query)

        try:
            # プレビューなのでタイムアウトは短めに5秒
            response = requests.get(rss_url, timeout=5)
            response.raise_for_status()
        except requests.exceptions.RequestException as e:
            # 外部サービスからの取得失敗は 502 Bad Gateway を返す
            return JsonResponse(
                {'error': f'Failed to fetch news feed: {e}'},
                status=502)

        feed = feedparser.parse(response.content)

        articles = []
        for entry in feed.entries[:5]:
            articles.append({
                'title': entry.title,
                'link': entry.link,
                'published': entry.get('published', 'N/A')
            })

        return JsonResponse({'feed': feed.feed, 'articles': articles},
                            safe=False)
