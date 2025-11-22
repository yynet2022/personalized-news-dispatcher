from django.core.management.base import BaseCommand

from users.models import User
from subscriptions.models import QuerySet
from subscriptions.services import (
    fetch_articles_for_queryset,
    send_digest_email,
    log_sent_articles,
    FeedFetchError
)


class Command(BaseCommand):
    help = ('Fetches news based on QuerySets '
            'and sends them to users as HTML email.')

    def add_arguments(self, parser):
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help=('Simulate the process without sending emails '
                  'or writing to the database.'),
        )
        parser.add_argument(
            '--after-days',
            type=int,
            default=2,
            help=('Fetch articles published within the last N days. '
                  'Set to 0 or less for no date limit.'),
        )

    def handle(self, *args, **options):
        dry_run = options['dry_run']
        if dry_run:
            self.stdout.write(
                self.style.WARNING("[DRY RUN] Running in dry-run mode."))

        self.stdout.write("Starting the news fetching batch process...")

        active_users = User.objects.filter(
            is_active=True).prefetch_related('queryset_set')

        for user in active_users:
            try:
                self.process_user(user, dry_run, options)
            except Exception as e:
                self.stderr.write(self.style.ERROR(
                    f"Failed to process user {user.email}: {e}"))

        self.stdout.write("Batch process finished.")

    def process_user(self, user, dry_run, options):
        """一人のユーザーに対する処理をまとめた関数"""
        self.stdout.write(f"Processing user: {user.email}")

        # prefetch_related を使ってキャッシュされた結果を効率的に利用
        all_querysets = user.queryset_set.all()
        user_querysets = [qs for qs in all_querysets if qs.auto_send]
        if not user_querysets:
            self.stdout.write(
                f"  No active querysets for {user.email}. Skipping.")
            return

        # ユーザーの各QuerySetについて新しい記事を取得し、個別にメールを送信
        for queryset in user_querysets:
            self.stdout.write(f"  Processing queryset: {queryset.name}")
            try:
                query_with_date, new_articles = fetch_articles_for_queryset(
                    queryset=queryset,
                    user=user,
                    after_days_override=options['after_days'],
                    dry_run=dry_run
                )

                if new_articles:
                    self.stdout.write(
                        f"    Found {len(new_articles)} new articles.")
                    querysets_with_articles = [{
                        'queryset': queryset,
                        'queryset_name': queryset.name,
                        'query_str': query_with_date,
                        'articles': new_articles,
                    }]

                    if dry_run:
                        self.stdout.write(
                            "    [DRY RUN] "
                            f"Would send digest email to {user.email} "
                            f"for queryset '{queryset.name}'.")
                        self.stdout.write(
                            f"    [DRY RUN] "
                            f"Would log {len(new_articles)} articles as sent.")
                    else:
                        self.stdout.write(
                            f"    Sending email to {user.email} "
                            f"for queryset '{queryset.name}'.")
                        send_digest_email(user, querysets_with_articles)

                        self.stdout.write(
                            f"    Logging {len(new_articles)} sent articles.")
                        log_sent_articles(user, new_articles)
                else:
                    self.stdout.write(
                        f"    No new articles found for "
                        f"queryset '{queryset.name}'.")
            except FeedFetchError as e:
                self.stderr.write(self.style.ERROR(
                    f"  Failed to fetch feed for queryset '{queryset.name}': {e}"
                ))
            except Exception as e:
                self.stderr.write(self.style.ERROR(
                    f"  An unexpected error occurred for queryset '{queryset.name}': {e}"
                ))

