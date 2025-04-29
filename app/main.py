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
    elif "kavak" in user_message and len(user_message.split()) < 4:
        reply = KavakInfoService.get_company_info()
    else:
        tokens = user_message.split()

        found_autos = pd.DataFrame()

        for token in tokens:
            search_by_make = catalog_service.search_by_make(token)
            search_by_model = catalog_service.search_by_model(token)

            if not search_by_make.empty:
                found_autos = pd.concat([found_autos, search_by_make])

            if not search_by_model.empty:
                found_autos = pd.concat([found_autos, search_by_model])

        if not found_autos.empty:
            found_autos = found_autos.drop_duplicates()
            autos = found_autos.head(3)
            reply = "🚗 Autos que encontré para ti:\n"
            for _, car in autos.iterrows():
                reply += f"- {car['make']} {car['model']} ({car['year']}) - ${car['price']:,.0f} MXN\n"
        else:
            reply = openai_service.ask(user_message, kavak_context)

    response_xml = f"""
    <Response>
        <Message>{reply}</Message>
    </Response>
    """
    return Response(content=response_xml.strip(), media_type="application/xml")
