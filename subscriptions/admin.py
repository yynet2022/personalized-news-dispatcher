from django.contrib import admin

from .models import (
    LargeCategory,
    UniversalKeywords,
    CurrentKeywords,
    RelatedKeywords,
    QuerySet
)

# モデルをAdminサイトに登録
admin.site.register(LargeCategory)
admin.site.register(UniversalKeywords)
admin.site.register(CurrentKeywords)
admin.site.register(RelatedKeywords)
admin.site.register(QuerySet)
