from pathlib import Path

import pandas as pd
import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.services.kavak_info import KavakInfoService
from app.services.openai_client import OpenAIClientService
from app.services.tools import process_plate_or_fine_intent

client = TestClient(app)

# Cargar CSV real del catálogo
csv_path = (
    Path(__file__).resolve().parent.parent / "data" / "sample_caso_ai_engineer.csv"
)
catalog = pd.read_csv(csv_path)

# Tomamos un modelo real del catálogo
example_model = catalog.iloc[0]["model"]
example_make = catalog.iloc[0]["make"]
mock_response_text = (
    f"Te recomiendo un {example_make} {example_model}, es una excelente opción."
)


@pytest.fixture(autouse=True)
def mock_llm(monkeypatch):
    # Simula la respuesta del LLM
    monkeypatch.setattr(
        OpenAIClientService,
        "ask",
        lambda self, session_id, user_message, context, conv_manager: mock_response_text,
    )


def test_user_asks_for_recommendation():
    """Simula que un usuario pide una recomendación y se devuelve un auto del catálogo"""
    response = client.post(
        "/webhook",
        data={"Body": "¿Qué auto me recomiendas?", "From": "+521234567890"},
    )

    assert response.status_code == 200
    decoded = response.content.decode("utf-8")
    assert example_model in decoded
    assert example_make in decoded


def test_user_selects_specific_car(monkeypatch):
    """Simula que un usuario selecciona un auto como respuesta a una recomendación"""

    # Usamos un auto real del catálogo
    row = catalog.iloc[1]
    selected_make = row["make"]
    selected_model = row["model"]
    selected_year = row["year"]
    selected_price = int(row["price"])
    selected_version = row["version"]

    # Respuesta simulada del LLM
    simulated_llm_response = (
        f"Perfecto, seleccionaste el {selected_make} {selected_model} {selected_year}.\n"
        f"Versión: {selected_version}\n"
        f"Precio: ${selected_price:,} MXN"
    )

    monkeypatch.setattr(
        OpenAIClientService,
        "ask",
        lambda self, session_id, user_message, context, conv_manager: simulated_llm_response,
    )

    response = client.post(
        "/webhook",
        data={
            "Body": f"Me interesa el {selected_make} {selected_model}",
            "From": "+521999888777",
        },
    )

    assert response.status_code == 200
    decoded = response.content.decode("utf-8")
    assert selected_model in decoded
    assert (
        selected_version.split()[0] in decoded
    )  # al menos una palabra clave de la versión
    assert f"${selected_price:,}".split()[0] in decoded  # validamos parte del precio


def test_user_requests_financing(monkeypatch):
    """Simula que el usuario pide financiamiento y se devuelve una respuesta contextual"""

    simulated_llm_response = (
        "Claro, para este auto puedes pagar desde $6,500 MXN al mes, "
        "dependiendo del enganche y plazo. ¿Te gustaría simularlo?"
    )

    monkeypatch.setattr(
        OpenAIClientService,
        "ask",
        lambda self, session_id, user_message, context, conv_manager: simulated_llm_response,
    )

    response = client.post(
        "/webhook",
        data={"Body": "¿Cuánto pagaría al mes?", "From": "+521888777666"},
    )

    assert response.status_code == 200
    decoded = response.content.decode("utf-8")
    assert "al mes" in decoded or "mensual" in decoded
    assert "$" in decoded


@pytest.mark.parametrize(
    "user_message,expected_phrase",
    [
        (
            "¿Cuáles son los beneficios de comprar en Kavak?",
            "✔️ Al comprar con Kavak obtienes",
        ),
        ("¿Dónde están sus sedes?", "📍 Nuestras principales sedes son"),
        ("¿Qué planes de pago ofrecen?", "💳 Nuestro plan de pagos te permite"),
    ],
)
def test_faq_queries(monkeypatch, user_message, expected_phrase):
    """Simula preguntas frecuentes y verifica que el contenido real esperado esté presente"""

    # Simula que el LLM responde con los textos reales (omitimos monkeypatch)
    def fake_ask(self, session_id, user_message, context, conv_manager):
        if "beneficio" in user_message.lower():
            return "✔️ Al comprar con Kavak obtienes:\n- Inspección de 240 puntos.\n..."
        elif "sede" in user_message.lower():
            return "📍 Nuestras principales sedes son:\n- CDMX: Patio Santa Fe..."
        elif "plan" in user_message.lower() or "pago" in user_message.lower():
            return "💳 Nuestro plan de pagos te permite adquirir tu auto usado a meses.\n..."
        return "❌ No entendí tu pregunta"

    monkeypatch.setattr(OpenAIClientService, "ask", fake_ask)

    response = client.post(
        "/webhook",
        data={"Body": user_message, "From": "+521777666555"},
    )

    assert response.status_code == 200
    decoded = response.content.decode("utf-8")
    assert expected_phrase in decoded


