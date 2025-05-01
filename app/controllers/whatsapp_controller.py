import math
import re
import string
import threading
import time
import unicodedata
from datetime import datetime
from pathlib import Path

import pandas as pd
from fastapi.responses import Response

from app.core.constants import BRAND_ABBREVIATIONS, STOPWORDS
from app.core.utils import normalizar_texto
from app.core.validators import es_placa_valida_cdMX
from app.services.catalog import CatalogService
from app.services.kavak_info import KavakInfoService
from app.services.openai_client import OpenAIClientService
from app.services.sqs_sender import enviar_placa_a_sqs

openai_service = OpenAIClientService()
catalog_service = CatalogService()

context_path = Path(__file__).parent.parent.parent / "data" / "kavak_context.txt"
with open(context_path, "r", encoding="utf-8") as f:
    kavak_context = f.read()

active_search_results = {}
active_sessions = {}
waiting_for_financing_decision = {}
session_last_active = {}
waiting_for_plate = {}

SESSION_TIMEOUT_SECONDS = 300


def clean_token(token: str) -> str:
    """Elimina puntuación y acentos de un token individual."""
    token = token.translate(str.maketrans("", "", string.punctuation))  # remueve signos
    token = "".join(
        c
        for c in unicodedata.normalize("NFD", token)
        if unicodedata.category(c) != "Mn"
    )  # remueve acentos
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


def session_cleaner():
    while True:
        now = datetime.utcnow()
        to_delete = []

        for phone, last_active in session_last_active.items():
            elapsed_seconds = (now - last_active).total_seconds()
            if elapsed_seconds > SESSION_TIMEOUT_SECONDS:
                to_delete.append(phone)

        for phone in to_delete:
            print(f"🧹 Limpiando sesión inactiva por timeout: {phone}")
            active_sessions.pop(phone, None)
            active_search_results.pop(phone, None)
            waiting_for_financing_decision.pop(phone, None)
            session_last_active.pop(phone, None)

        time.sleep(60)


threading.Thread(target=session_cleaner, daemon=True).start()


