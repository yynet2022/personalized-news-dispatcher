from django.contrib import admin

# Register your models here.
from django.contrib.auth.admin import UserAdmin
from .models import User


# Userモデルに合わせたカスタムUserAdminを作成
class CustomUserAdmin(UserAdmin):
    # UserAdminのfieldsetsからusernameを削除し、emailに置き換える
    # fieldsetsは、管理画面の編集ページでどのフィールドをどういう構成で表示するかを定義するもの
    fieldsets = (
        (None, {"fields": ("email", "password")}),
        ("Personal info", {"fields": ("first_name", "last_name")}),
        ("Permissions", {"fields":
                         ("is_active", "is_staff",
                          "is_superuser", "groups", "user_permissions")}),
        ("Important dates", {"fields": ("last_login", "date_joined")}),
    )
    # 管理画面の一覧ページに表示する項目
    list_display = ("email", "first_name", "last_name", "is_staff")
    # 管理画面の検索ボックスで検索対象となる項目
    search_fields = ("email", "first_name", "last_name")
    # 管理画面での並び順
    ordering = ("email",)


# 作成したカスタムUserAdminをUserモデルに適用
admin.site.register(User, CustomUserAdmin)
