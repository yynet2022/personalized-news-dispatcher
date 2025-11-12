from django.conf import settings
import logging

logger = logging.getLogger(__name__)

# --- Optional AI library imports ---
try:
    import google.generativeai as genai
    GEMINI_IS_AVAILABLE = True
except ImportError:
    GEMINI_IS_AVAILABLE = False
    genai = None

try:
    import openai
    import httpx
    OPENAI_IS_AVAILABLE = True
except ImportError:
    OPENAI_IS_AVAILABLE = False
    openai = None
    httpx = None
# --- End of optional imports ---



def translate_text_with_gemini(text: str, target_language: str = "Japanese") -> str:
    """
    Translates text using Google Gemini API.

    Args:
        text: The text to translate.
        target_language: The language to translate the text into. Defaults to "Japanese".

    Returns:
        The translated text, or the original text if translation fails, API key is not set, or the library is not installed.
    """
    if not GEMINI_IS_AVAILABLE:
        logger.warning("google-generativeai is not installed. Skipping Gemini translation.")
        return text
        
    api_key = settings.GEMINI_API_KEY
    if not api_key:
        logger.warning("GEMINI_API_KEY is not set. Skipping Gemini translation.")
        return text

    try:
        logger.debug(f"Attempting to translate with Gemini model: {settings.GEMINI_MODEL}")
        genai.configure(api_key=api_key)
        model = genai.GenerativeModel(settings.GEMINI_MODEL)
        prompt = f"Translate the following text into {target_language}. If the text is HTML, translate only the visible text content while preserving all HTML tags and structure:\n\n{text}"
        
        logger.debug("Sending request to Gemini API...")
        response = model.generate_content(prompt)
        logger.debug("Successfully received response from Gemini API.")
        
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
        The translated text, or the original text if translation fails, API key is not set, or the library is not installed.
    """
    if not OPENAI_IS_AVAILABLE:
        logger.warning("openai is not installed. Skipping OpenAI translation.")
        return text

    api_key = settings.OPENAI_API_KEY
    if not api_key:
        logger.warning("OPENAI_API_KEY is not set. Skipping OpenAI translation.")
        return text

    try:
        logger.debug(f"Attempting to translate with OpenAI model: {settings.OPENAI_MODEL}")
        
        # SSL検証をsettings.pyの値に基づいて設定
        http_client = httpx.Client(verify=settings.OPENAI_SSL_VERIFY)
        
        # クライアントの初期化
        client = openai.OpenAI(
            api_key=api_key,
            base_url=settings.OPENAI_API_BASE_URL, # Noneの場合はデフォルトのURLが使われる
            http_client=http_client
        )

        logger.debug("Sending request to OpenAI API...")
        response = client.chat.completions.create(
            model=settings.OPENAI_MODEL,
            messages=[
                {"role": "system", "content": f"You are a helpful assistant that translates text into {target_language}. If the text is HTML, translate only the visible text content while preserving all HTML tags and structure."},
                {"role": "user", "content": text}
            ]
        )
        logger.debug("Successfully received response from OpenAI API.")

        return response.choices[0].message.content
    except Exception as e:
        logger.error(f"OpenAI translation failed: {e}")
        return text

def translate_content(text: str, target_language: str = "Japanese") -> str:
    """
    Translates content using available AI services (Gemini or OpenAI).
    Prioritizes Gemini if its API key is set and the library is installed, otherwise tries OpenAI.

    Args:
        text: The text content (can be plain text or HTML) to translate.
        target_language: The language to translate the text into. Defaults to "Japanese".

    Returns:
        The translated text, or the original text if no translation service is available or translation fails.
    """
    use_gemini = GEMINI_IS_AVAILABLE and settings.GEMINI_API_KEY
    use_openai = OPENAI_IS_AVAILABLE and settings.OPENAI_API_KEY

    if use_gemini:
        logger.debug("Gemini is selected as the translation provider.")
        return translate_text_with_gemini(text, target_language)
    elif use_openai:
        logger.debug("OpenAI is selected as the translation provider.")
        return translate_text_with_openai(text, target_language)
    else:
        if not (GEMINI_IS_AVAILABLE or OPENAI_IS_AVAILABLE):
            logger.info("No AI translation libraries are installed. Skipping translation.")
        else:
            logger.info("No AI translation API key found. Skipping translation.")
        return text
