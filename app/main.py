from fastapi import FastAPI, Form
from fastapi.responses import Response
from app.services.kavak_info import KavakInfoService
from app.services.openai_client import OpenAIClientService
from app.services.catalog import CatalogService

from pathlib import Path

app = FastAPI(title="Kavak Sales Bot")

context_path = Path(__file__).parent.parent / "data" / "kavak_context.txt"
with open(context_path, "r", encoding="utf-8") as f:
    kavak_context = f.read()

openai_service = OpenAIClientService()
catalog_service = CatalogService()

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
        search_by_make = catalog_service.search_by_make(user_message)
        search_by_model = catalog_service.search_by_model(user_message)

        if not search_by_make.empty:
            first_car = search_by_make.iloc[0]
            reply = (
                f"🚗 Encontré este auto disponible:\n"
                f"{first_car['make']} {first_car['model']} {first_car['year']} - "
                f"${first_car['price']:,.0f} MXN."
            )
        elif not search_by_model.empty:
            first_car = search_by_model.iloc[0]
            reply = (
                f"🚗 Encontré este modelo disponible:\n"
                f"{first_car['make']} {first_car['model']} {first_car['year']} - "
                f"${first_car['price']:,.0f} MXN."
            )
        else:
            reply = openai_service.ask(user_message, kavak_context)

    response_xml = f"""
    <Response>
        <Message>{reply}</Message>
    </Response>
    """
    return Response(content=response_xml.strip(), media_type="application/xml")
