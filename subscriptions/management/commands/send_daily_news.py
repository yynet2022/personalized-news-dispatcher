import feedparser
import requests
from urllib.parse import quote
from datetime import datetime, timezone, timedelta
from django.core.management.base import BaseCommand
from django.core.mail import send_mail
from django.conf import settings
from django.urls import reverse
from django.contrib.sites.models import Site
from django.template.loader import render_to_string
from users.models import User
from news.models import Article, SentArticleLog
from subscriptions.models import QuerySet


def get_published_date_from_entry(entry):
    """
    feedparserのentryからタイムゾーン付きのdatetimeオブジェクトを取得する。
    published_parsedがなければNoneを返す。
    """
    if hasattr(entry, 'published_parsed') and entry.published_parsed:
        # time.struct_timeをdatetimeオブジェクトに変換
        dt_naive = datetime(*entry.published_parsed[:6])
        # UTCタイムゾーンを付与
        return dt_naive.replace(tzinfo=timezone.utc)
    return None


class Command(BaseCommand):
    help = ('Fetches news based on QuerySets '
            'and sends them to users as HTML email.')

    def add_arguments(self, parser):
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Simulate the process without sending emails or writing to the database.',
        )
        parser.add_argument(
            '--after-days',
            type=int,
            default=2,
            help='Fetch articles published within the last N days. Set to 0 or less for no date limit.',
        )

    def handle(self, *args, **options):
        dry_run = options['dry_run']
        if dry_run:
            self.stdout.write(self.style.WARNING("[DRY RUN] Running in dry-run mode."))

        self.stdout.write("Starting the news fetching batch process...")

        current_site = Site.objects.get_current()
        site_url = f'http://{current_site.domain}'
        active_users = User.objects.filter(is_active=True)

        for user in active_users:
            self.process_user(user, site_url, dry_run, options)

        self.stdout.write("Batch process finished.")

    def process_user(self, user, site_url, dry_run, options):
        """一人のユーザーに対する処理をまとめた関数"""
        self.stdout.write(f"Processing user: {user.email}")

        user_querysets = QuerySet.objects.filter(user=user)
        if not user_querysets.exists():
            return

        querysets_with_articles, all_new_articles = \
            self.fetch_all_news(user, user_querysets, dry_run, options)

        if querysets_with_articles:
            if dry_run:
                self.stdout.write(f"  [DRY RUN] Would send digest email to {user.email}.")
                self.stdout.write(f"  [DRY RUN] Would log {len(all_new_articles)} articles as sent for {user.email}.")
            else:
                self.send_digest_email(user, querysets_with_articles, site_url)
                self.log_sent_articles(user, all_new_articles)
        else:
            self.stdout.write(f"  No new articles found for {user.email}.")

    def fetch_all_news(self, user, user_querysets, dry_run, options):
        """ユーザーの全QuerySetから新しいニュースを取得する関数"""
        querysets_with_articles = []
        all_new_articles = []

        for queryset in user_querysets:
            self.stdout.write(f"  Processing queryset: {queryset.name}")

            new_articles_for_queryset = \
                self.fetch_news_for_queryset(user, queryset, dry_run, options)

            if new_articles_for_queryset:
                querysets_with_articles.append({
                    'queryset_name': queryset.name,
                    'articles': new_articles_for_queryset,
                })
                all_new_articles.extend(new_articles_for_queryset)

        return querysets_with_articles, all_new_articles

    def fetch_news_for_queryset(self, user, queryset, dry_run, options):
        """一つのQuerySetからニュースを取得する関数"""
        after_days = options['after_days']
        date_query_param = ""
        if after_days > 0:
            two_days_ago = datetime.now() - timedelta(days=after_days)
            after_date = two_days_ago.strftime('%Y-%m-%d')
            date_query_param = f"after:{after_date}"

        base_url = ("https://news.google.com/rss/search?"
                    f"q={{query}}+{date_query_param}&hl=ja&gl=JP&ceid=JP:ja")
        encoded_query = quote(queryset.query_str)
        rss_url = base_url.format(query=encoded_query)

        if options['verbosity'] >= 1:
            self.stdout.write(f"    Fetching RSS from: {rss_url}")

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

        if options['verbosity'] >= 1:
            self.stdout.write(f"    Found {len(feed.entries)} entries in RSS feed.")

        new_articles = []
        for entry in feed.entries:
            published_date = get_published_date_from_entry(entry)

            # after_days が 0 より大きい場合のみ、日付フィルタリングを適用
            if after_days > 0 and published_date:
                # 現在時刻から after_days 日前を計算
                threshold_date = datetime.now(timezone.utc) - timedelta(days=after_days)
                if published_date < threshold_date:
                    if options['verbosity'] >= 1:
                        self.stdout.write(
                            f"    [SKIPPED] Article too old: "
                            f"\"{entry.title[:50]}...\" (Published: {published_date})")
                    continue # この記事はスキップ

            article = None
            created = False
            if dry_run:
                article = Article.objects.filter(url=entry.link).first()
                if not article:
                    article = Article(
                        url=entry.link,
                        title=entry.title,
                        published_date=published_date
                    )
                    created = True
                    self.stdout.write(
                        f'  [DRY RUN] Would create new article: "{article.title[:50]}..." (Published: {article.published_date})'
                    )
            else:
                article, created = Article.objects.get_or_create(
                    url=entry.link,
                    defaults={
                        'title': entry.title,
                        'published_date': published_date
                    }
                )

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
