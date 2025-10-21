from django import forms
from .models import QuerySet, MediumCategory, CustomKeywords, RelatedKeywords


class QuerySetForm(forms.ModelForm):
    class Meta:
        model = QuerySet
        fields = ['name', 'large_category', 'medium_categories',
                  'custom_keywords', 'related_keywords']
        widgets = {
            'medium_categories': forms.CheckboxSelectMultiple,
            'custom_keywords': forms.CheckboxSelectMultiple,
            'related_keywords': forms.CheckboxSelectMultiple,
        }

    def __init__(self, *args, **kwargs):
        user = kwargs.pop('user', None)
        super().__init__(*args, **kwargs)

        self.fields['medium_categories'].label_from_instance = lambda obj: obj.name

        if user:
            self.fields['custom_keywords'].queryset = \
                CustomKeywords.objects.filter(user=user)

        self.fields['medium_categories'].queryset = \
            MediumCategory.objects.none()
        self.fields['related_keywords'].queryset = \
            RelatedKeywords.objects.none()

        if 'large_category' in self.data:
            large_category_id = self.data.get('large_category')
            if large_category_id:
                try:
                    self.fields['medium_categories'].queryset = \
                        MediumCategory.objects.filter(
                          large_category_id=large_category_id).order_by('name')
                    # medium_categories が選択されている場合、related_keywords をフィルタリング
                    selected_medium_categories = self.data.getlist('medium_categories')
                    if selected_medium_categories:
                        self.fields['related_keywords'].queryset = \
                            RelatedKeywords.objects.filter(
                                medium_category__id__in=selected_medium_categories).order_by('name')
                except (ValueError, TypeError):
                    pass
        # 既存インスタンスがあり、かつ、large_category_id が NULL でないことを確認
        elif self.instance.pk and self.instance.large_category_id:
            self.fields['medium_categories'].queryset = \
               self.instance.large_category.mediumcategory_set.order_by('name')
            # 既存インスタンスの medium_categories に基づいて related_keywords をフィルタリング
            if self.instance.medium_categories.exists():
                self.fields['related_keywords'].queryset = \
                    RelatedKeywords.objects.filter(
                        medium_category__in=self.instance.medium_categories.all()).order_by('name')
