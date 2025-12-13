import time
from django.core.management.base import BaseCommand

from users.models import User
from subscriptions.models import QuerySet
from subscriptions.services import (
    fetch_articles_for_subscription,
    send_articles_email,
)
from core.services import log_sent_articles
from core.fetchers import FeedFetchError


class Command(BaseCommand):
    help = 'Fetches articles based on QuerySets and sends them to users.'

    def add_arguments(self, parser):
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help=('Simulate the process without sending emails '
                  'or writing to the database.'),
        )
        parser.add_argument(
            '--source',
            type=str,
            default='all',
            choices=['all', 'google_news', 'cinii', 'arxiv'],
            help='Specify the news source to fetch from.'
        )
        parser.add_argument(
            '--after-days',
            type=int,
            default=0,
            help=('Fetch articles published within the last N days. '
                  'If 0, uses the setting from each QuerySet.'),
        )
        parser.add_argument(
            '--interval',
            type=int,
            default=5,
            help='Interval in seconds between fetch operations.'
        )

    def handle(self, *args, **options):
        dry_run = options['dry_run']
        if dry_run:
            self.stdout.write(
                self.style.WARNING("[DRY RUN] Running in dry-run mode."))

        self.stdout.write("Starting the article dispatch process...")

        active_users = User.objects.filter(
            is_active=True, queryset__auto_send=True
        ).prefetch_related('queryset_set').distinct()

        for user in active_users:
            self.process_user(user, options)

        self.stdout.write("Article dispatch process finished.")

    def process_user(self, user, options):
        """Processes all relevant QuerySets for a single user."""
        dry_run = options['dry_run']
        interval = options['interval']
        source_filter = options['source']
        after_days_override = options['after_days'] \
            if options['after_days'] > 0 else None

        self.stdout.write(f"Processing user: {user.email}")

        # Prefetch されたデータを Python 上でフィルタリング
        all_querysets = [
            qs for qs in user.queryset_set.all() if qs.auto_send
        ]
        if source_filter != 'all':
            all_querysets = [
                qs for qs in all_querysets if qs.source == source_filter
            ]

        if not all_querysets:
            self.stdout.write(f"  No active querysets for {user.email} "
                              "matching the criteria. Skipping.")
            return

        for queryset in all_querysets:
            try:
                self.stdout.write(f"  Processing queryset: '{queryset.name}' "
                                  f"({queryset.get_source_display()})")

                if interval > 0:
                    time.sleep(interval)

                _, new_articles = fetch_articles_for_subscription(
                    queryset=queryset,
                    user=user,
                    after_days_override=after_days_override,
                    dry_run=dry_run
                )

                if new_articles:
                    self.stdout.write(
                        f"    Found {len(new_articles)} new articles.")
                    querysets_with_articles = [{
                        'queryset': queryset,
                        'queryset_name': queryset.name,
                        'query_str': queryset.query_str,
                        'articles': new_articles,
                    }]

                    if dry_run:
                        self.stdout.write(
                            "    [DRY RUN] Would send email and log articles.")
                    else:
                        # ソースに応じて件名とテンプレートを決定
                        template_name = 'news/email/news_digest_email'
                        if queryset.source == QuerySet.SOURCE_GOOGLE_NEWS:
                            subject = ('[News Dispatcher] Daily News Digest'
                                       f' - {queryset.name}')
                            enable_translation = True
                        elif queryset.source == QuerySet.SOURCE_CINII:
                            subject = ('[CiNii Research] Daily Digest'
                                       f' - {queryset.name}')
                            enable_translation = False
                        elif queryset.source == QuerySet.SOURCE_ARXIV:
                            subject = ('[arXiv] Daily Digest'
                                       f' - {queryset.name}')
                            enable_translation = False
                        else:
                            self.stderr.write(
                                f"Unknown source '{queryset.source}'."
                                " Skipping email.")
                            continue

                        self.stdout.write(f"    Sending email to {user.email}")
                        send_articles_email(
                            user=user,
                            querysets_with_articles=querysets_with_articles,
                            subject=subject,
                            template_name=template_name,
                            enable_translation=enable_translation
                        )

                        self.stdout.write("    Logging sent articles.")
                        log_sent_articles(user, new_articles)
                else:
                    self.stdout.write("    No new articles found.")

            except FeedFetchError as e:
                self.stderr.write(self.style.ERROR(
                    f"  Failed to fetch feed for '{queryset.name}': {e}"))
            except Exception as e:
                self.stderr.write(self.style.ERROR(
                    f"  An unexpected error occurred for '{queryset.name}':"
                    f" {e}"))