def test_user_asks_for_fines_without_plate(monkeypatch):
    """Simula que el usuario pregunta por multas sin dar placa y el LLM responde pidiéndola"""

    mock_response = "Por favor, escribe la *placa del vehículo* para buscar las multas."

    monkeypatch.setattr(
        OpenAIClientService,
        "ask",
        lambda self, session_id, user_message, context, conv_manager: mock_response,
    )

    response = client.post(
        "/webhook",
        data={"Body": "Quiero saber si tengo multas", "From": "+521666555444"},
    )

    assert response.status_code == 200
    decoded = response.content.decode("utf-8")
    assert "placa del vehículo" in decoded.lower()


def test_user_asks_for_cheapest_car(monkeypatch):
    """El usuario pregunta por el auto más barato, y el sistema debe responder con el correcto del CSV"""

    cheapest_car = catalog.loc[catalog["price"].idxmin()]
    make = cheapest_car["make"]
    model = cheapest_car["model"]
    price = int(cheapest_car["price"])

    simulated_llm_response = f"El auto más barato que tenemos es un {make} {model} con un precio de ${price:,} MXN."

    monkeypatch.setattr(
        OpenAIClientService,
        "ask",
        lambda self, session_id, user_message, context, conv_manager: simulated_llm_response,
    )

    response = client.post(
        "/webhook",
        data={
            "Body": "¿Cuál es el auto más barato que tienes?",
            "From": "+521444333222",
        },
    )

    assert response.status_code == 200
    decoded = response.content.decode("utf-8")
    assert make in decoded
    assert model in decoded
    assert f"${price:,}".split()[0] in decoded


def test_financing_then_model_switch(monkeypatch):
    """Flujo completo: búsqueda barata → detalles → financiamiento → cambio a otro modelo (Versa) sin contaminar la respuesta"""

    user_id = "+521999111222"
    last_response = {}

    # Flujo simulado paso a paso con función_call
    def fake_llm_response(self, session_id, user_message, context, conv_manager):
        msg = user_message.lower()

        if "barato" in msg:
            last_response["step"] = "search_catalog_car"
            return {
                "function_call": {
                    "name": "search_catalog_car",
                    "arguments": '{"price_max":160000,"phone":"whatsapp:'
                    + user_id
                    + '"}',
                }
            }

        if "detalles del gol" in msg:
            last_response["step"] = "get_car_details_by_index"
            return {
                "function_call": {
                    "name": "get_car_details_by_index",
                    "arguments": '{"index":1,"phone":"whatsapp:' + user_id + '"}',
                }
            }

        if "80 mil" in msg or "80000" in msg:
            last_response["step"] = "simulate_financing"
            return {
                "function_call": {
                    "name": "simulate_financing",
                    "arguments": '{"price":156999,"downpayment":80000,"months":36,"phone":"whatsapp:'
                    + user_id
                    + '"}',
                }
            }

        if "versa" in msg:
            last_response["step"] = "search_catalog_car_new"
            return {
                "function_call": {
                    "name": "search_catalog_car",
                    "arguments": '{"model":"versa","phone":"whatsapp:' + user_id + '"}',
                }
            }

        return {"content": "❌ No entendí tu mensaje"}

    monkeypatch.setattr(OpenAIClientService, "ask", fake_llm_response)

    # Paso 1: busca algo barato
    res1 = client.post("/webhook", data={"Body": "Quiero algo barato", "From": user_id})
    assert res1.status_code == 200
    assert last_response["step"] == "search_catalog_car"

    # Paso 2: pide detalles del Gol
    res2 = client.post(
        "/webhook", data={"Body": "Dame detalles del gol", "From": user_id}
    )
    assert res2.status_code == 200
    assert last_response["step"] == "get_car_details_by_index"

    # Paso 3: financiamiento
    res3 = client.post(
        "/webhook", data={"Body": "Tengo 80000 y a 36 meses", "From": user_id}
    )
    assert res3.status_code == 200
    assert last_response["step"] == "simulate_financing"

    # Paso 4: cambio de intención, buscar Versa
    res4 = client.post(
        "/webhook",
        data={"Body": "Perfecto gracias, ¿tendrás algún Versa?", "From": user_id},
    )
    assert res4.status_code == 200
    assert last_response["step"] == "search_catalog_car_new"

    # Validar que no se repita la simulación de financiamiento anterior
    decoded = res4.content.decode("utf-8").lower()
    assert "enganche" not in decoded
    assert "mensualidad" not in decoded
    assert "80,000" not in decoded
    assert "36 meses" not in decoded


