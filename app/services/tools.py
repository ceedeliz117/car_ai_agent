# app/services/tools.py

from app.core.utils import safe_get
from app.core.validators import is_valid_plate
from app.functions.sessions import get_state
from app.services.catalog import CatalogService
from app.services.sqs_sender import send_sqs_plate


def process_plate_or_fine_intent(plate: str, phone: str) -> str:
    if is_valid_plate(plate):
        send_sqs_plate(plate, phone)
        return f"🔎 Estamos consultando las multas de la placa *{plate}*. Te avisaremos en breve."
    else:
        return f"❌ La placa que enviaste no parece válida para CDMX. Asegúrate de usar un formato como ABC123 o ABC123D."


def normalize_bool(value):
    if isinstance(value, str):
        value = value.lower()
        if value in ["true", "sí", "si", "con"]:
            return True
        elif value in ["false", "no", "sin"]:
            return False
    return value


def search_catalog_car(phone=None, conv_manager=None, **filters) -> str:
    print("🔍 Filtros recibidos:", filters)

    for raw_key in list(filters.keys()):
        if "_" in raw_key:
            prefix, suffix = raw_key.split("_", 1)
            if prefix in ["min", "max"]:
                normalized_key = f"{prefix}_{suffix}"
                if raw_key != normalized_key:
                    filters[normalized_key] = filters.pop(raw_key)
            elif suffix in ["min", "max"]:
                normalized_key = f"{suffix}_{prefix}"
                if raw_key != normalized_key:
                    filters[normalized_key] = filters.pop(raw_key)

    print("🔍 telefono:", phone)

    df = CatalogService().catalog_df.copy()

    range_fields = ["price", "year", "km", "largo", "ancho", "altura"]
    operator_map = {
        "lte": "max",
        "gte": "min",
        "$lte": "max",
        "$gte": "min",
        "lt": "max",
        "gt": "min",
        "$lt": "max",
        "$gt": "min",
        "max": "max",
        "min": "min",
    }

    # Soporte para estructura tipo {"price": {"$lt": 160000}}
    for field in range_fields:
        if field in filters and isinstance(filters[field], dict):
            field_filter = filters.pop(field)
            for op, suffix in operator_map.items():
                if op in field_filter:
                    filters[f"{suffix}_{field}"] = field_filter[op]

    for key, value in filters.items():
        for prefix in ["min_", "max_"]:
            if key.startswith(prefix):
                base_field = key[len(prefix) :]
                if base_field in df.columns:
                    if prefix == "min_":
                        df = df[df[base_field] >= value]
                    elif prefix == "max_":
                        df = df[df[base_field] <= value]

    # Filtros exactos
    field_aliases = {
        "modelo": "model",
        "marca": "make",
        "versión": "version",
        "precio": "price",
        # más alias si es necesario
    }

    for key, value in filters.items():
        if value is None or key.startswith(("min_", "max_")):
            continue

        column = field_aliases.get(key, key)
        if column not in df.columns:
            continue

        normalized_value = normalize_bool(value)
        if isinstance(normalized_value, bool):
            df = df[df[column] == normalized_value]
        else:
            df = df[df[column].astype(str).str.lower() == str(normalized_value).lower()]

    # Fallback por tokens
    model_value = filters.get("model") or filters.get("modelo")
    if df.empty and model_value:
        tokens = str(model_value).lower().split()
        fallback_df = CatalogService().catalog_df.copy()
        fallback_mask = fallback_df.apply(
            lambda row: any(
                token in str(row.get(col, "")).lower()
                for token in tokens
                for col in ["make", "model", "version"]
            ),
            axis=1,
        )
        df = fallback_df[fallback_mask]

    if phone:
        active_search_results, active_sessions, *_ = get_state()
        print(f"💾 Guardando {len(df)} autos para {phone}")
        active_search_results[phone] = df

        # Solo limpiar si realmente hay resultados
        if not df.empty:
            active_sessions.pop(phone, None)
            if conv_manager:
                conv_manager.set_attribute(phone, "selected_car", None)
                conv_manager.set_attribute(phone, "intent_state", {})

    df = df.head(5)

    if df.empty:
        return {"error": "NO_MATCHES"}

    results = df.to_dict(orient="records")

    if phone:
        active_search_results, active_sessions, *_ = get_state()
        active_search_results[phone] = df
        if not df.empty:
            active_sessions.pop(phone, None)
            if conv_manager:
                conv_manager.set_attribute(phone, "selected_car", None)
                conv_manager.set_attribute(phone, "intent_state", {})

    return {"matches": results, "total_found": len(results)}


