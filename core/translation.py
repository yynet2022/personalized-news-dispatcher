from __future__ import annotations

import json
import logging
import re
from typing import cast

from django.conf import settings

logger = logging.getLogger(__name__)

# --- Optional AI library imports ---
try:
    # import google.generativeai as genai
    # https://ai.google.dev/gemini-api/docs/migrate?hl=ja
    from google import genai  # type: ignore[no-redef]

    GEMINI_IS_AVAILABLE = True
except ImportError:
    genai = None  # type: ignore[assignment]
    GEMINI_IS_AVAILABLE = False

try:
    import httpx
    import openai

    OPENAI_IS_AVAILABLE = True
except ImportError:
    httpx = None  # type: ignore[assignment]
    openai = None  # type: ignore[assignment]
    OPENAI_IS_AVAILABLE = False

try:
    import instructor
    from pydantic import BaseModel, Field

    INSTRUCTOR_IS_AVAILABLE = True
except ImportError:
    instructor = None  # type: ignore[assignment]
    BaseModel = object  # type: ignore[assignment,misc]

    def Field(*args, **kwargs):  # type: ignore[no-redef]
        return None

    INSTRUCTOR_IS_AVAILABLE = False
# --- End of optional imports ---


if INSTRUCTOR_IS_AVAILABLE:

    class TranslatedTitles(BaseModel):
        translated_titles: list[str] = Field(
            ...,
            description="List of titles translated into the target language.",
        )


def _clean_json_response(text: str) -> str:
    """
    Cleans the response text to extract valid JSON array.
    Removes Markdown code blocks and whitespace.
    """
    # Remove markdown code blocks if present
    match = re.search(r"```(?:json)?\s*(\[.*\])\s*```", text, re.DOTALL)
    if match:
        return match.group(1)
    # If no code blocks, look for the first '[' and last ']'
    match = re.search(r"(\[.*\])", text, re.DOTALL)
    if match:
        return match.group(1)
    return text


def translate_text_with_gemini(
    text: str, target_language: str = settings.DEFAULT_LANGUAGE
) -> str:
    """
    Translates text using Google Gemini API.

    Args:
        text: The text to translate.
        target_language: The language to translate the text into.
                         Defaults to system default language ("Japanese").

    Returns:
        The translated text, or the original text if translation fails,
        API key is not set, or the library is not installed.
    """
    if not GEMINI_IS_AVAILABLE:
        logger.warning(
            "google-generativeai is not installed."
            " Skipping Gemini translation."
        )
        return text

    api_key = settings.GEMINI_API_KEY
    if not api_key:
        logger.warning(
            "GEMINI_API_KEY is not set." " Skipping Gemini translation."
        )
        return text

    try:
        logger.info("Gemini translation start.")
        logger.debug(
            "Attempting to translate with Gemini model: "
            f"{settings.GEMINI_MODEL}"
        )
        # genai.configure(api_key=api_key)
        client = genai.Client(api_key=api_key)
        prompt = (
            f"Translate the following text into {target_language}."
            " If the text is HTML, translate only the visible text "
            "content while preserving all HTML tags and structure:\n\n"
            f"{text}"
        )

        logger.debug("Sending request to Gemini API...")
        # model = genai.GenerativeModel(settings.GEMINI_MODEL)
        # response = model.generate_content(
        #     prompt, generation_config={'temperature': 0.0})
        response = client.models.generate_content(
            model=settings.GEMINI_MODEL,
            contents=prompt,
            config=genai.types.GenerateContentConfig(temperature=0.0),
        )
        logger.debug("Successfully received response from Gemini API.")

        logger.info("Gemini translation end.")
        return response.text or text
    except Exception as e:
        logger.error(f"Gemini translation failed: {e}")
        return text


