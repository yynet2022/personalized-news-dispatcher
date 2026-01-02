import shlex

from django import forms

from .models import (
    ArXivKeywords,
    CiNiiKeywords,
    CurrentKeywords,
    QuerySet,
    RelatedKeywords,
    UniversalKeywords,
)


def _split(s: str):
    parts = []
    for p in shlex.split(s):
        p = p.strip()
        if p:
            parts.append(f'"{p}"' if " " in p else p)
    return parts


class QuerySetForm(forms.ModelForm):
    class Meta:
        model = QuerySet
        fields = [
            "name",
            "source",
            "auto_send",
            # Google News fields
            "large_category",
            "country",
            "universal_keywords",
            "current_keywords",
            "related_keywords",
            # CiNii fields
            "cinii_keywords",
            # arXiv fields
            "arxiv_keywords",
            # Common fields
            "additional_or_keywords",
            "refinement_keywords",
            "after_days",
            "max_articles",
        ]
        widgets = {
            "source": forms.RadioSelect,
            "universal_keywords": forms.CheckboxSelectMultiple,
            "current_keywords": forms.CheckboxSelectMultiple,
            "related_keywords": forms.CheckboxSelectMultiple,
            "cinii_keywords": forms.CheckboxSelectMultiple,
            "arxiv_keywords": forms.CheckboxSelectMultiple,
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        f_ = self.fields

        # --- Google News field setup ---
        f_["universal_keywords"].label_from_instance = lambda x: x.name
        f_["current_keywords"].label_from_instance = lambda x: x.name
        f_["related_keywords"].label_from_instance = lambda x: x.name
        f_["universal_keywords"].queryset = UniversalKeywords.objects.none()
        f_["current_keywords"].queryset = CurrentKeywords.objects.none()
        f_["related_keywords"].queryset = RelatedKeywords.objects.none()

        if "large_category" in self.data:
            large_category_id = self.data.get("large_category")
            if large_category_id:
                try:
                    f_["universal_keywords"].queryset = (
                        UniversalKeywords.objects.filter(
                            large_category_id=large_category_id
                        ).order_by("name")
                    )
                    f_["current_keywords"].queryset = (
                        CurrentKeywords.objects.filter(
                            large_category_id=large_category_id
                        ).order_by("name")
                    )
                    f_["related_keywords"].queryset = (
                        RelatedKeywords.objects.filter(
                            large_category_id=large_category_id
                        ).order_by("name")
                    )
                except (ValueError, TypeError):
                    pass
        elif self.instance.pk and self.instance.large_category_id:
            f_["universal_keywords"].queryset = (
                self.instance.large_category.universalkeywords_set.order_by(
                    "name"
                )
            )
            f_["current_keywords"].queryset = (
                self.instance.large_category.currentkeywords_set.order_by(
                    "name"
                )
            )
            f_["related_keywords"].queryset = (
                self.instance.large_category.relatedkeywords_set.order_by(
                    "name"
                )
            )

        # --- CiNii field setup ---
        f_["cinii_keywords"].queryset = CiNiiKeywords.objects.order_by("name")
        f_["cinii_keywords"].label_from_instance = lambda obj: obj.name

        # --- arXiv field setup ---
        f_["arxiv_keywords"].queryset = ArXivKeywords.objects.order_by("name")
        f_["arxiv_keywords"].label_from_instance = lambda obj: obj.name

        # --- Common field setup ---
        f_["after_days"].widget.attrs.update({"min": 0})
        f_["max_articles"].widget.attrs.update({"min": 1})

        # --- Disable source on update ---
        if self.instance and not self.instance._state.adding:
            self.fields["source"].disabled = True

    def clean(self):
        cleaned_data = super().clean()
        source = cleaned_data.get("source")

        if source == QuerySet.SOURCE_GOOGLE_NEWS:
            # CiNii関連のフィールドをクリア
            if "cinii_keywords" in cleaned_data:
                cleaned_data["cinii_keywords"] = CiNiiKeywords.objects.none()

        elif source == QuerySet.SOURCE_CINII:
            # Google News関連のフィールドをクリア
            self._clear_google_news_fields(cleaned_data)

        elif source == QuerySet.SOURCE_ARXIV:
            # Google News と CiNii 関連のフィールドをクリア
            self._clear_google_news_fields(cleaned_data)
            if "cinii_keywords" in cleaned_data:
                cleaned_data["cinii_keywords"] = CiNiiKeywords.objects.none()

        return cleaned_data

    def _clear_google_news_fields(self, cleaned_data):
        """Google News関連のフィールドをクリアするヘルパーメソッド"""
        cleaned_data["large_category"] = None
        cleaned_data["country"] = ""
        if "universal_keywords" in cleaned_data:
            cleaned_data["universal_keywords"] = (
                UniversalKeywords.objects.none()
            )
        if "current_keywords" in cleaned_data:
            cleaned_data["current_keywords"] = CurrentKeywords.objects.none()
        if "related_keywords" in cleaned_data:
            cleaned_data["related_keywords"] = RelatedKeywords.objects.none()

    def save(self, commit=True):
        instance = super().save(commit=False)

        source = self.cleaned_data.get("source")
        if source == QuerySet.SOURCE_GOOGLE_NEWS:
            instance.query_str = self._build_google_news_query()
        elif source == QuerySet.SOURCE_CINII:
            instance.query_str = self._build_cinii_query()
        elif source == QuerySet.SOURCE_ARXIV:
            instance.query_str = self._build_arxiv_query()

        if commit:
            instance.save()
            self.save_m2m()

        return instance

    def _build_google_news_query(self):
        parts = []
        if self.cleaned_data.get("large_category"):
            parts.append(self.cleaned_data.get("large_category").name)

        for field in [
            "universal_keywords",
            "current_keywords",
            "related_keywords",
        ]:
            for keyword in self.cleaned_data.get(field, []):
                parts.append(keyword.name)

        additional = self.cleaned_data.get("additional_or_keywords", "")
        parts.extend(_split(additional))

        or_part = " OR ".join(parts)
        if len(parts) > 1:
            or_part = f"({or_part})"

        refinement = self.cleaned_data.get("refinement_keywords", "")
        return f"{or_part} {refinement}".strip()

    def _build_cinii_query(self):
        parts = []
        for keyword in self.cleaned_data.get("cinii_keywords", []):
            # スペースを含むものはダブルクオートで囲む
            name = keyword.name
            parts.append(f'"{name}"' if " " in name else name)

        additional = self.cleaned_data.get("additional_or_keywords", "")
        parts.extend(_split(additional))

        or_part = " OR ".join(parts)
        if len(parts) > 1:
            or_part = f"({or_part})"

        refinement = self.cleaned_data.get("refinement_keywords", "")
        return f"{or_part} {refinement}".strip()

    def _build_arxiv_query(self):
        """arXivの検索クエリを構築する。"""
        # https://info.arxiv.org/help/api/user-manual.html#query_details
        parts = []

        # 選択されたキーワード
        for keyword in self.cleaned_data.get("arxiv_keywords", []):
            name = keyword.name
            # スペースを含む場合はダブルクオートで囲む
            part = f'"{name}"' if " " in name else name
            parts.append(f"all:{part}")

        # OR追加キーワード
        additional = self.cleaned_data.get("additional_or_keywords", "")
        for p in _split(additional):
            parts.append(f"all:{p}")

        or_part = " OR ".join(parts)
        if len(parts) > 1:
            or_part = f"({or_part})"

        # 絞り込みキーワード
        refinement = self.cleaned_data.get("refinement_keywords", "")
        refinement_parts = []
        if refinement:
            # refinement_keywords をスペースで分割し、AND/ANDNOTを処理
            for term in shlex.split(refinement):
                term = term.strip()
                if not term:
                    continue
                # マイナスから始まる場合は ANDNOT
                if term.startswith("-"):
                    term_body = term[1:]
                    # フレーズ検索のためにダブルクオートで囲む
                    if " " in term_body:
                        term_body = f'"{term_body}"'
                    refinement_parts.append(f"ANDNOT all:{term_body}")
                # それ以外は AND
                else:
                    term_body = term
                    if " " in term_body:
                        term_body = f'"{term_body}"'
                    refinement_parts.append(f"AND all:{term_body}")

        refinement_part = " ".join(refinement_parts)

        # クエリの組み立て
        if or_part and refinement_part:
            return f"{or_part} {refinement_part}".strip()
        elif or_part:
            return or_part
        elif refinement_part:
            # AND/ANDNOTのみの場合は先頭の演算子を削除
            first_part = refinement_parts[0].split(" ", 1)[1]
            other_parts = " ".join(refinement_parts[1:])
            return f"{first_part} {other_parts}".strip()
        return ""
