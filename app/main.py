from fastapi import FastAPI, Form
from fastapi.responses import Response

app = FastAPI(title="Kavak Sales Bot")

@app.post("/webhook")
async def whatsapp_webhook(
    Body: str = Form(...),
    From: str = Form(...),
):
    print(f"📩 Mensaje recibido de {From}: {Body}")
    reply = "🚗 ¡Hola! Soy tu asesor virtual de Kavak. ¿Qué tipo de auto estás buscando hoy?"

    response_xml = f"""
    <Response>
        <Message>{reply}</Message>
    </Response>
    """
    return Response(content=response_xml.strip(), media_type="application/xml")
