from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse
from django.contrib.messages import get_messages

from .models import QuerySet, LargeCategory
from core.fetchers import FeedFetchError


User = get_user_model()


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
