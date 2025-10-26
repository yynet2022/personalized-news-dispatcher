from django import forms
from .models import QuerySet, UniversalKeywords, CurrentKeywords, RelatedKeywords


class QuerySetForm(forms.ModelForm):
    class Meta:
        model = QuerySet
        fields = ['name', 'large_category', 'universal_keywords',
                  'current_keywords', 'related_keywords',
                  'additional_or_keywords', 'refinement_keywords']
        widgets = {
            'universal_keywords': forms.CheckboxSelectMultiple,
            'current_keywords': forms.CheckboxSelectMultiple,
            'related_keywords': forms.CheckboxSelectMultiple,
        }

    def __init__(self, *args, **kwargs):
        user = kwargs.pop('user', None)
        super().__init__(*args, **kwargs)

        self.fields['universal_keywords'].label_from_instance = lambda obj: obj.name
        self.fields['current_keywords'].label_from_instance = lambda obj: obj.name
        self.fields['related_keywords'].label_from_instance = lambda obj: obj.name

        self.fields['universal_keywords'].queryset = UniversalKeywords.objects.none()
        self.fields['current_keywords'].queryset = CurrentKeywords.objects.none()
        self.fields['related_keywords'].queryset = RelatedKeywords.objects.none()

        if 'large_category' in self.data:
            large_category_id = self.data.get('large_category')
            if large_category_id:
                try:
                    self.fields['universal_keywords'].queryset = UniversalKeywords.objects.filter(
                        large_category_id=large_category_id).order_by('name')
                    self.fields['current_keywords'].queryset = CurrentKeywords.objects.filter(
                        large_category_id=large_category_id).order_by('name')
                    self.fields['related_keywords'].queryset = RelatedKeywords.objects.filter(
                        large_category_id=large_category_id).order_by('name')
                except (ValueError, TypeError):
                    pass
        elif self.instance.pk and self.instance.large_category_id:
            self.fields['universal_keywords'].queryset = self.instance.large_category.universalkeywords_set.order_by('name')
            self.fields['current_keywords'].queryset = self.instance.large_category.currentkeywords_set.order_by('name')
            self.fields['related_keywords'].queryset = self.instance.large_category.relatedkeywords_set.order_by('name')
