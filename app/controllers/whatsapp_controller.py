import threading
from pathlib import Path

from app.core.utils import make_twilio_response, text_normalizer
from app.functions.sessions import clear_user_session, session_cleaner
from app.services.conversation_manager import ConversationManager
from app.services.openai_client import OpenAIClientService

conv_manager = ConversationManager()
openai_service = OpenAIClientService()

context_path = Path(__file__).parent.parent.parent / "data" / "kavak_context.txt"
with open(context_path, "r", encoding="utf-8") as f:
    kavak_context = f.read()

threading.Thread(target=session_cleaner, daemon=True).start()


def handle_whatsapp_message(Body: str, From: str):
    user_message_raw = Body.strip()
    user_message = text_normalizer(user_message_raw)

    print(f"📥 Mensaje recibido de {From}: {user_message}")

    if user_message in ["cancelar", "salir"]:
        clear_user_session(From)
        return make_twilio_response(
            "🛑 Se ha cancelado tu sesión. ¿En qué más puedo ayudarte?"
        )

    response_text = openai_service.ask(
        session_id=From,
        user_message=user_message_raw,
        context=kavak_context,
        conv_manager=conv_manager,
    )

    if isinstance(response_text, str) and len(response_text.strip()) < 2:
        return make_twilio_response("❌ No entendí tu mensaje. ¿Puedes reformularlo?")

    return make_twilio_response(response_text)
