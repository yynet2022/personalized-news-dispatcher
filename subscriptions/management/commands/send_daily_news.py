from django.core.management.base import BaseCommand

from users.models import User
from subscriptions.models import QuerySet
from subscriptions.services import (
    fetch_articles_for_queryset,
    send_digest_email,
    log_sent_articles
)


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

        active_users = User.objects.filter(is_active=True)

        for user in active_users:
            self.process_user(user, dry_run, options)

        self.stdout.write("Batch process finished.")

    def process_user(self, user, dry_run, options):
        """一人のユーザーに対する処理をまとめた関数"""
        self.stdout.write(f"Processing user: {user.email}")

        user_querysets = QuerySet.objects.filter(user=user)
        if not user_querysets.exists():
            self.stdout.write(f"  No querysets found for {user.email}. Skipping.")
            return

        querysets_with_articles = []
        all_new_articles = []

        # ユーザーの各QuerySetについて新しい記事を取得
        for queryset in user_querysets:
            self.stdout.write(f"  Processing queryset: {queryset.name}")
            
            new_articles = fetch_articles_for_queryset(
                queryset=queryset,
                user=user,
                after_days_override=options['after_days'],
                dry_run=dry_run
            )

            if new_articles:
                self.stdout.write(f"    Found {len(new_articles)} new articles.")
                querysets_with_articles.append({
                    'queryset_name': queryset.name,
                    'articles': new_articles,
                })
                all_new_articles.extend(new_articles)

        # 新しい記事があればメールを送信し、ログを記録
        if querysets_with_articles:
            if dry_run:
                self.stdout.write(f"  [DRY RUN] Would send digest email to {user.email}.")
                self.stdout.write(f"  [DRY RUN] Would log {len(all_new_articles)} articles as sent for {user.email}.")
            else:
                self.stdout.write(f"  Sending email to {user.email}.")
                send_digest_email(user, querysets_with_articles)
                
                self.stdout.write(f"  Logging {len(all_new_articles)} sent articles for {user.email}.")
                log_sent_articles(user, all_new_articles)
        else:
            self.stdout.write(f"  No new articles found for {user.email}.")
