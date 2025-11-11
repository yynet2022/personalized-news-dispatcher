import google.generativeai as genai
import openai
from django.conf import settings
import logging

logger = logging.getLogger(__name__)

def translate_text_with_gemini(text: str, target_language: str = "Japanese") -> str:
    """
    Translates text using Google Gemini API.

    Args:
        text: The text to translate.
        target_language: The language to translate the text into. Defaults to "Japanese".

    Returns:
        The translated text, or the original text if translation fails or API key is not set.
    """
    api_key = settings.GEMINI_API_KEY
    if not api_key:
        logger.warning("GEMINI_API_KEY is not set. Skipping Gemini translation.")
        return text

    try:
        genai.configure(api_key=api_key)
        model = genai.GenerativeModel(settings.GEMINI_MODEL)
        prompt = f"Translate the following text into {target_language}. If the text is HTML, translate only the visible text content while preserving all HTML tags and structure:\n\n{text}"
        response = model.generate_content(prompt)
        return response.text
    except Exception as e:
        logger.error(f"Gemini translation failed: {e}")
        return text

def translate_text_with_openai(text: str, target_language: str = "Japanese") -> str:
    """
    Translates text using OpenAI API.

    Args:
        text: The text to translate.
        target_language: The language to translate the text into. Defaults to "Japanese".

    Returns:
        The translated text, or the original text if translation fails or API key is not set.
    """
    api_key = settings.OPENAI_API_KEY
    if not api_key:
        logger.warning("OPENAI_API_KEY is not set. Skipping OpenAI translation.")
        return text

    try:
        # クライアントの初期化
        client = openai.OpenAI(
            api_key=api_key,
            base_url=settings.OPENAI_API_BASE_URL # Noneの場合はデフォルトのURLが使われる
        )
        response = client.chat.completions.create(
            model=settings.OPENAI_MODEL,
            messages=[
                {"role": "system", "content": f"You are a helpful assistant that translates text into {target_language}. If the text is HTML, translate only the visible text content while preserving all HTML tags and structure."},
                {"role": "user", "content": text}
            ]
        )
        return response.choices[0].message.content
    except Exception as e:
        logger.error(f"OpenAI translation failed: {e}")
        return text

def translate_content(text: str, target_language: str = "Japanese") -> str:
    """
    Translates content using available AI services (Gemini or OpenAI).
    Prioritizes Gemini if its API key is set, otherwise tries OpenAI.

    Args:
        text: The text content (can be plain text or HTML) to translate.
        target_language: The language to translate the text into. Defaults to "Japanese".

    Returns:
        The translated text, or the original text if no translation service is available or translation fails.
    """
    if settings.GEMINI_API_KEY:
        return translate_text_with_gemini(text, target_language)
    elif settings.OPENAI_API_KEY:
        return translate_text_with_openai(text, target_language)
    else:
        logger.info("No AI translation API key found. Skipping translation.")
        return text
