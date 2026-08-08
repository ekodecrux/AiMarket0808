import os
import json
import logging
from groq import AsyncGroq
from emergentintegrations.llm.chat import LlmChat, UserMessage

logger = logging.getLogger(__name__)

EMERGENT_LLM_KEY = os.environ.get("EMERGENT_LLM_KEY")
GROQ_API_KEY = os.environ.get("GROQ_API_KEY")
GROQ_MODEL = os.environ.get("GROQ_MODEL", "llama-3.3-70b-versatile")
IMAGE_MODEL = "gemini-3.1-flash-image-preview"

_groq = AsyncGroq(api_key=GROQ_API_KEY) if GROQ_API_KEY else None


async def generate_text(session_id: str, system_message: str, prompt: str) -> str:
    if _groq is None:
        raise RuntimeError("GROQ_API_KEY is not configured; add it in the server environment before using AI generation.")
    resp = await _groq.chat.completions.create(
        model=GROQ_MODEL,
        messages=[
            {"role": "system", "content": system_message},
            {"role": "user", "content": prompt},
        ],
        temperature=0.8,
    )
    return resp.choices[0].message.content or ""


async def generate_json(session_id: str, system_message: str, prompt: str) -> dict:
    system = system_message + (
        "\n\nRespond with ONLY a single valid JSON object. No markdown or commentary."
    )
    try:
        resp = await _groq.chat.completions.create(
            model=GROQ_MODEL,
            messages=[
                {"role": "system", "content": system},
                {"role": "user", "content": prompt},
            ],
            temperature=0.7,
            response_format={"type": "json_object"},
        )
        raw = resp.choices[0].message.content or "{}"
    except Exception as e:
        logger.error(f"Groq json call failed: {e}")
        raw = await generate_text(session_id, system, prompt)
    return _parse_json(raw)


def _parse_json(raw: str) -> dict:
    text = raw.strip()
    if text.startswith("```"):
        text = text.split("```", 2)[1] if "```" in text else text
        if text.startswith("json"):
            text = text[4:]
        text = text.strip("` \n")
    start = text.find("{")
    end = text.rfind("}")
    if start != -1 and end != -1:
        text = text[start : end + 1]
    try:
        return json.loads(text)
    except Exception as e:
        logger.error(f"JSON parse failed: {e}")
        return {"_raw": raw, "_error": "Could not parse AI response as JSON"}


async def generate_image(session_id: str, prompt: str) -> str:
    """Returns a data URL (base64) for the generated image via Gemini Nano Banana."""
    chat = LlmChat(
        api_key=EMERGENT_LLM_KEY,
        session_id=session_id,
        system_message="You are an expert marketing creative image generator.",
    ).with_model("gemini", IMAGE_MODEL).with_params(modalities=["image", "text"])

    _, images = await chat.send_message_multimodal_response(UserMessage(text=prompt))
    if images:
        img = images[0]
        return f"data:{img['mime_type']};base64,{img['data']}"
    return ""