def translate_titles_with_gemini(
    titles: list[str], target_language: str = settings.DEFAULT_LANGUAGE
) -> list[str]:
    """
    Translates a list of titles using Google Gemini API.
    """
    if not GEMINI_IS_AVAILABLE:
        return titles

    api_key = settings.GEMINI_API_KEY
    if not api_key:
        return titles

    if not titles:
        return []

    try:
        client = genai.Client(api_key=api_key)
        titles_json = json.dumps(titles, ensure_ascii=False)

        # Use structured output if pydantic is available
        if INSTRUCTOR_IS_AVAILABLE:
            prompt = (
                f"Translate the following list of titles "
                f"into {target_language}. {titles_json}"
            )
            logger.debug(
                "Sending batch translation request "
                "to Gemini API (Structured)..."
            )

            response = client.models.generate_content(
                model=settings.GEMINI_MODEL,
                contents=prompt,
                config=genai.types.GenerateContentConfig(
                    temperature=0.0,
                    response_mime_type="application/json",
                    response_schema=TranslatedTitles,
                ),
            )

            # Try to get parsed object from response.parsed
            # (if supported by SDK)
            if hasattr(response, "parsed") and response.parsed:
                parsed_response = cast(TranslatedTitles, response.parsed)
                logger.debug(
                    "Success(Gemini/Struct): "
                    f"{parsed_response.translated_titles[:1]}..."
                )
                return parsed_response.translated_titles

            # Fallback to manual parsing of response.text
            res_text = response.text
            if res_text:
                try:
                    obj = TranslatedTitles.model_validate_json(res_text)
                    logger.debug(
                        "Success(Gemini/Struct/Text): "
                        f"{obj.translated_titles[:1]}..."
                    )
                    return obj.translated_titles
                except Exception as parse_e:
                    logger.warning(
                        "Failed to parse Gemini structured response: "
                        f"{parse_e}"
                    )
                    # If parsing failed, fall through to legacy method?
                    # Or return original?
                    # If structured output was requested but failed to parse,
                    # it's likely the model returned something weird.
                    # We can try legacy method logic if we assume the
                    # model ignores schema.
                    pass

        # Legacy method (Manual Prompting + Regex Cleaning)
        prompt_legacy = (
            f"Translate the following list of titles into {target_language}. "
            "Output ONLY a raw JSON list of strings "
            '(e.g. ["translated title 1", "translated title 2"]). '
            "Do not include any Markdown formatting or explanations. "
            "Maintain the original order and count.\n\n"
            f"{titles_json}"
        )

        logger.debug(
            "Sending batch translation request to Gemini API (Legacy)..."
        )
        response = client.models.generate_content(
            model=settings.GEMINI_MODEL,
            contents=prompt_legacy,
            config=genai.types.GenerateContentConfig(
                temperature=0.0,
                response_mime_type="application/json",
            ),
        )

        res_text = response.text
        if not res_text:
            logger.warning("Gemini returned empty response.")
            return titles

        cleaned_json = _clean_json_response(res_text)
        translated_titles = json.loads(cleaned_json)

        if isinstance(translated_titles, list) and len(
            translated_titles
        ) == len(titles):
            logger.debug(f'Success(Gemini): ["{translated_titles[0]}", ...]')
            return [str(t) for t in translated_titles]
        else:
            logger.warning(
                "Gemini returned invalid JSON structure or count mismatch."
            )
            return titles

    except Exception as e:
        logger.error(f"Gemini batch translation failed: {e}")
        return titles


def translate_text_with_openai(
    text: str, target_language: str = settings.DEFAULT_LANGUAGE
) -> str:
    """
    Translates text using OpenAI API.

    Args:
        text: The text to translate.
        target_language: The language to translate the text into.
                         Defaults to system default language ("Japanese").

    Returns:
        The translated text, or the original text if translation fails,
        API key is not set, or the library is not installed.
    """
    if not OPENAI_IS_AVAILABLE:
        logger.warning("openai is not installed. Skipping OpenAI translation.")
        return text

    api_key = settings.OPENAI_API_KEY
    if not api_key:
        logger.warning(
            "OPENAI_API_KEY is not set." " Skipping OpenAI translation."
        )
        return text

    system_content = (
        "You are a helpful assistant that translates text"
        f" into {target_language}. If the text is HTML, translate only the"
        " visible text content while preserving all HTML tags and structure."
        " Do not use code blocks in your response."
    )
    try:
        logger.info("OpenAI translation start.")
        logger.debug(
            "Attempting to translate with OpenAI model: "
            f"{settings.OPENAI_MODEL}"
        )

        # SSL検証をsettings.pyの値に基づいて設定
        http_client = httpx.Client(verify=settings.OPENAI_SSL_VERIFY)

        # クライアントの初期化
        client = openai.OpenAI(
            api_key=api_key,
            base_url=settings.OPENAI_API_BASE_URL,
            http_client=http_client,
        )

        logger.debug("Sending request to OpenAI API...")
        response = client.chat.completions.create(
            model=settings.OPENAI_MODEL,
            messages=[
                {"role": "system", "content": system_content},
                {"role": "user", "content": text},
            ],
            temperature=0.0,
        )
        logger.debug("Successfully received response from OpenAI API.")

        logger.info("OpenAI translation end.")
        return response.choices[0].message.content or text
    except Exception as e:
        logger.error(f"OpenAI translation failed: {e}")
        return text


