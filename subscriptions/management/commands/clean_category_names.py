from django.core.management.base import BaseCommand
from subscriptions.models import LargeCategory, MediumCategory, RelatedKeywords

class Command(BaseCommand):
    help = 'Cleans and normalizes existing category names according to new validation rules.'

    def handle(self, *args, **options):
        self.stdout.write('Starting to clean and normalize category names...')

        # LargeCategory のクリーンアップ
        self.stdout.write('\nProcessing LargeCategory names...')
        for obj in LargeCategory.objects.all():
            old_name = obj.name
            try:
                # save() メソッド内で正規化とバリデーションが実行される
                obj.save()
                if old_name != obj.name:
                    self.stdout.write(self.style.SUCCESS(f'  Normalized LargeCategory: "{old_name}" -> "{obj.name}"'))
                else:
                    self.stdout.write(f'  LargeCategory "{obj.name}" is already clean.')
            except Exception as e:
                self.stderr.write(self.style.ERROR(f'  Error cleaning LargeCategory "{old_name}": {e}'))

        # MediumCategory のクリーンアップ
        self.stdout.write('\nProcessing MediumCategory names...')
        for obj in MediumCategory.objects.all():
            old_name = obj.name
            try:
                obj.save()
                if old_name != obj.name:
                    self.stdout.write(self.style.SUCCESS(f'  Normalized MediumCategory: "{old_name}" -> "{obj.name}"'))
                else:
                    self.stdout.write(f'  MediumCategory "{obj.name}" is already clean.')
            except Exception as e:
                self.stderr.write(self.style.ERROR(f'  Error cleaning MediumCategory "{old_name}": {e}'))

        # RelatedKeywords のクリーンアップ
        self.stdout.write('\nProcessing RelatedKeywords names...')
        for obj in RelatedKeywords.objects.all():
            old_name = obj.name
            try:
                obj.save()
                if old_name != obj.name:
                    self.stdout.write(self.style.SUCCESS(f'  Normalized RelatedKeyword: "{old_name}" -> "{obj.name}"'))
                else:
                    self.stdout.write(f'  RelatedKeyword "{obj.name}" is already clean.')
            except Exception as e:
                self.stderr.write(self.style.ERROR(f'  Error cleaning RelatedKeyword "{old_name}": {e}'))

        self.stdout.write(self.style.SUCCESS('\nSuccessfully finished cleaning and normalizing category names.'))
