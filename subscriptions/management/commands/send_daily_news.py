import feedparser
import requests
from urllib.parse import quote
from django.core.management.base import BaseCommand
from django.core.mail import send_mail
from django.conf import settings
from django.urls import reverse
from django.contrib.sites.models import Site
from django.template.loader import render_to_string
from users.models import User
from news.models import Article, SentArticleLog
from subscriptions.models import QuerySet


class Command(BaseCommand):
    help = ('Fetches news based on QuerySets '
            'and sends them to users as HTML email.')

    def handle(self, *args, **options):
        self.stdout.write("Starting the news fetching batch process...")

        current_site = Site.objects.get_current()
        site_url = f'http://{current_site.domain}'
        active_users = User.objects.filter(is_active=True)

        for user in active_users:
            self.process_user(user, site_url)

        self.stdout.write("Batch process finished.")

    def process_user(self, user, site_url):
        """一人のユーザーに対する処理をまとめた関数"""
        self.stdout.write(f"Processing user: {user.email}")

        user_querysets = QuerySet.objects.filter(user=user)
        if not user_querysets.exists():
            return

        querysets_with_articles, all_new_articles = \
            self.fetch_all_news(user, user_querysets)

        if querysets_with_articles:
            self.send_digest_email(user, querysets_with_articles, site_url)
            self.log_sent_articles(user, all_new_articles)
        else:
            self.stdout.write(f"  No new articles found for {user.email}.")

    def fetch_all_news(self, user, user_querysets):
        """ユーザーの全QuerySetから新しいニュースを取得する関数"""
        querysets_with_articles = []
        all_new_articles = []

        for queryset in user_querysets:
            self.stdout.write(f"  Processing queryset: {queryset.name}")

            new_articles_for_queryset = \
                self.fetch_news_for_queryset(user, queryset)

            if new_articles_for_queryset:
                querysets_with_articles.append({
                    'queryset_name': queryset.name,
                    'articles': new_articles_for_queryset,
                })
                all_new_articles.extend(new_articles_for_queryset)

        return querysets_with_articles, all_new_articles

    def fetch_news_for_queryset(self, user, queryset):
        """一つのQuerySetからニュースを取得する関数"""
        base_url = ("https://news.google.com/rss/search?"
                    "q={query}&hl=ja&gl=JP&ceid=JP:ja")
        encoded_query = quote(queryset.query_str)
        rss_url = base_url.format(query=encoded_query)

        try:
            # タイムアウトを10秒に設定
            response = requests.get(rss_url, timeout=10)
            # ステータスコードが200番台でなければ例外を発生
            response.raise_for_status()
        except requests.exceptions.RequestException as e:
            self.stderr.write(f"  Error fetching RSS feed for "
                              f"'{queryset.name}': {e}")
            return []

        feed = feedparser.parse(response.content)

        new_articles = []
        for entry in feed.entries:
            article, created = Article.objects.get_or_create(
                url=entry.link, defaults={'title': entry.title})
            is_sent = SentArticleLog.objects.filter(
                user=user, article=article).exists()
            if not is_sent:
                new_articles.append(article)
        return new_articles

    def send_digest_email(self, user, querysets_with_articles, site_url):
        """ニュースダイジェストメールを送信する関数"""
        self.stdout.write(f"  Sending email to {user.email}.")

        # テンプレートに渡す前にトラッキングURLを付与
        for item in querysets_with_articles:
            for article in item['articles']:
                tracking_path = reverse('news:track_click',
                                        kwargs={'pk': article.pk})
                article.tracking_url = site_url + tracking_path

        context = {
            'user': user,
            'querysets_with_articles': querysets_with_articles,
            'site_url': site_url,
        }

        plain_body = render_to_string('news/email/news_digest_email.txt',
                                      context)
        html_body = render_to_string('news/email/news_digest_email.html',
                                     context)

        send_mail(
            subject='【News Dispatcher】今日のニュースダイジェスト',
            message=plain_body,
            from_email=settings.EMAIL_HOST_USER,
            recipient_list=[user.email],
            fail_silently=False,
            html_message=html_body,
        )

    def log_sent_articles(self, user, all_new_articles):
        """送信済み記事をログに記録する関数"""
        for article in set(all_new_articles):
            SentArticleLog.objects.create(user=user, article=article)
