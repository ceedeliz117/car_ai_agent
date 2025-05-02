import re
import threading
import time
from datetime import datetime
from pathlib import Path

import pandas as pd
from fastapi.responses import Response

from app.core.constants import MULTAS_KEYWORDS
from app.core.utils import make_twilio_response, text_normalizer
from app.functions.autos import process_selected_auto
from app.functions.catalog import process_catalog_or_fallback
from app.functions.financing import (
    process_financing_decision,
    process_financing_downpayment,
    process_financing_months,
)
from app.functions.fines import process_plate_or_fine_intent
from app.functions.sessions import (
    clear_user_session,
    get_state,
    session_cleaner,
    update_last_active,
)
from app.services.catalog import CatalogService
from app.services.kavak_info import KavakInfoService
from app.services.openai_client import OpenAIClientService

threading.Thread(target=session_cleaner, daemon=True).start()

openai_service = OpenAIClientService()
catalog_service = CatalogService()

context_path = Path(__file__).parent.parent.parent / "data" / "kavak_context.txt"
with open(context_path, "r", encoding="utf-8") as f:
    kavak_context = f.read()


def handle_whatsapp_message(Body: str, From: str):
    (
        active_search_results,
        active_sessions,
        waiting_for_financing_decision,
        session_last_active,
        waiting_for_plate,
    ) = get_state()
    user_message_raw = Body.strip()
    user_message = text_normalizer(user_message_raw)

    print(f"📥 Mensaje recibido de {From}: {user_message}")

    if user_message in ["cancelar", "salir"]:
        clear_user_session(From)
        return make_twilio_response(
            "🛑 Se ha cancelado tu sesión. ¿En qué más puedo ayudarte?"
        )

    if From in active_sessions and any(
        keyword in user_message for keyword in MULTAS_KEYWORDS
    ):
        print("⚠️ Usuario intentó cambiar de tema a mitad del flujo.")
        return make_twilio_response(
            "🚧 Estás en medio de una simulación. Si quieres consultar multas, escribe *cancelar* para terminar este flujo primero."
        )

    if any(keyword in user_message for keyword in MULTAS_KEYWORDS):
        print("🧾 Detectamos intención de consultar multas")
        return process_plate_or_fine_intent(user_message_raw, From)

    update_last_active(From)

    if waiting_for_plate.get(From):
        return process_plate_or_fine_intent(user_message_raw, From)

    if waiting_for_financing_decision.get(From):
        return process_financing_decision(user_message, From)

    if From in active_sessions:
        session = active_sessions[From]
        if session["phase"] == "waiting_for_downpayment":
            return process_financing_downpayment(user_message, From)
        if session["phase"] == "waiting_for_months":
            return process_financing_months(user_message, From)

    if (
        user_message.isdigit()
        and From in active_search_results
        and not active_search_results[From].empty
    ):
        return process_selected_auto(user_message, From)

    if user_message.isdigit():
        print(
            "⚠️ Usuario envió número sin contexto válido. Cerrando sesión para evitar errores."
        )
        clear_user_session(From)
        return make_twilio_response(
            "❌ No entendí tu mensaje. ¿Podrías decirme si estás buscando un auto o quieres consultar multas?"
        )

    print("🔎 Procesando búsqueda en catálogo o fallback OpenAI")
    fallback_response = process_catalog_or_fallback(user_message, From)

    if (
        From in active_sessions
        or waiting_for_plate.get(From)
        or waiting_for_financing_decision.get(From)
    ) and (
        From not in active_search_results
        or active_search_results[From].empty
        or len(user_message.strip()) <= 3
    ):
        print(
            "⚠️ Resultado sin contexto válido o palabra muy corta durante un flujo. Respuesta no confiable, limpiando sesión."
        )
        clear_user_session(From)
        return make_twilio_response(
            "❌ No entendí tu mensaje. ¿Estás buscando un auto o necesitas consultar multas?"
        )

    return fallback_response