def translate_titles_with_openai(
    titles: list[str], target_language: str = settings.DEFAULT_LANGUAGE
) -> list[str]:
    """
    Translates a list of titles using OpenAI API.
    """
    if not OPENAI_IS_AVAILABLE:
        return titles

    api_key = settings.OPENAI_API_KEY
    if not api_key:
        return titles

    if not titles:
        return []

    try:
        http_client = httpx.Client(verify=settings.OPENAI_SSL_VERIFY)

        # Use instructor if available
        # INSTRUCTOR_IS_AVAILABLE = False
        if INSTRUCTOR_IS_AVAILABLE:
            logger.debug("Using instructor for OpenAI translation.")
            instructor_client = instructor.from_openai(
                openai.OpenAI(
                    api_key=api_key,
                    base_url=settings.OPENAI_API_BASE_URL,
                    http_client=http_client,
                )
            )

            system_prompt = (
                "You are a helpful assistant that translates a list of "
                f"titles into {target_language}."
            )

            logger.debug(
                "Sending batch translation request to OpenAI API "
                "(Instructor)..."
            )

            resp = instructor_client.chat.completions.create(
                model=settings.OPENAI_MODEL,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {
                        "role": "user",
                        "content": (
                            "Translate the following list of titles into "
                            f"{target_language}. "
                            f"{json.dumps(titles, ensure_ascii=False)}"
                        ),
                    },
                ],
                response_model=TranslatedTitles,
                temperature=0.0,
            )

            logger.debug(
                f"Success(OpenAI/Instructor): {resp.translated_titles[:1]}..."
            )
            return resp.translated_titles

        # Legacy method
        client = openai.OpenAI(
            api_key=api_key,
            base_url=settings.OPENAI_API_BASE_URL,
            http_client=http_client,
        )

        system_content = (
            "You are a helpful assistant that translates a list of titles "
            f"into {target_language}. Output ONLY a raw JSON list of strings "
            '(e.g. ["translated 1", "translated 2"]). '
            "Do not use Markdown code blocks. "
            "Maintain the original order and count."
        )

        titles_json = json.dumps(titles, ensure_ascii=False)

        logger.debug(
            "Sending batch translation request to OpenAI API (Legacy)..."
        )
        response = client.chat.completions.create(
            model=settings.OPENAI_MODEL,
            messages=[
                {"role": "system", "content": system_content},
                {"role": "user", "content": titles_json},
            ],
            temperature=0.0,
            response_format={"type": "json_object"},
        )

        res_content = response.choices[0].message.content
        if not res_content:
            logger.warning("OpenAI returned empty response.")
            return titles

        cleaned_json = _clean_json_response(res_content)
        translated_titles = json.loads(cleaned_json)

        if isinstance(translated_titles, list) and len(
            translated_titles
        ) == len(titles):
            logger.debug(f'Success(OpenAI): ["{translated_titles[0]}", ...]')
            return [str(t) for t in translated_titles]
        else:
            logger.warning(
                "OpenAI returned invalid JSON structure or count mismatch."
            )
            return titles

    except Exception as e:
        logger.error(f"OpenAI batch translation failed: {e}")
        return titles


def translate_content(
    text: str, target_language: str = settings.DEFAULT_LANGUAGE
) -> str:
    """
    Translates content using available AI services (Gemini or OpenAI).
    Prioritizes Gemini if its API key is set and the library is installed,
    otherwise tries OpenAI.

    Args:
        text: The text content (can be plain text or HTML) to translate.
        target_language: The language to translate the text into.
                         Defaults to system default language ("Japanese").

    Returns:
        The translated text, or the original text
        if no translation service is available or translation fails.
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
            logger.info(
                "No AI translation libraries are installed."
                " Skipping translation."
            )
        else:
            logger.info(
                "No AI translation API key found." " Skipping translation."
            )
        return text


def translate_titles_batch(
    titles: list[str], target_language: str = settings.DEFAULT_LANGUAGE
) -> list[str]:
    """
    Translates a list of titles using available AI services (Gemini or OpenAI).

    Args:
        titles: List of titles to translate.
        target_language: Target language.

    Returns:
        List of translated titles. Returns original list on failure.
    """
    use_gemini = GEMINI_IS_AVAILABLE and settings.GEMINI_API_KEY
    use_openai = OPENAI_IS_AVAILABLE and settings.OPENAI_API_KEY

    if use_gemini:
        return translate_titles_with_gemini(titles, target_language)
    elif use_openai:
        return translate_titles_with_openai(titles, target_language)
    else:
        return titles