def get_car_details_by_index(index: int, phone: str) -> dict:
    active_search_results, active_sessions, *_ = get_state()
    print(f"📥 Usuario pidió detalles del auto {index} para {phone}")
    print(f"📂 Autos disponibles en memoria:", list(active_search_results.keys()))

    if phone not in active_search_results:
        return {"error": "NO_SEARCH_RESULTS"}

    df = active_search_results[phone]

    if index < 1 or index > len(df):
        return {"error": "INVALID_INDEX", "available_range": len(df)}

    car = df.iloc[index - 1]
    car_dict = car.to_dict()

    active_sessions[phone] = {"selected_car": car_dict, "waiting_financing": True}

    return {
        "make": car_dict.get("make"),
        "model": car_dict.get("model"),
        "year": car_dict.get("year"),
        "version": car_dict.get("version"),
        "price": car_dict.get("price"),
        "bluetooth": car_dict.get("bluetooth", "No"),
        "car_play": car_dict.get("car_play", "No"),
        "largo": car_dict.get("largo"),
        "ancho": car_dict.get("ancho"),
        "altura": car_dict.get("altura"),
    }


def simulate_financing(
    price: float = None,
    downpayment: float = None,
    months: int = None,
    phone: str = None,
    conv_manager=None,
) -> str:
    print("teléfono", phone)

    # 1. Buscar auto seleccionado si no se dio el precio
    _, active_sessions, *_ = get_state()

    if price is None and phone:
        car = active_sessions.get(phone, {}).get("selected_car")
        if not car and conv_manager:
            car = conv_manager.get_attribute(phone, "selected_car")
        if car:
            price = car.get("price")

    if not price:
        return "❌ No tengo el precio del auto. Por favor selecciona un auto antes de simular el financiamiento."

    # 2. Validar enganche
    MIN_ENGANCHE = 0.1
    MAX_ENGANCHE = 0.7

    if downpayment is None:
        return f"¿Con cuánto quieres iniciar como enganche? El mínimo es el 10% del valor del auto (al menos ${price * MIN_ENGANCHE:,.0f} MXN)."

    if downpayment < price * MIN_ENGANCHE:
        return f"❌ El enganche mínimo es el 10% del valor del auto (${price * MIN_ENGANCHE:,.0f} MXN)."

    if downpayment > price * MAX_ENGANCHE:
        return f"❌ El enganche no debe exceder el 70% del valor del auto (${price * MAX_ENGANCHE:,.0f} MXN)."

    # 3. Validar plazo
    if months is None:
        return "¿A cuántos meses te gustaría financiarlo? Por ejemplo, puedes elegir 36, 48 o 60 meses."

    # 4. Calcular simulación
    INTEREST_RATE = 0.10
    loan_amount = price - downpayment
    total_to_pay = loan_amount * (1 + INTEREST_RATE)
    monthly_payment = total_to_pay / months

    if phone in active_sessions:
        active_sessions[phone]["waiting_financing"] = False
        active_sessions[phone]["selected_car"] = None

    if conv_manager:
        conv_manager.set_attribute(phone, "selected_car", None)
        conv_manager.set_attribute(phone, "last_financing", None)

    return {
        "price": round(price),
        "downpayment": round(downpayment),
        "months": months,
        "interest_rate": INTEREST_RATE,
        "monthly_payment": round(monthly_payment),
        "loan_amount": round(loan_amount),
        "total_to_pay": round(total_to_pay),
    }


def get_user_preferences(phone: str) -> dict:
    return {
        "question": "¿Prefieres un auto amplio, económico, con tecnología como CarPlay o Bluetooth?",
        "options": ["económico", "amplio", "conectividad", "auto compacto", "familiar"],
    }
