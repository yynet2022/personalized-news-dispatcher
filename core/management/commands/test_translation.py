# core/management/commands/test_translation.py

from django.core.management.base import BaseCommand, CommandParser
from core.translation import translate_content
import logging

class Command(BaseCommand):
    """
    実際にAI翻訳サービスに接続して、翻訳機能をテストするカスタム管理コマンド。
    """
    help = 'Test the translation functionality by connecting to the actual AI service.'

    def add_arguments(self, parser: CommandParser) -> None:
        """
        コマンドライン引数を定義します。
        """
        parser.add_argument(
            'text_to_translate',
            type=str,
            help='The text to be translated.'
        )
        parser.add_argument(
            '--lang',
            type=str,
            default='Japanese',
            help='The target language for translation. (e.g., "English", "Korean")'
        )
        parser.add_argument(
            '--loglevel',
            type=str,
            choices=['DEBUG', 'INFO', 'WARNING', 'ERROR', 'CRITICAL'],
            default='INFO',
            help='Set the logging level. (e.g., DEBUG, INFO, WARNING)'
        )

    def handle(self, *args, **options) -> None:
        """
        コマンドが実行された際のメインロジック。
        """
        # --- ロギングレベルを設定 ---
        log_level = options['loglevel'].upper()
        # ルートロガーのレベルを設定することで、translation.py内のロガーにも影響します
        logging.getLogger().setLevel(log_level)
        # --- ここまでロギング設定 ---

        text_to_translate = options['text_to_translate']
        target_language = options['lang']

        self.stdout.write(self.style.NOTICE(f"Original text: '{text_to_translate}'"))
        self.stdout.write(self.style.NOTICE(f"Target language: {target_language}"))
        self.stdout.write(self.style.NOTICE(f"Logging level set to: {log_level}"))
        self.stdout.write("---")
        self.stdout.write("Attempting to translate...")

        try:
            translated_text = translate_content(text_to_translate, target_language)

            self.stdout.write("---")
            if translated_text == text_to_translate:
                self.stdout.write(self.style.WARNING(
                    "Translation result is the same as the original text. "
                    "This might be due to a failed translation or the text not needing translation."
                ))
            else:
                self.stdout.write(self.style.SUCCESS("Translation successful!"))

            self.stdout.write(self.style.SUCCESS(f"Translated text: '{translated_text}'"))

        except Exception as e:
            self.stderr.write(self.style.ERROR(f"An unexpected error occurred: {e}"))
            logging.error("Command failed with an exception", exc_info=True)
