import json

from django.core.management.base import BaseCommand
from django.db import IntegrityError, transaction

from subscriptions.models import CiNiiKeywords


class Command(BaseCommand):
    """
    JSONファイルからCiNiiキーワードを登録するコマンド
    """

    help = "Create or update CiNii keywords from a JSON file."

    def add_arguments(self, parser):
        """
        コマンドライン引数を定義する
        """
        parser.add_argument(
            "json_file",
            nargs="?",
            type=str,
            default="data/cinii_keywords.json",
            help="Path to the JSON file containing CiNii keywords.",
        )

    @transaction.atomic
    def handle(self, *args, **options):
        """
        コマンドのメインロジック
        """
        json_file_path = options["json_file"]

        try:
            with open(json_file_path, "r", encoding="utf-8") as f:
                data = json.load(f)
        except FileNotFoundError:
            self.stderr.write(
                self.style.ERROR(f"File not found: {json_file_path}")
            )
            return
        except json.JSONDecodeError:
            self.stderr.write(
                self.style.ERROR(f"Invalid JSON format in {json_file_path}")
            )
            return

        self.stdout.write(
            self.style.SUCCESS(
                "Start updating CiNii keywords " f"from {json_file_path}..."
            )
        )

        keywords_data = data.get("cinii_keywords", [])

        for keyword_data in keywords_data:
            keyword_name = keyword_data.get("name")
            if not keyword_name:
                continue

            try:
                _, created = CiNiiKeywords.objects.update_or_create(
                    name=keyword_name,
                    defaults={
                        "description": keyword_data.get("description", "")
                    },
                )
                if created:
                    message = f"  Created CiNii Keyword: {keyword_name}"
                    self.stdout.write(self.style.SUCCESS(message))
                else:
                    message = f"  Updated CiNii Keyword: {keyword_name}"
                    self.stdout.write(message)
            except IntegrityError:
                message = (
                    f"  Error: Duplicate CiNii Keyword found: "
                    f"{keyword_name}"
                )
                self.stderr.write(self.style.ERROR(message))

        self.stdout.write(
            self.style.SUCCESS(
                "\nSuccessfully finished updating CiNii keywords."
            )
        )
