from app.core.utils import fallback_with_repeat, make_twilio_response, safe_get
from app.functions.sessions import get_state


def process_financing_decision(user_message: str, phone: str):
    (
        active_search_results,
        active_sessions,
        waiting_for_financing_decision,
        session_last_active,
        waiting_for_plate,
    ) = get_state()

    if user_message == "1":
        autos = active_search_results[phone]
        selected_car = autos.iloc[0].to_dict()

        active_sessions[phone] = {
            "selected_car": selected_car,
            "phase": "waiting_for_downpayment",
            "downpayment": None,
            "months": None,
        }
        waiting_for_financing_decision.pop(phone, None)
        return make_twilio_response(
            "💵 ¡Perfecto! ¿Cuánto podrías dar como enganche? (ejemplo: 50000)"
        )

    elif user_message == "2":
        waiting_for_financing_decision.pop(phone, None)
        return make_twilio_response(
            "✅ ¡Perfecto! Si quieres ver otros autos o hacer otra búsqueda, solo envía un mensaje."
        )

    else:
        last_prompt = (
            "💬 ¿Te gustaría que simulemos una opción de financiamiento para este auto?\n\n"
            "Responde 1 para SÍ o 2 para NO."
        )
        return make_twilio_response(fallback_with_repeat(last_prompt))


def process_financing_downpayment(user_message: str, phone: str):
    state = get_state()
    session = state[1][phone]  # active_sessions

    if user_message.isdigit():
        downpayment = int(user_message)
        price = session["selected_car"]["price"]
        max_downpayment = price * 0.7

        if downpayment > max_downpayment:
            return make_twilio_response(
                f"❌ El enganche que propones (${downpayment:,.0f} MXN) "
                f"supera el 70% del valor del auto (${price:,.0f} MXN).\n"
                "Por favor ingresa un monto de enganche más bajo."
            )

        session["downpayment"] = downpayment
        session["phase"] = "waiting_for_months"
        return make_twilio_response(
            "⏳ ¿En cuántos meses te gustaría pagar? (elige entre 36, 48 o 60 meses)"
        )

    last_prompt = "💵 ¿Cuánto podrías dar como enganche? (ejemplo: 50000)"
    return make_twilio_response(fallback_with_repeat(last_prompt))


def process_financing_months(user_message: str, phone: str):
    state = get_state()
    session = state[1][phone]  # active_sessions

    if user_message.isdigit() and int(user_message) in [36, 48, 60]:
        months = int(user_message)
        price = session["selected_car"]["price"]
        downpayment = session["downpayment"]
        interest_rate = 0.10

        loan_amount = price - downpayment
        total_to_pay = loan_amount * (1 + interest_rate)
        monthly_payment = total_to_pay / months

        del state[1][phone]  # borra la sesión

        return make_twilio_response(
            f"💵 Tu simulación:\n\n"
            f"Enganche: ${downpayment:,.0f} MXN\n"
            f"Plazo: {months} meses\n"
            f"Tasa estimada: 10%\n"
            f"Mensualidad aproximada: ${monthly_payment:,.0f} MXN\n\n"
            "🚗 ¿Te gustaría ver otro auto o hacer otra búsqueda?"
        )

    last_prompt = (
        "⏳ ¿En cuántos meses te gustaría pagar? (elige entre 36, 48 o 60 meses)"
    )
    return make_twilio_response(fallback_with_repeat(last_prompt))
