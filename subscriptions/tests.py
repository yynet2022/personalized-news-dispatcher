import io
import uuid
from unittest.mock import patch, MagicMock

from django.core.management import call_command
from django.contrib.auth import get_user_model
from django.test import TestCase, override_settings
from django.urls import reverse
from django.contrib.messages import get_messages

from .models import QuerySet, LargeCategory
from news.models import Article
from .services import FeedFetchError


User = get_user_model()


@override_settings(LOGGING_LEVEL='CRITICAL')
class SendDailyNewsCommandTest(TestCase):
    """
    management/commands/send_daily_news.py のテスト
    """
    @classmethod
    def setUpTestData(cls):
        # テスト全体で使うオブジェクトを作成
        cls.user1 = User.objects.create_user(
            'user1@example.com', 'password')
        cls.user2 = User.objects.create_user(
            'user2@example.com', 'password')
        cls.inactive_user = User.objects.create_user(
            'inactive@example.com', 'password', is_active=False)
        cls.category = LargeCategory.objects.create(name='Technology')

        # user1 に2つのQuerySetを設定
        cls.qs1_user1 = QuerySet.objects.create(
            user=cls.user1, name='Tech News', large_category=cls.category,
            query_str='Technology', auto_send=True)
        cls.qs2_user1 = QuerySet.objects.create(
            user=cls.user1, name='AI Weekly', large_category=cls.category,
            query_str='AI', auto_send=True)
        QuerySet.objects.create(
            user=cls.user1, name='Manual Send', large_category=cls.category,
            query_str='Manual', auto_send=False)

        # user2 に1つのQuerySetを設定
        cls.qs_user2 = QuerySet.objects.create(
            user=cls.user2, name='Sports', large_category=cls.category,
            query_str='Sports', auto_send=True)

        # テスト用の記事を事前に作成
        cls.article1 = Article.objects.create(
            url='http://example.com/tech', title='Tech Article')
        cls.article2 = Article.objects.create(
            url='http://example.com/ai', title='AI Article')
        cls.article3 = Article.objects.create(
            url='http://example.com/sports', title='Sports Article')

    @patch('subscriptions.management.commands.send_daily_news.send_digest_email')
    @patch('subscriptions.management.commands.send_daily_news.fetch_articles_for_queryset')
    def test_command_sends_email_to_active_users(
            self, mock_fetch, mock_send_email):
        """コマンドがアクティブユーザーの有効なQuerySetにメールを送信することをテスト"""
        # fetchが呼ばれた際の戻り値を設定
        mock_fetch.side_effect = [
            ('query', [self.article1]),  # user1 の Tech News
            ('query', [self.article2]),  # user1 の AI Weekly
            ('query', [self.article3]),  # user2 の Sports
        ]

        stdout = io.StringIO()
        call_command('send_daily_news', stdout=stdout)

        self.assertEqual(mock_send_email.call_count, 3)

        output = stdout.getvalue()
        self.assertIn('Processing user: user1@example.com', output)
        self.assertIn('Processing user: user2@example.com', output)
        self.assertNotIn('Processing user: inactive@example.com', output)
        self.assertNotIn('Manual Send', output)

    @patch('subscriptions.management.commands.send_daily_news.log_sent_articles')
    @patch('subscriptions.management.commands.send_daily_news.send_digest_email')
    @patch('subscriptions.management.commands.send_daily_news.fetch_articles_for_queryset')
    def test_n_plus_one_problem_is_solved(
            self, mock_fetch, mock_send_email, mock_log):
        """prefetch_relatedによってN+1問題が解決されているかテスト"""
        mock_fetch.return_value = ('query', [self.article1])

        # クエリ数をアサートする。QuerySetの取得でループが発生しないことを確認。
        # 1: User取得 + prefetch
        # 1-4: Djangoの内部クエリ (セッション、コンテントタイプ等)
        # 厳密な数は環境で変動しうるため、5クエリ以下であればOKとする
        with self.assertNumQueries(2):
            call_command('send_daily_news')

    @patch('subscriptions.management.commands.send_daily_news.send_digest_email')
    @patch('subscriptions.management.commands.send_daily_news.fetch_articles_for_queryset')
    def test_command_continues_on_user_processing_error(
            self, mock_fetch, mock_send_email):
        """一人のユーザー処理でエラーが発生しても処理が継続されるかテスト"""
        mock_fetch.side_effect = [
            ('query', [self.article1]),
            ('query', [self.article2]),
            ('query', [self.article3]),
        ]
        # user1の最初のメール送信でエラーを発生させる
        mock_send_email.side_effect = [
            Exception("SMTP Error"),  # user1, qs1
            None,                     # user1, qs2
            None,                     # user2, qs1
        ]

        stderr = io.StringIO()
        call_command('send_daily_news', stderr=stderr)

        # user1でエラーが出ても、残りのメール送信は試行される
        self.assertEqual(mock_send_email.call_count, 3)

        stderr_output = stderr.getvalue()
        # ユーザーレベルのエラーではなく、QuerySetレベルのエラーが出力されることを確認
        self.assertNotIn('Failed to process user', stderr_output)
        self.assertIn("An unexpected error occurred for queryset", stderr_output)
        self.assertIn("SMTP Error", stderr_output)

    @patch('subscriptions.management.commands.send_daily_news.send_digest_email')
    @patch('subscriptions.management.commands.send_daily_news.fetch_articles_for_queryset')
    def test_command_handles_feed_fetch_error(
            self, mock_fetch, mock_send_email):
        """FeedFetchErrorが発生した場合にエラーを記録して継続するかテスト"""
        mock_fetch.side_effect = [
            FeedFetchError("API limit reached"),  # user1, qs1
            ('query', [self.article2]),           # user1, qs2
            ('query', [self.article3]),           # user2, qs1
        ]

        stderr = io.StringIO()
        call_command('send_daily_news', stderr=stderr)

        # エラーが発生しても、成功した2つはメールが送信される
        self.assertEqual(mock_send_email.call_count, 2)
        self.assertIn(
            "Failed to fetch feed for queryset 'Tech News': API limit reached",
            stderr.getvalue())


