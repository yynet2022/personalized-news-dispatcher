from django.core.management.base import BaseCommand
from django.utils import timezone
from datetime import timedelta
from collections import defaultdict

from users.models import User
from news.models import ClickLog, Article
from subscriptions.services import send_recommendation_email


class Command(BaseCommand):
    """
    最近クリックされた記事を集計し、各ユーザーがまだ読んでいない記事の中で、
    他のユーザーが多く読んでいる記事を推薦するメールを送信する。
    """
    help = ('Sends article recommendations to users based on '
            'what other users have recently read.')

    def add_arguments(self, parser):
        """コマンドライン引数を追加する"""
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help=('Simulate the process without sending emails.'),
        )
        parser.add_argument(
            '--hours',
            type=int,
            default=24,
            help='How many hours ago to look for clicks.',
        )
        parser.add_argument(
            '--max-articles',
            type=int,
            default=20,
            help='The maximum number of articles to recommend.',
        )

    def handle(self, *args, **options):
        """コマンドのメインロジック"""
        dry_run = options['dry_run']
        if dry_run:
            self.stdout.write(
                self.style.WARNING("[DRY RUN] Running in dry-run mode."))

        self.stdout.write("Starting the recommendation batch process...")

        hours = options['hours']
        max_articles = options['max_articles']
        since_time = timezone.now() - timedelta(hours=hours)

        # 期間内のクリックログを取得
        recent_clicks = ClickLog.objects.filter(
            clicked_at__gte=since_time
        ).select_related('user', 'article')

        if not recent_clicks.exists():
            self.stdout.write(self.style.SUCCESS(
                "No recent clicks found. Exiting."))
            return

        # 記事ごとにクリックしたユニークユーザーを収集
        article_readers = defaultdict(set)
        # ユーザーごとにクリックした記事を収集
        user_read_articles = defaultdict(set)

        for click in recent_clicks:
            # ユーザーが不明なクリックは除外
            if click.user:
                article_readers[click.article_id].add(click.user.id)
                user_read_articles[click.user.id].add(click.article_id)

        # popular_articles のリストを作成: (article_id, reader_count)
        popular_articles = [
            (article_id, len(users))
            for article_id, users in article_readers.items()
        ]
        # 読者が多い順にソート
        popular_articles.sort(key=lambda x: x[1], reverse=True)

        active_users = User.objects.filter(is_active=True)

        self.stdout.write(
            f"Found {len(popular_articles)} articles read by "
            f"{len(user_read_articles)} users in the last {hours} hours.")

        # 記事IDを一括で取得するための準備
        all_article_ids = [article_id for article_id, count in popular_articles]
        articles_in_bulk = Article.objects.in_bulk(all_article_ids)

        # これからユーザーごとの処理
        for user in active_users:
            read_articles_set = user_read_articles.get(user.id, set())

            recommendations = []
            for article_id, reader_count in popular_articles:
                # ユーザーが読んでいない、かつ記事DBに存在する
                if article_id not in read_articles_set and article_id in articles_in_bulk:
                    article = articles_in_bulk[article_id]
                    recommendations.append({
                        'article': article,
                        'count': reader_count
                    })

                if len(recommendations) >= max_articles:
                    break

            if recommendations:
                self.stdout.write(
                    f"  Found {len(recommendations)} recommendations for {user.email}")
                if dry_run:
                    self.stdout.write(f"    [DRY RUN] Would send email to {user.email}")
                else:
                    try:
                        self.stdout.write(f"    Sending email to {user.email}")
                        send_recommendation_email(user, recommendations)
                    except Exception as e:
                        self.stderr.write(self.style.ERROR(
                            f"    Failed to send email to {user.email}: {e}"))
            else:
                self.stdout.write(
                    f"  No new recommendations for {user.email}")

        self.stdout.write("Batch process finished.")
