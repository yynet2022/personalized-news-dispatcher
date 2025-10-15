import json
from django.core.management.base import BaseCommand
from subscriptions.models import LargeCategory, MediumCategory

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

        # --- LargeCategory の登録 ---
        large_categories = data.get('LargeCategory', [])
        self.stdout.write('Processing LargeCategory...')
        for name in large_categories:
            obj, created = LargeCategory.objects.get_or_create(name=name)
            if created:
                self.stdout.write(self.style.SUCCESS(f'  Created LargeCategory: {name}'))
            else:
                self.stdout.write(f'  LargeCategory already exists: {name}')

        # --- MediumCategory の登録 ---
        medium_categories_data = data.get('MediumCategory', {})
        self.stdout.write('\nProcessing MediumCategory...')
        for large_cat_name, medium_cat_names in medium_categories_data.items():
            try:
                large_cat = LargeCategory.objects.get(name=large_cat_name)
                for name in medium_cat_names:
                    obj, created = MediumCategory.objects.get_or_create(
                        large_category=large_cat,
                        name=name
                    )
                    if created:
                        self.stdout.write(self.style.SUCCESS(f'  Created MediumCategory: {large_cat_name} -> {name}'))
                    else:
                        self.stdout.write(f'  MediumCategory already exists: {large_cat_name} -> {name}')
            except LargeCategory.DoesNotExist:
                self.stderr.write(self.style.WARNING(f'  LargeCategory not found, skipping: {large_cat_name}'))

        self.stdout.write(self.style.SUCCESS('\nSuccessfully finished updating categories.'))