def handle_whatsapp_message(Body: str, From: str):
    user_message_raw = Body.strip()
    user_message = normalizar_texto(user_message_raw)

    print(f"📥 Mensaje recibido de {From}: {user_message}")
    multas_keywords = [
        "multa",
        "multas",
        "infraccion",
        "infracciones",
        "placa",
        "tenencia",
        "adeudo",
        "adeudos",
        "tarjeta de circulacion",
        "licencia",
        "transito",
        "pago de placas",
        "verifica si debo",
        "debo pagar",
        "consultar placa",
    ]

    if any(keyword in user_message for keyword in multas_keywords):
        print("🧾 Detectamos intención de consultar multas")

        # Detectar placas tipo ABC123 o ABC123D
        match = re.search(r"\b([A-Z]{3}\d{3}[A-Z]?)\b", user_message_raw.upper())
        if match:
            plate = match.group(1).upper()
            if es_placa_valida_cdMX(plate):
                enviar_placa_a_sqs(plate, From)
                return make_twilio_response(
                    f"🔎 Estamos consultando las multas de la placa *{plate}*. Te avisaremos en breve."
                )
            else:
                return make_twilio_response(
                    "❌ La placa que enviaste no parece válida para CDMX. Asegúrate de usar un formato como ABC123 o ABC123D."
                )

        else:
            waiting_for_plate[From] = True
            return make_twilio_response(
                "🚗 Claro, puedo ayudarte con eso. Por favor escribe la *placa del vehículo* que deseas consultar, como por ejemplo: ABC123 o NSZ314B."
            )

    session_last_active[From] = datetime.utcnow()

    if waiting_for_plate.get(From):
        match = re.search(r"\b([A-Z]{3}\d{3}[A-Z]?)\b", user_message_raw.upper())
        if match:
            plate = match.group(1)
            enviar_placa_a_sqs(plate, From)
            del waiting_for_plate[From]
            return make_twilio_response(
                f"🔎 Estamos consultando las multas de la placa *{plate}*. Te avisaremos en breve."
            )
        else:
            return make_twilio_response(
                "❌ No detecté la placa. Por favor escríbela como: ABC123 o NSZ314B."
            )

    if waiting_for_financing_decision.get(From):
        if user_message == "1":
            autos = active_search_results[From]
            selected_car = autos.iloc[0].to_dict()

            active_sessions[From] = {
                "selected_car": selected_car,
                "phase": "waiting_for_downpayment",
                "downpayment": None,
                "months": None,
            }
            reply = "💵 ¡Perfecto! ¿Cuánto podrías dar como enganche? (ejemplo: 50000)"
            waiting_for_financing_decision.pop(From, None)
        elif user_message == "2":
            reply = "✅ ¡Perfecto! Si quieres ver otros autos o hacer otra búsqueda, solo envía un mensaje."
            waiting_for_financing_decision.pop(From, None)
        else:
            last_prompt = (
                "💬 ¿Te gustaría que simulemos una opción de financiamiento para este auto?\n\n"
                "Responde 1 para SÍ o 2 para NO."
            )
            reply = fallback_with_repeat(last_prompt)

        return make_twilio_response(reply)

    if From in active_sessions:
        session = active_sessions[From]
        print(f"⚙️ Sesión activa detectada: fase {session['phase']}")

        if session["phase"] == "waiting_for_downpayment":
            if user_message.isdigit():
                downpayment = int(user_message)
                price = session["selected_car"]["price"]
                max_downpayment = price * 0.7

                if downpayment > max_downpayment:
                    reply = (
                        f"❌ El enganche que propones (${downpayment:,.0f} MXN) "
                        f"supera el 70% del valor del auto (${price:,.0f} MXN).\n"
                        "Por favor ingresa un monto de enganche más bajo."
                    )
                else:
                    session["downpayment"] = downpayment
                    session["phase"] = "waiting_for_months"
                    reply = "⏳ ¿En cuántos meses te gustaría pagar? (elige entre 36, 48 o 60 meses)"
            else:
                last_prompt = "💵 ¿Cuánto podrías dar como enganche? (ejemplo: 50000)"
                reply = fallback_with_repeat(last_prompt)

            return make_twilio_response(reply)

        if session["phase"] == "waiting_for_months":
            if user_message.isdigit() and int(user_message) in [36, 48, 60]:
                months = int(user_message)
                price = session["selected_car"]["price"]
                downpayment = session["downpayment"]
                interest_rate = 0.10

                loan_amount = price - downpayment
                total_to_pay = loan_amount * (1 + interest_rate)
                monthly_payment = total_to_pay / months

                reply = (
                    f"💵 Tu simulación:\n\n"
                    f"Enganche: ${downpayment:,.0f} MXN\n"
                    f"Plazo: {months} meses\n"
                    f"Tasa estimada: 10%\n"
                    f"Mensualidad aproximada: ${monthly_payment:,.0f} MXN\n\n"
                    "🚗 ¿Te gustaría ver otro auto o hacer otra búsqueda?"
                )

                del active_sessions[From]
            else:
                last_prompt = "⏳ ¿En cuántos meses te gustaría pagar? (elige entre 36, 48 o 60 meses)"
                reply = fallback_with_repeat(last_prompt)

            return make_twilio_response(reply)

    if user_message.isdigit() and From in active_search_results:
        print("📄 Usuario eligió auto por número")
        autos = active_search_results[From]
        selected_index = int(user_message) - 1

        if 0 <= selected_index < len(autos):
            selected_car = autos.iloc[selected_index]

            active_search_results[From] = autos.iloc[[selected_index]]
            waiting_for_financing_decision[From] = True

            reply = (
                f"🚗 Detalles del auto seleccionado:\n\n"
                f"Marca: {safe_get(selected_car['make'])}\n"
                f"Modelo: {safe_get(selected_car['model'])}\n"
                f"Año: {safe_get(selected_car['year'])}\n"
                f"Versión: {safe_get(selected_car.get('version'))}\n"
                f"Precio: ${safe_get(selected_car['price']):,.0f} MXN\n"
                f"Bluetooth: {safe_get(selected_car.get('bluetooth'), 'NO')}\n"
                f"CarPlay: {safe_get(selected_car.get('car_play'), 'NO')}\n\n"
                "💬 ¿Te gustaría que simulemos una opción de financiamiento para este auto?\n\n"
                "Responde 1 para SÍ o 2 para NO."
            )
        else:
            print("❌ Número de auto seleccionado fuera de rango")
            reply = "❌ El número seleccionado no es válido. Por favor selecciona un número de la lista."

        return make_twilio_response(reply)

    print("🔎 Procesando búsqueda en catálogo o fallback OpenAI")
    tokens = user_message.split()
    tokens = [token for token in tokens if token not in STOPWORDS]
    tokens = [clean_token(token) for token in tokens]
    tokens = [BRAND_ABBREVIATIONS.get(token, token) for token in tokens]
    user_message_processed = " ".join(tokens)

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
            autos = found_autos.head(5)
            active_search_results[From] = autos
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
