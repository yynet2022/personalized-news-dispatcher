from django.contrib import admin

# Register your models here.
from .models import LargeCategory, MediumCategory, CustomKeywords, QuerySet

# モデルをAdminサイトに登録
admin.site.register(LargeCategory)
admin.site.register(MediumCategory)
admin.site.register(CustomKeywords)
admin.site.register(QuerySet)
