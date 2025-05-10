import math
import re
import string
import unicodedata

import pandas as pd
from fastapi.responses import Response


def text_normalizer(texto: str) -> str:
    texto = texto.lower()
    texto = texto.translate(str.maketrans("", "", string.punctuation))
    texto = "".join(
        c
        for c in unicodedata.normalize("NFD", texto)
        if unicodedata.category(c) != "Mn"
    )
    return texto.strip()


def make_twilio_response(message: str) -> Response:
    print(f"📤 Enviando respuesta Twilio:\n{message}\n")
    response_xml = f"""
    <Response>
        <Message>{message}</Message>
    </Response>
    """
    return Response(content=response_xml.strip(), media_type="application/xml")


def safe_get(value, fallback="No disponible"):
    if pd.isna(value) or (isinstance(value, float) and math.isnan(value)):
        return fallback
    return value
