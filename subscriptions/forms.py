from django import forms
from .models import (
    QuerySet, UniversalKeywords, CurrentKeywords, RelatedKeywords,
    CiNiiKeywords)


class QuerySetForm(forms.ModelForm):
    class Meta:
        model = QuerySet
        fields = [
            'name', 'source', 'auto_send',
            # Google News fields
            'large_category', 'country',
            'universal_keywords', 'current_keywords', 'related_keywords',
            # CiNii fields
            'cinii_keywords',
            # Common fields
            'additional_or_keywords', 'refinement_keywords',
            'after_days', 'max_articles',
        ]
        widgets = {
            'source': forms.RadioSelect,
            'universal_keywords': forms.CheckboxSelectMultiple,
            'current_keywords': forms.CheckboxSelectMultiple,
            'related_keywords': forms.CheckboxSelectMultiple,
            'cinii_keywords': forms.CheckboxSelectMultiple,
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        f_ = self.fields

        # --- Google News field setup ---
        f_['universal_keywords'].label_from_instance = lambda x: x.name
        f_['current_keywords'].label_from_instance = lambda x: x.name
        f_['related_keywords'].label_from_instance = lambda x: x.name
        f_['universal_keywords'].queryset = UniversalKeywords.objects.none()
        f_['current_keywords'].queryset = CurrentKeywords.objects.none()
        f_['related_keywords'].queryset = RelatedKeywords.objects.none()

        if 'large_category' in self.data:
            large_category_id = self.data.get('large_category')
            if large_category_id:
                try:
                    f_['universal_keywords'].queryset = \
                        UniversalKeywords.objects.filter(
                            large_category_id=large_category_id
                        ).order_by('name')
                    f_['current_keywords'].queryset = \
                        CurrentKeywords.objects.filter(
                            large_category_id=large_category_id
                        ).order_by('name')
                    f_['related_keywords'].queryset = \
                        RelatedKeywords.objects.filter(
                            large_category_id=large_category_id
                        ).order_by('name')
                except (ValueError, TypeError):
                    pass
        elif self.instance.pk and self.instance.large_category_id:
            f_['universal_keywords'].queryset = \
                self.instance.large_category.universalkeywords_set.order_by(
                    'name')
            f_['current_keywords'].queryset = \
                self.instance.large_category.currentkeywords_set.order_by(
                    'name')
            f_['related_keywords'].queryset = \
                self.instance.large_category.relatedkeywords_set.order_by(
                    'name')

        # --- CiNii field setup ---
        f_['cinii_keywords'].queryset = CiNiiKeywords.objects.order_by('name')
        f_['cinii_keywords'].label_from_instance = lambda obj: obj.name

        # --- Common field setup ---
        f_['after_days'].widget.attrs.update({'min': 0})
        f_['max_articles'].widget.attrs.update({'min': 1})

        # --- Disable source on update ---
        if self.instance and not self.instance._state.adding:
            self.fields['source'].disabled = True

    def clean(self):
        cleaned_data = super().clean()
        source = cleaned_data.get('source')

        if source == QuerySet.SOURCE_GOOGLE_NEWS:
            # CiNii関連のフィールドをクリア
            if 'cinii_keywords' in cleaned_data:
                cleaned_data['cinii_keywords'] = CiNiiKeywords.objects.none()
        elif source == QuerySet.SOURCE_CINII:
            # Google News関連のフィールドをクリア
            cleaned_data['large_category'] = None
            cleaned_data['country'] = ''
            if 'universal_keywords' in cleaned_data:
                cleaned_data['universal_keywords'] = \
                    UniversalKeywords.objects.none()
            if 'current_keywords' in cleaned_data:
                cleaned_data['current_keywords'] = \
                    CurrentKeywords.objects.none()
            if 'related_keywords' in cleaned_data:
                cleaned_data['related_keywords'] = \
                    RelatedKeywords.objects.none()

        return cleaned_data

    def save(self, commit=True):
        instance = super().save(commit=False)

        source = self.cleaned_data.get('source')
        if source == QuerySet.SOURCE_GOOGLE_NEWS:
            instance.query_str = self._build_google_news_query()
        elif source == QuerySet.SOURCE_CINII:
            instance.query_str = self._build_cinii_query()

        if commit:
            instance.save()
            self.save_m2m()

        return instance

    def _build_google_news_query(self):
        parts = []
        if self.cleaned_data.get('large_category'):
            parts.append(self.cleaned_data.get('large_category').name)

        for field in ['universal_keywords',
                      'current_keywords', 'related_keywords']:
            for keyword in self.cleaned_data.get(field, []):
                parts.append(keyword.name)

        additional = self.cleaned_data.get('additional_or_keywords', '')
        if additional:
            parts.extend(additional.split())

        or_part = " OR ".join(f'{p}' for p in parts if p)
        if len(parts) > 1:
            or_part = f"({or_part})"

        refinement = self.cleaned_data.get('refinement_keywords', '')
        return f"{or_part} {refinement}".strip()

    def _build_cinii_query(self):
        parts = []
        for keyword in self.cleaned_data.get('cinii_keywords', []):
            parts.append(f'{keyword.name}')

        additional = self.cleaned_data.get('additional_or_keywords', '')
        if additional:
            parts.extend(f'{p}' for p in additional.split() if p)

        or_part = " OR ".join(parts)
        if len(parts) > 1:
            or_part = f"({or_part})"

        refinement = self.cleaned_data.get('refinement_keywords', '')
        return f"{or_part} {refinement}".strip()
