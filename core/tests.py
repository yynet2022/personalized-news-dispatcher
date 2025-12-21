from django.test import TestCase
from django.utils import timezone
from unittest.mock import patch
from users.models import User
from news.models import Article, SentArticleLog
from subscriptions.models import QuerySet, LargeCategory
from core.fetchers import ArticleFetcher
# from datetime import timedelta
from typing import List, Tuple, Union


class TestArticleFetcher(ArticleFetcher):
    """ArticleFetcherの抽象メソッドを実装したテスト用クラス"""
    def fetch_articles(
        self,
        dry_run: bool = False,
        after_days_override: Union[int, None] = None,
        enable_translation: bool = True
    ) -> Tuple[str, List[Article]]:
        return "query", []


class ArticleFetcherTest(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            email='test@example.com', password='password')
        self.category = LargeCategory.objects.create(name='Test Cat')
        self.queryset = QuerySet.objects.create(
            user=self.user,
            name='Test QuerySet',
            query_str='test',
            large_category=self.category
        )
        self.fetcher = TestArticleFetcher(self.queryset, self.user)

    @patch('core.fetchers.translate_titles_batch')
    def test_save_articles_creates_articles(self, mock_translate):
        # 翻訳されたタイトルを返すように設定
        mock_translate.side_effect = (
            lambda titles, target_language: [f"Translated: {t}"
                                             for t in titles]
        )

        data = [
            {
                'title': 'Test Article 1',
                'url': 'http://example.com/1',
                'published_date': timezone.now()
            },
            {
                'title': 'Test Article 2',
                'url': 'http://example.com/2',
                'published_date': timezone.now()
            }
        ]
        # target_languageを指定して翻訳を実行させる
        saved = self.fetcher.save_articles(data, target_language='Japanese')
        self.assertEqual(len(saved), 2)
        self.assertEqual(Article.objects.count(), 2)
        # 翻訳が反映されているか確認
        self.assertEqual(saved[0].title, 'Translated: Test Article 1')
        self.assertEqual(saved[1].title, 'Translated: Test Article 2')

    @patch('core.fetchers.translate_titles_batch')
    def test_save_articles_skips_sent_articles(self, mock_translate):
        mock_translate.side_effect = lambda titles: titles

        # 記事を事前に作成し、送信済みログを作成
        article = Article.objects.create(
            url='http://example.com/sent',
            title='Sent Article',
            published_date=timezone.now()
        )
        SentArticleLog.objects.create(user=self.user, article=article)

        # Fetcherを再初期化（既読リストを読み込むため）
        self.fetcher = TestArticleFetcher(self.queryset, self.user)

        data = [
            {
                'title': 'Sent Article',
                'url': 'http://example.com/sent',
                'published_date': timezone.now()
            },
            {
                'title': 'New Article',
                'url': 'http://example.com/new',
                'published_date': timezone.now()
            }
        ]

        saved = self.fetcher.save_articles(data)

        # Sent Articleはスキップされるはず
        self.assertEqual(len(saved), 1)
        self.assertEqual(saved[0].url, 'http://example.com/new')

    @patch('core.fetchers.translate_titles_batch')
    def test_save_articles_dry_run(self, mock_translate):
        mock_translate.side_effect = lambda titles: titles

        data = [
            {
                'title': 'Dry Run Article',
                'url': 'http://example.com/dry',
                'published_date': timezone.now()
            }
        ]
        saved = self.fetcher.save_articles(data, dry_run=True)

        self.assertEqual(len(saved), 1)
        # DBには保存されていないはず
        self.assertEqual(
            Article.objects.filter(url='http://example.com/dry').count(), 0)
        # 返されたオブジェクトは正しいか
        self.assertEqual(saved[0].title, 'Dry Run Article')

    @patch('core.fetchers.translate_titles_batch')
    def test_save_articles_idempotency(self, mock_translate):
        """get_or_createが正しく動作し、重複作成されないことを確認"""
        mock_translate.side_effect = lambda titles: titles

        data = [
            {
                'title': 'Duplicate Article',
                'url': 'http://example.com/dup',
                'published_date': timezone.now()
            }
        ]

        # 1回目
        saved1 = self.fetcher.save_articles(data)
        self.assertEqual(len(saved1), 1)

        # 2回目
        saved2 = self.fetcher.save_articles(data)
        self.assertEqual(len(saved2), 1)

        # DB上のカウントは1であるべき
        self.assertEqual(
            Article.objects.filter(url='http://example.com/dup').count(), 1)
