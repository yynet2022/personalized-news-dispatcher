from django.contrib import admin

# Register your models here.
from .models import Article, SentArticleLog

# モデルをAdminサイトに登録
admin.site.register(Article)
admin.site.register(SentArticleLog)
