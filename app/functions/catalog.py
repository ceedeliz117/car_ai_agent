from pathlib import Path

import pandas as pd

from app.core.constants import BRAND_ABBREVIATIONS, STOPWORDS
from app.core.utils import (
    clean_token,
    extract_price_from_text,
    make_twilio_response,
    safe_get,
    user_is_asking_for_recommendation,
)
from app.functions.sessions import get_state
from app.services.catalog import CatalogService
from app.services.kavak_info import KavakInfoService
from app.services.openai_client import OpenAIClientService

# Servicios compartidos
catalog_service = CatalogService()
openai_service = OpenAIClientService()

context_path = Path(__file__).parent.parent.parent / "data" / "kavak_context.txt"
with open(context_path, "r", encoding="utf-8") as f:
    kavak_context = f.read()


def process_recommendation_by_price(user_message: str, phone: str) -> str | None:
    approx_price = extract_price_from_text(user_message)
    is_recommendation = user_is_asking_for_recommendation(user_message)

    if approx_price and is_recommendation:
        print(f"💰 Recomendación solicitada por precio: {approx_price}")
        df = catalog_service.catalog_df
        filtered = catalog_service.filter_by_approx_price(df, approx_price)

        if not filtered.empty:
            autos = filtered.head(5)
            get_state()[0][phone] = autos

            reply = "🚗 Estos autos podrían interesarte:\n\n"
            for idx, (_, car) in enumerate(autos.iterrows(), 1):
                reply += f"{idx}. {safe_get(car['make'])} {safe_get(car['model'])} ({safe_get(car['year'])}) - ${safe_get(car['price']):,.0f} MXN\n"
            reply += "\n🔢 Responde el número del auto que te interesa para enviarte más detalles."

            return make_twilio_response(reply)
        else:
            return make_twilio_response(
                "❌ No encontré autos en ese rango de precio. Puedes intentar con otra cantidad."
            )

    if any(
        palabra in user_message.lower()
        for palabra in [
            "barato",
            "económico",
            "económica",
            "economico",
            "economica",
            "accesible",
        ]
    ):
        df = catalog_service.catalog_df.sort_values(by="price")
        autos = df.head(10)
        get_state()[0][phone] = autos

        reply = "🚗 Aquí tienes los autos más económicos disponibles:\n\n"
        for idx, (_, car) in enumerate(autos.iterrows(), 1):
            reply += f"{idx}. {safe_get(car['make'])} {safe_get(car['model'])} ({safe_get(car['year'])}) - ${safe_get(car['price']):,.0f} MXN\n"
        reply += "\n🔢 Responde el número del auto que te interesa para enviarte más detalles."
        return make_twilio_response(reply)

    return None


def process_catalog_or_fallback(user_message: str, phone: str):
    approx_price = extract_price_from_text(user_message)
    recommendation_response = process_recommendation_by_price(user_message, phone)
    if recommendation_response:
        return recommendation_response

    tokens = user_message.split()
    tokens = [token for token in tokens if token not in STOPWORDS]
    tokens = [clean_token(token) for token in tokens]
    tokens = [BRAND_ABBREVIATIONS.get(token, token) for token in tokens]
    user_message_processed = " ".join(tokens)

    # Preguntas frecuentes
    if "beneficio" in user_message_processed or "ventaja" in user_message_processed:
        reply = KavakInfoService.get_benefits_info()
    elif "sede" in user_message_processed or "sucursal" in user_message_processed:
        reply = KavakInfoService.get_sedes_info()
    elif (
        "financiamiento" in user_message_processed
        or "pago a meses" in user_message_processed
    ):
        reply = KavakInfoService.get_payment_plans_info()
    elif "kavak" in user_message_processed and len(user_message_processed.split()) < 4:
        reply = KavakInfoService.get_company_info()
    else:
        found_autos = pd.DataFrame()

        for token in tokens:
            search_result = catalog_service.search_catalog(token)
            print(f"🔍 Buscando coincidencias con token: '{token}'")
            if not search_result.empty:
                found_autos = pd.concat([found_autos, search_result])

        if not found_autos.empty:
            found_autos = found_autos.drop_duplicates()
            if approx_price:
                found_autos = catalog_service.filter_by_approx_price(
                    found_autos, approx_price
                )

            autos = found_autos.head(5)

            state = get_state()
            active_search_results = state[0]

            active_search_results[phone] = autos

            reply = "🚗 Autos que encontré para ti:\n\n"
            for idx, (_, car) in enumerate(autos.iterrows(), 1):
                reply += f"{idx}. {safe_get(car['make'])} {safe_get(car['model'])} ({safe_get(car['year'])}) - ${safe_get(car['price']):,.0f} MXN\n"
            reply += "\n🔢 Responde el número del auto que te interesa para enviarte más detalles."
        else:
            print("🤖 Fallback a OpenAI")
            if len(user_message_processed) < 4 or all(len(t) < 3 for t in tokens):
                reply = (
                    "❌ Disculpa, no entendí tu mensaje. ¿Podrías escribirlo nuevamente?\n"
                    "Puedes preguntarme por una marca, modelo o financiamiento."
                )
            else:
                reply = openai_service.ask(user_message_processed, kavak_context)

    return make_twilio_response(reply)
