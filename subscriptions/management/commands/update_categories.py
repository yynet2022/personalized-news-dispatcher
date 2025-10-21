import json
from django.core.management.base import BaseCommand
from subscriptions.models import LargeCategory, MediumCategory, RelatedKeywords

class Command(BaseCommand):
    """
    JSONファイルから大分類・中分類を登録するコマンド
    """
    help = 'Create LargeCategory and MediumCategory from a JSON file.'

    def add_arguments(self, parser):
        """
        コマンドライン引数を定義する
        """
        parser.add_argument('json_file', type=str, help='Path to the JSON file')

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

        # --- Category の登録 ---
        categories_data = data.get('Category', {})

        for large_cat_name, medium_categories in categories_data.items():
            # LargeCategory の登録
            large_cat, created = LargeCategory.objects.get_or_create(name=large_cat_name)
            if created:
                self.stdout.write(self.style.SUCCESS(f'  Created LargeCategory: {large_cat_name}'))
            else:
                self.stdout.write(f'  LargeCategory already exists: {large_cat_name}')

            for medium_cat_name, related_keywords in medium_categories.items():
                # MediumCategory の登録
                medium_cat, created = MediumCategory.objects.get_or_create(
                    large_category=large_cat,
                    name=medium_cat_name
                )
                if created:
                    self.stdout.write(self.style.SUCCESS(f'    Created MediumCategory: {large_cat_name} -> {medium_cat_name}'))
                else:
                    self.stdout.write(f'    MediumCategory already exists: {large_cat_name} -> {medium_cat_name}')

                # RelatedKeywords の登録
                for keyword_name in related_keywords:
                    related_keyword, created = RelatedKeywords.objects.get_or_create(
                        medium_category=medium_cat,
                        name=keyword_name
                    )
                    if created:
                        self.stdout.write(self.style.SUCCESS(f'      Created RelatedKeyword: {medium_cat_name} -> {keyword_name}'))
                    else:
                        self.stdout.write(f'      RelatedKeyword already exists: {medium_cat_name} -> {keyword_name}')

        self.stdout.write(self.style.SUCCESS('\nSuccessfully finished updating categories.'))
