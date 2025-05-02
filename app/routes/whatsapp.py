# app/routes/whatsapp.py

from fastapi import APIRouter, Form

from app.controllers.whatsapp_controller import handle_whatsapp_message
from app.core.utils import make_twilio_response
from app.functions.sessions import clear_user_session

router = APIRouter()


@router.post("/webhook")
async def whatsapp_webhook(
    Body: str = Form(...),
    From: str = Form(...),
):
    if not Body or not isinstance(Body, str) or Body.strip() == "":
        clear_user_session(From)
        return make_twilio_response(
            "📎 Solo puedo procesar mensajes de texto por ahora. Se ha reiniciado tu sesión."
        )
    return handle_whatsapp_message(Body, From)
