from fastapi import FastAPI, Form
from fastapi.responses import Response
from app.services.kavak_info import KavakInfoService
from app.services.openai_client import OpenAIClientService
from pathlib import Path

# 👇 Crear FastAPI app (¡esto te faltaba!)
app = FastAPI(title="Kavak Sales Bot")

# Leer contexto general de Kavak para GPT
context_path = Path(__file__).parent.parent / "data" / "kavak_context.txt"
with open(context_path, "r", encoding="utf-8") as f:
    kavak_context = f.read()

# Crear instancia de servicio OpenAI
openai_service = OpenAIClientService()

# Definimos el webhook
@app.post("/webhook")
async def whatsapp_webhook(
    Body: str = Form(...),
    From: str = Form(...),
):
    user_message = Body.lower().strip()

    if "beneficio" in user_message or "ventaja" in user_message:
        reply = KavakInfoService.get_benefits_info()
    elif "sede" in user_message or "sucursal" in user_message:
        reply = KavakInfoService.get_sedes_info()
    elif "financiamiento" in user_message or "pago a meses" in user_message:
        reply = KavakInfoService.get_payment_plans_info()
    elif "qué es kavak" in user_message or "kavak" in user_message:
        reply = KavakInfoService.get_company_info()
    else:
        # Si no hay respuesta fija, preguntamos a OpenAI
        reply = openai_service.ask(user_message, kavak_context)

    response_xml = f"""
    <Response>
        <Message>{reply}</Message>
    </Response>
    """
    return Response(content=response_xml.strip(), media_type="application/xml")
