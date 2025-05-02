import math
import re
import string
import unicodedata

import pandas as pd
from fastapi.responses import Response

from app.core.constants import (
    COLLOQUIAL_NUMBERS,
    RECOMMENDATION_PATTERNS,
    TOKEN_SYNONYMS,
)


def text_normalizer(texto: str) -> str:
    texto = texto.lower()
    texto = texto.translate(str.maketrans("", "", string.punctuation))
    texto = "".join(
        c
        for c in unicodedata.normalize("NFD", texto)
        if unicodedata.category(c) != "Mn"
    )
    return texto.strip()


def clean_token(token: str) -> str:
    """Elimina puntuación y acentos de un token individual."""
    token = token.translate(str.maketrans("", "", string.punctuation))
    token = "".join(
        c
        for c in unicodedata.normalize("NFD", token)
        if unicodedata.category(c) != "Mn"
    )
    return token.lower().strip()


def make_twilio_response(message: str) -> Response:
    print(f"📤 Enviando respuesta Twilio:\n{message}\n")
    response_xml = f"""
    <Response>
        <Message>{message}</Message>
    </Response>
    """
    return Response(content=response_xml.strip(), media_type="application/xml")


def fallback_with_repeat(last_prompt: str) -> str:
    return "❌ Disculpa, no entendí tu mensaje. ¿Podrías repetirlo?\n\n" + last_prompt


def safe_get(value, fallback="No disponible"):
    if pd.isna(value) or (isinstance(value, float) and math.isnan(value)):
        return fallback
    return value


def normalize_token(token: str) -> str:
    """
    Limpia y normaliza un token según sinónimos definidos en TOKEN_SYNONYMS.
    Ejemplos: 'blutut' → 'bluetooth', 'car play' → 'car_play'
    """
    token = token.strip().lower()
    token = re.sub(r"[^a-z0-9]", "", token)
    return TOKEN_SYNONYMS.get(token, token)


def extract_price_from_text(text: str) -> int | None:
    text = text.lower()

    for phrase, value in COLLOQUIAL_NUMBERS.items():
        if phrase in text:
            print(f"💬 Frase coloquial detectada: {phrase} = {value}")
            return value

    match = re.search(r"(\d+(?:[.,]?\d{0,3})?)\s*(mil|k|m)?", text)
    if match:
        num_str = match.group(1).replace(",", "").replace(".", "")
        suffix = match.group(2)

        try:
            value = int(num_str)
            if suffix in ["mil", "k"]:
                value *= 1000
            elif suffix == "m":
                value *= 1_000_000
            print(f"🔢 Valor numérico extraído: {value}")
            return value
        except ValueError:
            return None

    print("⚠️ No se detectó precio")
    return None


def user_is_asking_for_recommendation(text: str) -> bool:
    return any(k in text.lower() for k in RECOMMENDATION_PATTERNS)
