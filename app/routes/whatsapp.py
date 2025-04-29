# app/routes/whatsapp.py

from fastapi import APIRouter, Form

from app.controllers.whatsapp_controller import handle_whatsapp_message

router = APIRouter()


@router.post("/webhook")
async def whatsapp_webhook(
    Body: str = Form(...),
    From: str = Form(...),
):
    return handle_whatsapp_message(Body, From)