def test_flow_vw_to_versa_with_financing(monkeypatch):
    """Test completo: buscar vw → detalles auto 2 → simular → preguntar por versa → validar que cambia de contexto"""

    user_id = "+521555444333"
    last_function_called = {}

    # Captura la intención del modelo
    def mock_ask(self, session_id, user_message, context, conv_manager):
        msg = user_message.lower()

        if "vw" in msg:
            last_function_called["step"] = "search_vw"
            return {
                "function_call": {
                    "name": "search_catalog_car",
                    "arguments": f'{{"make":"volkswagen","phone":"whatsapp:{user_id}"}}',
                }
            }

        if "segundo" in msg or "2" in msg:
            last_function_called["step"] = "details_2"
            return {
                "function_call": {
                    "name": "get_car_details_by_index",
                    "arguments": f'{{"index":2,"phone":"whatsapp:{user_id}"}}',
                }
            }

        if "80" in msg and "36" in msg:
            last_function_called["step"] = "simulate"
            return {
                "function_call": {
                    "name": "simulate_financing",
                    "arguments": f'{{"price":224999,"downpayment":80000,"months":36,"phone":"whatsapp:{user_id}"}}',
                }
            }

        if "versa" in msg:
            last_function_called["step"] = "search_versa"
            return {
                "function_call": {
                    "name": "search_catalog_car",
                    "arguments": f'{{"make":"nissan","model":"versa","phone":"whatsapp:{user_id}"}}',
                }
            }

        return {"content": "❌ No entendí tu mensaje"}

    monkeypatch.setattr(OpenAIClientService, "ask", mock_ask)

    # Paso 1: buscar vw
    res1 = client.post("/webhook", data={"Body": "Busco un VW", "From": user_id})
    assert res1.status_code == 200
    assert last_function_called["step"] == "search_vw"

    # Paso 2: elegir el segundo
    res2 = client.post(
        "/webhook", data={"Body": "Dame datos del segundo", "From": user_id}
    )
    assert res2.status_code == 200
    assert last_function_called["step"] == "details_2"

    # Paso 3: simular financiamiento
    res3 = client.post(
        "/webhook", data={"Body": "Sí, tengo 80mil y a 36 meses", "From": user_id}
    )
    assert res3.status_code == 200
    assert last_function_called["step"] == "simulate"

    # Paso 4: cambiar de intención
    res4 = client.post(
        "/webhook",
        data={"Body": "Perfecto gracias, ¿tendrás algún versa?", "From": user_id},
    )
    assert res4.status_code == 200
    assert last_function_called["step"] == "search_versa"

    decoded = res4.content.decode("utf-8").lower()
    assert '"make":"nissan"' in decoded
    assert '"model":"versa"' in decoded
    assert "mensualidad" not in decoded
    assert "80" not in decoded


def test_flow_ibiza_to_no_bluetooth(monkeypatch):
    """Flujo completo: buscar ibiza → seleccionar → financiar → cambiar a buscar sin bluetooth"""

    user_id = "+521333999111"
    last_function_called = {}

    def mock_ask(self, session_id, user_message, context, conv_manager):
        msg = user_message.lower()

        if "ibiza" in msg:
            last_function_called["step"] = "search_ibiza"
            return {
                "function_call": {
                    "name": "search_catalog_car",
                    "arguments": f'{{"model":"ibiza","phone":"whatsapp:{user_id}"}}',
                }
            }

        if "1" in msg or "primero" in msg:
            last_function_called["step"] = "details_1"
            return {
                "function_call": {
                    "name": "get_car_details_by_index",
                    "arguments": f'{{"index":1,"phone":"whatsapp:{user_id}"}}',
                }
            }

        if "80" in msg and "36" in msg:
            last_function_called["step"] = "simulate"
            return {
                "function_call": {
                    "name": "simulate_financing",
                    "arguments": f'{{"price":187999,"downpayment":80000,"months":36,"phone":"whatsapp:{user_id}"}}',
                }
            }

        if "sin bluetooth" in msg:
            last_function_called["step"] = "search_no_bluetooth"
            return {
                "function_call": {
                    "name": "search_catalog_car",
                    "arguments": f'{{"bluetooth":false,"phone":"whatsapp:{user_id}"}}',
                }
            }

        return {"content": "❌ No entendí tu mensaje"}

    monkeypatch.setattr(OpenAIClientService, "ask", mock_ask)

    # Paso 1: buscar ibiza
    res1 = client.post("/webhook", data={"Body": "Quiero un Ibiza", "From": user_id})
    assert res1.status_code == 200
    assert last_function_called["step"] == "search_ibiza"

    # Paso 2: seleccionar el primero
    res2 = client.post("/webhook", data={"Body": "El primero", "From": user_id})
    assert res2.status_code == 200
    assert last_function_called["step"] == "details_1"

    # Paso 3: simulación
    res3 = client.post(
        "/webhook", data={"Body": "Tengo 80mil a 36 meses", "From": user_id}
    )
    assert res3.status_code == 200
    assert last_function_called["step"] == "simulate"

    # Paso 4: nuevo criterio
    res4 = client.post(
        "/webhook", data={"Body": "quiero uno sin bluetooth", "From": user_id}
    )
    assert res4.status_code == 200
    assert last_function_called["step"] == "search_no_bluetooth"

    decoded = res4.content.decode("utf-8").lower()
    assert (
        "bluetooth" not in decoded or "false" in decoded
    )  # mensaje no debe decir que sí tiene
    assert "mensualidad" not in decoded  # no debe repetirse simulación anterior
    assert "ibiza" not in decoded  # no debe repetir auto anterior
