from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from .models import Article, ClickLog

User = get_user_model()


class TrackClickViewTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(email="test@example.com")
        self.article = Article.objects.create(
            title="Test Article",
            url="https://example.com/test-article",
            published_date="2023-01-01T12:00:00Z",
        )
        self.url = reverse("news:track_click", kwargs={"pk": self.article.pk})

    def test_authenticated_user_tracking(self):
        """
        ログインユーザーの場合:
        1. ClickLogが作成されること
        2. 記事URLへリダイレクトされること (302)
        """
        self.client.force_login(self.user)
        response = self.client.get(self.url)

        # Check redirect
        self.assertRedirects(
            response, self.article.url, fetch_redirect_response=False
        )

        # Check ClickLog created
        self.assertTrue(
            ClickLog.objects.filter(
                user=self.user, article=self.article
            ).exists()
        )

    def test_unauthenticated_user_redirect_page(self):
        """
        未ログインユーザーの場合:
        1. ClickLogが作成されないこと
        2. 警告ページ (200 OK) が表示されること
        3. 警告ページに「ログインしていません」が含まれること
        4. 警告ページに記事URLが含まれること
        """
        response = self.client.get(self.url)

        # Check status code
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "news/tracking_redirect.html")

        # Check content
        self.assertContains(response, "ログインしていません")
        self.assertContains(response, self.article.url)

        # Check ClickLog NOT created
        self.assertFalse(ClickLog.objects.exists())
