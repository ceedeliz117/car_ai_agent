# app/main.py

from fastapi import FastAPI

from app.routes.health import router as health_router
from app.routes.whatsapp import router as whatsapp_router

app = FastAPI(title="Kavak Sales Bot")

app.include_router(whatsapp_router)
app.include_router(health_router)
