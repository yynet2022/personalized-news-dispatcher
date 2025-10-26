import json
from django.core.management.base import BaseCommand
from subscriptions.models import LargeCategory, UniversalKeywords, CurrentKeywords, RelatedKeywords
from django.db import transaction, IntegrityError

class Command(BaseCommand):
    """
    JSONファイルからカテゴリとキーワードを登録するコマンド
    """
    help = 'Create or update categories and keywords from a JSON file.'

    def add_arguments(self, parser):
        """
        コマンドライン引数を定義する
        """
        parser.add_argument('json_file', type=str, help='Path to the JSON file')

    def _update_keywords(self, large_cat, keyword_data_list, KeywordModel, keyword_type_name):
        for keyword_data in keyword_data_list:
            keyword_name = keyword_data.get('name')
            if not keyword_name:
                continue
            try:
                _, created = KeywordModel.objects.update_or_create(
                    large_category=large_cat,
                    name=keyword_name,
                    defaults={'description': keyword_data.get('description')}
                )
                if created:
                    self.stdout.write(self.style.SUCCESS(f'    Created {keyword_type_name}: {large_cat.name} -> {keyword_name}'))
                else:
                    self.stdout.write(f'    Updated {keyword_type_name}: {large_cat.name} -> {keyword_name}')
            except IntegrityError:
                self.stderr.write(self.style.ERROR(f'    Error: Duplicate {keyword_type_name} found for "{large_cat.name}": {keyword_name}'))

    @transaction.atomic
    def handle(self, *args, **options):
        """
        コマンドのメインロジック
        """
        json_file_path = options['json_file']

        try:
            with open(json_file_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
        except FileNotFoundError:
            self.stderr.write(self.style.ERROR(f'File not found: {json_file_path}'))
            return
        except json.JSONDecodeError:
            self.stderr.write(self.style.ERROR(f'Invalid JSON format in {json_file_path}'))
            return

        self.stdout.write(self.style.SUCCESS('Start updating categories...'))

        for category_data in data:
            large_cat_name = category_data.get('name')
            if not large_cat_name:
                continue

            # LargeCategory の登録
            large_cat, created = LargeCategory.objects.get_or_create(name=large_cat_name)
            if created:
                self.stdout.write(self.style.SUCCESS(f'  Created LargeCategory: {large_cat_name}'))
            else:
                self.stdout.write(f'  LargeCategory already exists: {large_cat_name}')

            self._update_keywords(large_cat, category_data.get('universal', []), UniversalKeywords, 'UniversalKeyword')
            self._update_keywords(large_cat, category_data.get('current', []), CurrentKeywords, 'CurrentKeyword')
            self._update_keywords(large_cat, category_data.get('related', []), RelatedKeywords, 'RelatedKeyword')

        self.stdout.write(self.style.SUCCESS('\nSuccessfully finished updating categories.'))
