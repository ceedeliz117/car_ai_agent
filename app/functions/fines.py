import re

from app.core.utils import make_twilio_response
from app.core.validators import is_valid_plate
from app.functions.sessions import get_state
from app.services.sqs_sender import enviar_placa_a_sqs


def process_plate_or_fine_intent(
    user_message_raw: str,
    phone: str,
):
    """
    Procesa el mensaje cuando el usuario ya ha expresado intención de consultar multas,
    o está pendiente de enviar una placa.
    """

    (_, _, _, _, waiting_for_plate) = get_state()

    match = re.search(r"\b([A-Z]{3}\d{3}[A-Z]?)\b", user_message_raw.upper())
    if match:
        plate = match.group(1).upper()
        if is_valid_plate(plate):
            enviar_placa_a_sqs(plate, phone)
            # Limpiar si estaba esperando
            waiting_for_plate.pop(phone, None)
            return make_twilio_response(
                f"🔎 Estamos consultando las multas de la placa *{plate}*. Te avisaremos en breve."
            )
        else:
            return make_twilio_response(
                "❌ La placa que enviaste no parece válida para CDMX. Asegúrate de usar un formato como ABC123 o ABC123D."
            )
    else:
        waiting_for_plate[phone] = True
        return make_twilio_response(
            "🚗 Claro, puedo ayudarte con eso. Por favor escribe la *placa del vehículo* que deseas consultar, como por ejemplo: ABC123 o NSZ314B."
        )