class SubscriptionsViewsTest(TestCase):
    """
    subscriptions/views.py のテスト
    """
    @classmethod
    def setUpTestData(cls):
        cls.user = User.objects.create_user('testuser@example.com', 'password')
        cls.category = LargeCategory.objects.create(name='Test Category')
        cls.queryset = QuerySet.objects.create(
            user=cls.user, name='Test', large_category=cls.category,
            query_str='Test Query')

    def setUp(self):
        self.client.login(username='testuser@example.com', password='password')

    @patch('subscriptions.views.fetch_articles_for_preview')
    def test_news_preview_api_handles_feed_fetch_error(self, mock_fetch):
        """NewsPreviewApiViewがFeedFetchErrorを処理できるかテスト"""
        mock_fetch.side_effect = FeedFetchError("API is down")

        url = reverse('subscriptions:api_news_preview')
        response = self.client.get(url, {'q': 'test'})

        self.assertEqual(response.status_code, 502)
        self.assertJSONEqual(
            response.content.decode(),
            {'error': 'Failed to fetch news feed: API is down'}
        )

    @patch('subscriptions.views.fetch_articles_for_queryset')
    def test_send_manual_email_handles_feed_fetch_error(self, mock_fetch):
        """send_manual_emailビューがFeedFetchErrorを処理できるかテスト"""
        mock_fetch.side_effect = FeedFetchError("API is down")

        url = reverse('subscriptions:queryset_send',
                      kwargs={'pk': self.queryset.pk})
        response = self.client.post(url)

        messages = list(get_messages(response.wsgi_request))
        self.assertEqual(len(messages), 1)
        self.assertEqual(str(messages[0]),
                         'ニュースの取得に失敗しました: API is down')
        self.assertRedirects(response,
                             reverse('subscriptions:queryset_list'))
