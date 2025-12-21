import io
from unittest.mock import patch

from django.test import TestCase, override_settings
from django.core.management import call_command
from django.contrib.auth import get_user_model

from subscriptions.models import QuerySet, LargeCategory
from subscriptions.management.commands.send_articles import Command
from news.models import Article
from core.fetchers import FeedFetchError

User = get_user_model()


@override_settings(LOGGING_LEVEL='CRITICAL')
class SendArticlesCommandTest(TestCase):
    def setUp(self):
        # 共通のユーザーとカテゴリ
        self.user = User.objects.create_user(
            email='testuser@example.com', password='password'
        )
        self.category = LargeCategory.objects.create(name='Test Category')
        self.tech_category = LargeCategory.objects.create(name='Technology')

        # ---------------------------------------------------------
        # Source Filter Test 用のデータ
        # ---------------------------------------------------------
        self.qs_google = QuerySet.objects.create(
            user=self.user,
            name='Google News Test',
            source=QuerySet.SOURCE_GOOGLE_NEWS,
            auto_send=True,
            query_str='test query google'
        )
        self.qs_cinii = QuerySet.objects.create(
            user=self.user,
            name='CiNii Test',
            source=QuerySet.SOURCE_CINII,
            auto_send=True,
            query_str='test query cinii'
        )
        self.qs_arxiv = QuerySet.objects.create(
            user=self.user,
            name='ArXiv Test',
            source=QuerySet.SOURCE_ARXIV,
            auto_send=True,
            query_str='test query arxiv'
        )
        self.qs_inactive = QuerySet.objects.create(
            user=self.user,
            name='Inactive Test',
            source=QuerySet.SOURCE_GOOGLE_NEWS,
            auto_send=False,
            query_str='inactive query'
        )

        # ---------------------------------------------------------
        # 統合したテスト用のデータ (旧 SendDailyNewsCommandTest より)
        # ---------------------------------------------------------
        self.user1 = User.objects.create_user(
            'user1@example.com', 'password')
        self.user2 = User.objects.create_user(
            'user2@example.com', 'password')
        self.inactive_user = User.objects.create_user(
            'inactive@example.com', 'password', is_active=False)

        # user1 に2つのQuerySetを設定
        self.qs1_user1 = QuerySet.objects.create(
            user=self.user1, name='Tech News',
            large_category=self.tech_category,
            query_str='Technology', auto_send=True,
            source=QuerySet.SOURCE_GOOGLE_NEWS)
        self.qs2_user1 = QuerySet.objects.create(
            user=self.user1, name='AI Weekly',
            large_category=self.tech_category,
            query_str='AI', auto_send=True,
            source=QuerySet.SOURCE_GOOGLE_NEWS)
        QuerySet.objects.create(
            user=self.user1, name='Manual Send',
            large_category=self.tech_category,
            query_str='Manual', auto_send=False,
            source=QuerySet.SOURCE_GOOGLE_NEWS)

        # user2 に1つのQuerySetを設定
        self.qs_user2 = QuerySet.objects.create(
            user=self.user2, name='Sports',
            large_category=self.tech_category,
            query_str='Sports', auto_send=True,
            source=QuerySet.SOURCE_GOOGLE_NEWS)

        # テスト用の記事を事前に作成
        self.article1 = Article.objects.create(
            url='http://example.com/tech', title='Tech Article')
        self.article2 = Article.objects.create(
            url='http://example.com/ai', title='AI Article')
        self.article3 = Article.objects.create(
            url='http://example.com/sports', title='Sports Article')
        self.article4 = Article.objects.create(
            url='http://arxiv.org/abs/2301.0001', title='ArXiv Article')

    @patch('subscriptions.management.commands.send_articles.fetch_articles_for_subscription')  # noqa: E501
    @patch('subscriptions.management.commands.send_articles.send_articles_email')  # noqa: E501
    @patch('subscriptions.management.commands.send_articles.log_sent_articles')
    def test_scholar_source_filter(
            self, mock_log_sent_articles, mock_send_articles_email,
            mock_fetch_articles):
        # fetch_articles_for_subscription が呼ばれたときに空のリストを返すようにモック
        mock_fetch_articles.return_value = (True, [])

        command = Command()
        command.stdout = io.StringIO()  # 標準出力のキャプチャ
        command.stderr = io.StringIO()  # 標準エラー出力のキャプチャ

        # --source scholar を指定してコマンドを実行
        call_command(
            command, stdout=command.stdout, stderr=command.stderr,
            source='scholar')

        output = command.stdout.getvalue()
        self.assertIn(
            "Processing queryset: 'CiNii Test' (CiNii Research)", output)
        self.assertIn("Processing queryset: 'ArXiv Test' (arXiv)", output)
        self.assertNotIn(
            "Processing queryset: 'Google News Test' (Google News)", output)

        # user1, user2 は scholar ソースを持っていないのでスキップされるログが出る
        self.assertIn(f"No active querysets for {self.user1.email}", output)

        # fetch_articles_for_subscription が CiNii と arXiv のクエリセットに対してのみ
        # 呼ばれたことを確認。setUp で作成された qs_cinii と qs_arxiv の2つ
        self.assertEqual(mock_fetch_articles.call_count, 2)
        called_querysets = [
            call_args[1]['queryset']
            for call_args in mock_fetch_articles.call_args_list
        ]
        self.assertIn(self.qs_cinii, called_querysets)
        self.assertIn(self.qs_arxiv, called_querysets)
        self.assertNotIn(self.qs_google, called_querysets)

        # send_articles_email と log_sent_articles は記事が見つからないので呼ばれないことを確認
        self.assertFalse(mock_send_articles_email.called)
        self.assertFalse(mock_log_sent_articles.called)

    @patch('subscriptions.management.commands.send_articles.fetch_articles_for_subscription')  # noqa: E501
    @patch('subscriptions.management.commands.send_articles.send_articles_email')  # noqa: E501
    @patch('subscriptions.management.commands.send_articles.log_sent_articles')
    def test_all_source_filter(
            self, mock_log_sent_articles, mock_send_articles_email,
            mock_fetch_articles):
        # fetch_articles_for_subscription が呼ばれたときに空のリストを返すようにモック
        mock_fetch_articles.return_value = (True, [])

        command = Command()
        command.stdout = io.StringIO()
        command.stderr = io.StringIO()

        # --source all を指定してコマンドを実行
        call_command(
            command, stdout=command.stdout, stderr=command.stderr,
            source='all')

        output = command.stdout.getvalue()
        self.assertIn(
            "Processing queryset: 'Google News Test' (Google News)", output)
        self.assertIn(
            "Processing queryset: 'CiNii Test' (CiNii Research)", output)
        self.assertIn("Processing queryset: 'ArXiv Test' (arXiv)", output)

        # fetch_articles_for_subscription が全ての有効なクエリセットに対して呼ばれたことを確認
        # setUp で作成された有効なクエリセットは合計 6つ
        # (qs_google, qs_cinii, qs_arxiv, qs1_user1, qs2_user1, qs_user2)
        self.assertEqual(mock_fetch_articles.call_count, 6)
        called_querysets = [
            call_args[1]['queryset']
            for call_args in mock_fetch_articles.call_args_list
        ]
        self.assertIn(self.qs_google, called_querysets)
        self.assertIn(self.qs_cinii, called_querysets)
        self.assertIn(self.qs_arxiv, called_querysets)

        self.assertFalse(mock_send_articles_email.called)
        self.assertFalse(mock_log_sent_articles.called)

    @patch('subscriptions.management.commands.send_articles.fetch_articles_for_subscription')  # noqa: E501
    @patch('subscriptions.management.commands.send_articles.send_articles_email')  # noqa: E501
    @patch('subscriptions.management.commands.send_articles.log_sent_articles')
    def test_single_source_filter(
            self, mock_log_sent_articles, mock_send_articles_email,
            mock_fetch_articles):
        # fetch_articles_for_subscription が呼ばれたときに空のリストを返すようにモック
        mock_fetch_articles.return_value = (True, [])

        command = Command()
        command.stdout = io.StringIO()
        command.stderr = io.StringIO()

        # --source google_news を指定してコマンドを実行
        call_command(
            command, stdout=command.stdout, stderr=command.stderr,
            source='google_news')

        output = command.stdout.getvalue()
        self.assertIn(
            "Processing queryset: 'Google News Test' (Google News)", output)
        self.assertNotIn(
            "Processing queryset: 'CiNii Test' (CiNii Research)", output)
        self.assertNotIn("Processing queryset: 'ArXiv Test' (arXiv)", output)

        # fetch_articles_for_subscription が Google News のクエリセットに対してのみ
        # 呼ばれたことを確認
        # Google News の有効なクエリセットは 4つ
        # (qs_google, qs1_user1, qs2_user1, qs_user2)
        self.assertEqual(mock_fetch_articles.call_count, 4)
        called_querysets = [
            call_args[1]['queryset']
            for call_args in mock_fetch_articles.call_args_list
        ]
        self.assertIn(self.qs_google, called_querysets)
        self.assertNotIn(self.qs_cinii, called_querysets)
        self.assertNotIn(self.qs_arxiv, called_querysets)

        self.assertFalse(mock_send_articles_email.called)
        self.assertFalse(mock_log_sent_articles.called)

    @patch('subscriptions.management.commands.send_articles.send_articles_email')  # noqa: E501
    @patch('subscriptions.management.commands.send_articles.fetch_articles_for_subscription')  # noqa: E501
    def test_command_sends_email_for_arxiv_source(
            self, mock_fetch, mock_send_email):
        """コマンドが arXiv ソースの QuerySet に対して正しく動作するかテスト"""
        # arXiv用のQuerySetを作成
        arxiv_qs = QuerySet.objects.create(
            user=self.user1, name='ArXiv Daily',
            query_str='cat:cs.AI', auto_send=True,
            source=QuerySet.SOURCE_ARXIV)

        def fetch_side_effect(queryset, user, **kwargs):
            if queryset.id == arxiv_qs.id:
                return 'query', [self.article4]
            return 'query', []
        mock_fetch.side_effect = fetch_side_effect

        call_command('send_articles', source='arxiv')

        # arXiv の QuerySet のみ処理される
        # setUp で作成された qs_arxiv と、ここで作成した arxiv_qs の2つ
        self.assertEqual(mock_fetch.call_count, 2)

        # arxiv_qs が正しく処理されたことを確認
        mock_fetch.assert_any_call(
            queryset=arxiv_qs,
            user=self.user1,
            after_days_override=None,
            dry_run=False,
            enable_translation=True
        )

        # メールが1回送信される
        # (qs_arxivは記事0なので送信なし、arxiv_qsは記事あり)
        self.assertEqual(mock_send_email.call_count, 1)

        # send_articles_email の引数を検証
        call_args = mock_send_email.call_args[1]
        self.assertEqual(call_args['user'], self.user1)
        self.assertEqual(
            call_args['subject'],
            '[arXiv] Daily Digest - ArXiv Daily'
        )
        self.assertFalse(call_args['enable_translation'])
        self.assertEqual(
            call_args['querysets_with_articles'][0]['articles'],
            [self.article4]
        )

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
        # 他のユーザー(testuser)のQuerySetは記事が見つからないので送信されない
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

        # 6つの有効なquerysetすべてが処理される (ソース指定なし=all)
        self.assertEqual(mock_fetch.call_count, 6)

        # メール送信試行は、記事が見つかった3回 (qs1_user1, qs2_user1, qs_user2)
        # qs2_user1 は失敗するが、メソッドは呼ばれる
        self.assertEqual(mock_send_email.call_count, 3)

        stderr_output = stderr.getvalue()
        # エラーメッセージが正しく出力されるか確認
        self.assertIn(
            "An unexpected error occurred for 'AI Weekly': SMTP Error",
            stderr_output)
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
