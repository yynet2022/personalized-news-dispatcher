from django import forms
from .models import (
    QuerySet, UniversalKeywords, CurrentKeywords, RelatedKeywords)


class QuerySetForm(forms.ModelForm):
    class Meta:
        model = QuerySet
        fields = ['name', 'auto_send', 'large_category', 'country', 'after_days',
                  'max_articles', 'universal_keywords',
                  'current_keywords', 'related_keywords',
                  'additional_or_keywords', 'refinement_keywords']
        widgets = {
            'universal_keywords': forms.CheckboxSelectMultiple,
            'current_keywords': forms.CheckboxSelectMultiple,
            'related_keywords': forms.CheckboxSelectMultiple,
        }

    def __init__(self, *args, **kwargs):
        _ = kwargs.pop('user', None)
        super().__init__(*args, **kwargs)

        f_ = self.fields
        f_['after_days'].widget.attrs.update({'min': 0})
        f_['max_articles'].widget.attrs.update({'min': 1})

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
                          large_category_id=large_category_id).order_by('name')
                    f_['current_keywords'].queryset = \
                        CurrentKeywords.objects.filter(
                          large_category_id=large_category_id).order_by('name')
                    f_['related_keywords'].queryset = \
                        RelatedKeywords.objects.filter(
                          large_category_id=large_category_id).order_by('name')
                except (ValueError, TypeError):
                    pass
        elif self.instance.pk and self.instance.large_category_id:
            f_['universal_keywords'].queryset = \
                self.instance.\
                large_category.universalkeywords_set.order_by('name')
            f_['current_keywords'].queryset = \
                self.instance.\
                large_category.currentkeywords_set.order_by('name')
            f_['related_keywords'].queryset = \
                self.instance.\
                large_category.relatedkeywords_set.order_by('name')
