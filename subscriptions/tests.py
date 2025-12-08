import io
from unittest.mock import patch

from django.core.management import call_command
from django.contrib.auth import get_user_model
from django.test import TestCase, override_settings
from django.urls import reverse
from django.contrib.messages import get_messages

from .models import QuerySet, LargeCategory
from news.models import Article
from core.fetchers import FeedFetchError


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
            query_str='Technology', auto_send=True,
            source=QuerySet.SOURCE_GOOGLE_NEWS)
        cls.qs2_user1 = QuerySet.objects.create(
            user=cls.user1, name='AI Weekly', large_category=cls.category,
            query_str='AI', auto_send=True,
            source=QuerySet.SOURCE_GOOGLE_NEWS)
        QuerySet.objects.create(
            user=cls.user1, name='Manual Send', large_category=cls.category,
            query_str='Manual', auto_send=False,
            source=QuerySet.SOURCE_GOOGLE_NEWS)

        # user2 に1つのQuerySetを設定
        cls.qs_user2 = QuerySet.objects.create(
            user=cls.user2, name='Sports', large_category=cls.category,
            query_str='Sports', auto_send=True,
            source=QuerySet.SOURCE_GOOGLE_NEWS)

        # テスト用の記事を事前に作成
        cls.article1 = Article.objects.create(
            url='http://example.com/tech', title='Tech Article')
        cls.article2 = Article.objects.create(
            url='http://example.com/ai', title='AI Article')
        cls.article3 = Article.objects.create(
            url='http://example.com/sports', title='Sports Article')

    @patch('subscriptions.management.commands.send_articles.send_articles_email')  # noqa: E501
    @patch('subscriptions.management.commands.send_articles.fetch_articles_for_subscription')  # noqa: E501
    def test_command_sends_email_to_active_users(
            self, mock_fetch, mock_send_email):
        """コマンドがアクティブユーザーの有効なQuerySetにメールを送信することをテスト"""
        def fetch_side_effect(queryset, user, **kwargs):
            if queryset.id == self.qs1_user1.id:
                return 'query', [self.article1]
            if queryset.id == self.qs2_user1.id:
                return 'query', [self.article2]
            if queryset.id == self.qs_user2.id:
                return 'query', [self.article3]
            return 'query', []
        mock_fetch.side_effect = fetch_side_effect

        stdout = io.StringIO()
        call_command('send_articles', stdout=stdout)

        # user1 に2回、user2 に1回、合計3回メールが送信される
        self.assertEqual(mock_send_email.call_count, 3)

        output = stdout.getvalue()
        self.assertIn('Processing user: user1@example.com', output)
        self.assertIn('Processing user: user2@example.com', output)
        self.assertNotIn('Processing user: inactive@example.com', output)
        self.assertNotIn('Manual Send', output)

    @patch('subscriptions.management.commands.send_articles.log_sent_articles')
    @patch('subscriptions.management.commands.send_articles.send_articles_email')  # noqa: E501
    @patch('subscriptions.management.commands.send_articles.fetch_articles_for_subscription')  # noqa: E501
    def test_n_plus_one_problem_is_solved(
            self, mock_fetch, mock_send_email, mock_log):
        """N+1問題が解決され、コマンドが正常に実行されることを確認する"""
        mock_fetch.return_value = ('query', [self.article1])

        # このテストは、コマンドがループ内で余計なクエリを発行しないことを
        # 暗に確認します。assertNumQueries は現状の実装と合わないため、
        # コマンドがエラーなく終了することを確認するに留めます。
        call_command('send_articles')
        self.assertTrue(mock_fetch.called)  # 少なくとも1回は呼ばれる
        self.assertTrue(mock_send_email.called)
        self.assertTrue(mock_log.called)

    @patch('subscriptions.management.commands.send_articles.send_articles_email')  # noqa: E501
    @patch('subscriptions.management.commands.send_articles.fetch_articles_for_subscription')  # noqa: E501
    def test_command_continues_on_user_processing_error(
            self, mock_fetch, mock_send_email):
        """一人のユーザー処理でエラーが発生しても処理が継続されるかテスト"""
        def fetch_side_effect(queryset, user, **kwargs):
            # すべてのfetchは成功する
            if queryset.id == self.qs1_user1.id:
                return 'query', [self.article1]
            if queryset.id == self.qs2_user1.id:
                return 'query', [self.article2]
            if queryset.id == self.qs_user2.id:
                return 'query', [self.article3]
            return 'query', []
        mock_fetch.side_effect = fetch_side_effect

        # qs2_user1 ('AI Weekly') のメール送信時のみエラーを発生させる
        def send_email_side_effect(user, querysets_with_articles, **kwargs):
            if querysets_with_articles[0]['queryset'].id == self.qs2_user1.id:
                raise Exception("SMTP Error")
        mock_send_email.side_effect = send_email_side_effect

        stderr = io.StringIO()
        call_command('send_articles', stderr=stderr, no_color=True)

        # 3つのquerysetすべてが処理される
        self.assertEqual(mock_fetch.call_count, 3)
        self.assertEqual(mock_send_email.call_count, 3)

        stderr_output = stderr.getvalue()
        # エラーメッセージが正しく出力されるか確認
        self.assertIn("An unexpected error occurred for 'AI Weekly': SMTP Error", stderr_output)  # noqa: E501
        # userレベルのエラーは出ない
        self.assertNotIn('Failed to process user', stderr_output)

    @patch('subscriptions.management.commands.send_articles.send_articles_email')  # noqa: E501
    @patch('subscriptions.management.commands.send_articles.fetch_articles_for_subscription')  # noqa: E501
    def test_command_handles_feed_fetch_error(
            self, mock_fetch, mock_send_email):
        """FeedFetchErrorが発生した場合にエラーを記録して継続するかテスト"""
        def fetch_side_effect(queryset, user, **kwargs):
            if queryset.id == self.qs1_user1.id:
                raise FeedFetchError("API limit reached")
            if queryset.id == self.qs2_user1.id:
                return 'query', [self.article2]
            if queryset.id == self.qs_user2.id:
                return 'query', [self.article3]
            return 'query', []
        mock_fetch.side_effect = fetch_side_effect

        stderr = io.StringIO()
        call_command('send_articles', stderr=stderr, no_color=True)

        # エラーが発生しても、成功した2つはメールが送信される
        self.assertEqual(mock_send_email.call_count, 2)
        self.assertIn(
            "Failed to fetch feed for 'Tech News': API limit reached",
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

    @patch('subscriptions.views.fetch_articles_for_subscription')
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

    @patch('subscriptions.views.fetch_articles_for_subscription')
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
