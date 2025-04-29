# app/controllers/whatsapp_controller.py

from pathlib import Path

import pandas as pd
from fastapi.responses import Response

from app.core.constants import BRAND_ABBREVIATIONS
from app.services.catalog import CatalogService
from app.services.kavak_info import KavakInfoService
from app.services.openai_client import OpenAIClientService

openai_service = OpenAIClientService()
catalog_service = CatalogService()

context_path = Path(__file__).parent.parent.parent / "data" / "kavak_context.txt"
with open(context_path, "r", encoding="utf-8") as f:
    kavak_context = f.read()

active_search_results = {}
active_sessions = {}


def make_twilio_response(message: str) -> Response:
    response_xml = f"""
    <Response>
        <Message>{message}</Message>
    </Response>
    """
    return Response(content=response_xml.strip(), media_type="application/xml")


def handle_whatsapp_message(Body: str, From: str):
    user_message = Body.lower().strip()

    if From in active_sessions:
        session = active_sessions[From]

        if session["phase"] == "waiting_for_downpayment":
            if user_message.isdigit():
                session["downpayment"] = int(user_message)
                session["phase"] = "waiting_for_months"
                reply = "⏳ ¿En cuántos meses te gustaría pagar? (elige entre 36, 48 o 60 meses)"
            else:
                reply = "❌ Por favor ingresa un número válido para el enganche."
            return make_twilio_response(reply)

        if session["phase"] == "waiting_for_months":
            if user_message.isdigit() and int(user_message) in [36, 48, 60]:
                session["months"] = int(user_message)
                price = session["selected_car"]["price"]
                downpayment = session["downpayment"]
                months = session["months"]
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
                reply = "❌ Por favor elige entre 36, 48 o 60 meses."
            return make_twilio_response(reply)

    if user_message == "sí" and From in active_search_results:
        autos = active_search_results[From]
        selected_car = autos.iloc[0].to_dict()

        active_sessions[From] = {
            "selected_car": selected_car,
            "phase": "waiting_for_downpayment",
            "downpayment": None,
            "months": None,
        }
        reply = "💵 ¡Perfecto! ¿Cuánto podrías dar como enganche? (ejemplo: 50000)"
        return make_twilio_response(reply)

    if user_message.isdigit() and From in active_search_results:
        autos = active_search_results[From]
        selected_index = int(user_message) - 1

        if 0 <= selected_index < len(autos):
            selected_car = autos.iloc[selected_index]

            reply = (
                f"🚗 Detalles del auto seleccionado:\n\n"
                f"Marca: {selected_car['make']}\n"
                f"Modelo: {selected_car['model']}\n"
                f"Año: {selected_car['year']}\n"
                f"Versión: {selected_car.get('version', 'N/A')}\n"
                f"Precio: ${selected_car['price']:,.0f} MXN\n"
                f"Bluetooth: {selected_car.get('bluetooth', 'N/A')}\n"
                f"CarPlay: {selected_car.get('car_play', 'N/A')}\n\n"
                "💬 ¿Te gustaría que simulemos una opción de financiamiento para este auto? (responde 'sí' o 'no')"
            )
        else:
            reply = "❌ El número seleccionado no es válido. Por favor selecciona un número de la lista."

        return make_twilio_response(reply)

    tokens = user_message.split()
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

            if not search_result.empty:
                found_autos = pd.concat([found_autos, search_result])

        if not found_autos.empty:
            found_autos = found_autos.drop_duplicates()
            autos = found_autos.head(5)
            active_search_results[From] = autos
            reply = "🚗 Autos que encontré para ti:\n\n"
            for idx, (_, car) in enumerate(autos.iterrows(), 1):
                reply += f"{idx}. {car['make']} {car['model']} ({car['year']}) - ${car['price']:,.0f} MXN\n"
            reply += "\n🔢 Responde el número del auto que te interesa para enviarte más detalles."
        else:
            reply = openai_service.ask(user_message_processed, kavak_context)

    return make_twilio_response(reply)
