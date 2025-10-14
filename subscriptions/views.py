from django.shortcuts import render, redirect
from django.views.generic import CreateView, UpdateView, DeleteView, View
from django.contrib.auth.mixins import LoginRequiredMixin
from django.urls import reverse_lazy
from .models import QuerySet, MediumCategory
from .forms import QuerySetForm
from django.http import JsonResponse
from django.db import IntegrityError
import feedparser
from urllib.parse import quote


class QuerySetListView(LoginRequiredMixin, View):
    def get(self, request, *args, **kwargs):
        querysets = QuerySet.objects.filter(user=request.user).order_by('name')
        context = {'querysets': querysets}
        return render(request, 'subscriptions/queryset_list.html', context)


def generate_query_str(form):
    large_cat_name = form.cleaned_data['large_category'].name
    medium_cat_names = [
        cat.name for cat in form.cleaned_data['medium_categories']]
    custom_keys_str = [
        f"({kw.keywords})" for kw in form.cleaned_data['custom_keywords']]
    or_parts = medium_cat_names + custom_keys_str
    or_query = " OR ".join(or_parts)
    return f'"{large_cat_name}" AND ({or_query})' \
        if or_query else f'"{large_cat_name}"'


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

        # --- ▼▼▼ こちらも同様に修正 ▼▼▼ ---
        large_category_id = form.data.get('large_category')
        if large_category_id:
            try:
                form.fields['medium_categories'].queryset = \
                    MediumCategory.objects.filter(
                        large_category_id=large_category_id)
            except (ValueError, TypeError):
                pass
        # --- ▲▲▲ ここまで ▲▲▲ ---

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

        feed = feedparser.parse(rss_url)

        articles = []
        for entry in feed.entries[:5]:
            articles.append({
                'title': entry.title,
                'link': entry.link,
                'published': entry.get('published', 'N/A')
            })

        return JsonResponse({'feed': feed.feed, 'articles': articles}, safe=False)
