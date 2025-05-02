import re

from app.core.utils import make_twilio_response, safe_get
from app.functions.sessions import get_state


def process_selected_auto(user_message: str, phone: str):
    (
        active_search_results,
        active_sessions,
        waiting_for_financing_decision,
        session_last_active,
        waiting_for_plate,
    ) = get_state()

    print("📄 Usuario eligió auto por número")
    autos = active_search_results[phone]

    try:
        selected_index = int(re.match(r"^\d+", user_message).group()) - 1
    except (ValueError, AttributeError):
        return make_twilio_response(
            "❌ Por favor responde solo con el número del auto que te interesa."
        )

    if not (0 <= selected_index < len(autos)):
        return make_twilio_response(
            "❌ Opción inválida. Por favor selecciona un número de la lista."
        )

    selected_car = autos.iloc[selected_index]

    active_search_results[phone] = autos.iloc[[selected_index]]
    waiting_for_financing_decision[phone] = True

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

    return make_twilio_response(reply)
