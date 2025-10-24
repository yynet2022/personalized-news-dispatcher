from django.shortcuts import render, redirect
from django.views.generic import CreateView, UpdateView, DeleteView, View
from django.contrib.auth.mixins import LoginRequiredMixin
from django.urls import reverse_lazy
from .models import QuerySet, UniversalKeywords, CurrentKeywords, RelatedKeywords
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

    return " OR ".join(parts)


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
