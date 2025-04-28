from fastapi import FastAPI, Request, Form
from app.core.config import settings
from fastapi.responses import PlainTextResponse

app = FastAPI(title="Kavak Sales Bot")

@app.get("/")
async def root():
    return {"message": "Kavak Sales Bot is running!"}

@app.post("/webhook", response_class=PlainTextResponse)
async def whatsapp_webhook(
    request: Request,
    body: str = Form(...),
    from_number: str = Form(...),
):
    print(f"📩 Mensaje recibido de {from_number}: {body}")
    return "Mensaje recibido correctamente."
