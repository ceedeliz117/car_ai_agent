import os
from pathlib import Path

import pandas as pd
import pytest
from dotenv import load_dotenv
from fastapi.testclient import TestClient

# Cargar .env desde la raíz del proyecto
env_path = Path(__file__).resolve().parent.parent / ".env"
load_dotenv(dotenv_path=env_path)

from app.core.utils import (
    extract_price_from_text,
    fallback_with_repeat,
    make_twilio_response,
    user_is_asking_for_recommendation,
)
from app.functions.autos import process_selected_auto
from app.functions.financing import process_financing_decision
from app.functions.fines import process_plate_or_fine_intent
from app.functions.sessions import (
    active_search_results,
    active_sessions,
    waiting_for_financing_decision,
    waiting_for_plate,
)

# App y funciones
from app.main import app
from app.services.kavak_info import KavakInfoService

client = TestClient(app)


def get_response_text(response):
    return response.body.decode()


@pytest.fixture(autouse=True)
def mock_services(monkeypatch):
    monkeypatch.setattr(KavakInfoService, "get_benefits_info", lambda: "Mock beneficio")
    monkeypatch.setattr(KavakInfoService, "get_sedes_info", lambda: "Mock sede")
    monkeypatch.setattr(
        KavakInfoService, "get_payment_plans_info", lambda: "Mock financiamiento"
    )


@pytest.fixture
def reset_sessions():
    active_sessions.clear()
    active_search_results.clear()
    waiting_for_financing_decision.clear()
    waiting_for_plate.clear()


# === CASOS DE PLACAS Y MULTAS ===


def test_handle_whatsapp_message_intent_without_plate(reset_sessions):
    """Usuario expresa intención de consultar multas pero no envía placa"""
    user_message = "Quiero ver si tengo multas"
    phone = "+521234567890"
    response = process_plate_or_fine_intent(user_message, phone)
    assert "escribe la *placa del vehículo*" in get_response_text(response)


def test_handle_whatsapp_message_valid_plate(reset_sessions, monkeypatch):
    """Placa válida correctamente procesada"""
    user_message = "Consulta de multa para ABC123"
    phone = "+521234567890"

    monkeypatch.setattr("app.functions.fines.is_valid_plate", lambda plate: True)
    response = process_plate_or_fine_intent(user_message, phone)
    assert "Estamos consultando las multas" in get_response_text(response)


def test_handle_whatsapp_message_invalid_but_formatted_plate(
    reset_sessions, monkeypatch
):
    """Placa con formato válido pero no válida para CDMX"""
    user_message = "Consulta de multa para ABC123"
    phone = "+521234567890"

    monkeypatch.setattr("app.functions.fines.is_valid_plate", lambda plate: False)
    response = process_plate_or_fine_intent(user_message, phone)
    assert "no parece válida" in get_response_text(response)


def test_handle_whatsapp_message_badly_formatted_plate(reset_sessions):
    """Placa mal formateada, no coincide con el patrón"""
    user_message = "Mi placa es 123ABC456"
    phone = "+521234567890"

    response = process_plate_or_fine_intent(user_message, phone)
    assert "escribe la *placa del vehículo*" in get_response_text(response)


def test_handle_whatsapp_message_waiting_for_plate(reset_sessions, monkeypatch):
    """Ya está esperando una placa, ahora la envía"""
    user_message = "ABC123"
    phone = "+521234567890"
    waiting_for_plate[phone] = True

    monkeypatch.setattr("app.functions.fines.is_valid_plate", lambda plate: True)
    response = process_plate_or_fine_intent(user_message, phone)
    assert "Estamos consultando las multas" in get_response_text(response)


# === CASOS DE FINANCIAMIENTO ===


def test_handle_whatsapp_message_waiting_for_financing_decision(reset_sessions):
    """Responde con '1' para aceptar financiamiento"""
    user_message = "1"
    phone = "+521234567890"

    # Simular búsqueda previa
    active_search_results[phone] = pd.DataFrame(
        [{"make": "Honda", "model": "Civic", "price": 200000}]
    )

    waiting_for_financing_decision[phone] = True
    active_sessions[phone] = {
        "phase": "waiting_for_downpayment",
        "selected_car": {"make": "Honda", "model": "Civic", "price": 200000},
    }

    response = process_financing_decision(user_message, phone)
    assert "¿Cuánto podrías dar como enganche?" in get_response_text(response)


# === CASOS DE SELECCIÓN DE AUTO ===


def test_handle_whatsapp_message_selected_auto(reset_sessions):
    """Usuario selecciona un auto de la lista"""
    user_message = "1"
    phone = "+521234567890"

    active_search_results[phone] = pd.DataFrame(
        [{"make": "Toyota", "model": "Corolla", "year": 2020, "price": 250000}]
    )

    response = process_selected_auto(user_message, phone)
    assert "Detalles del auto seleccionado" in get_response_text(response)


# === FUNCIONES UTILITARIAS ===


def test_fallback_with_repeat():
    """Responde con el mensaje repetido en caso de confusión"""
    last_prompt = (
        "💬 ¿Te gustaría que simulemos una opción de financiamiento para este auto?"
    )
    result = fallback_with_repeat(last_prompt)
    assert "Disculpa, no entendí tu mensaje" in result
    assert last_prompt in result


@pytest.mark.parametrize(
    "message, expected",
    [
        ("busco uno de 300 mil", 300000),
        ("y si tengo 300mil?", 300000),
        ("unos 150k está bien", 150000),
        ("quiero uno que cueste un toston", 50000),
        ("algo de 50,000 pesos", 50000),
        ("medio millon", 500000),
        ("dame algo por 1 millon", 1000000),
    ],
)
def test_extract_price_from_text(message, expected):
    assert extract_price_from_text(message) == expected


@pytest.mark.parametrize(
    "message",
    [
        "qué auto me recomiendas",
        "puedes sugerirme un coche?",
        "recomiéndame uno bueno",
        "recomiendame uno bueno",
        "qué auto debería comprar",
        "tienes alguna sugerencia?",
    ],
)
def test_user_is_asking_for_recommendation_true(message):
    assert user_is_asking_for_recommendation(message) is True


def test_number_without_context_should_reset_session(reset_sessions):
    """Usuario responde con '1' sin haber lista activa"""
    phone = "+521234567890"
    response = client.post("/webhook", data={"From": phone, "Body": "1"})
    text = response.text
    assert "no entendí tu mensaje" in text.lower()
    assert phone not in active_sessions


def test_generic_short_word_without_context_should_be_rejected(reset_sessions):
    """Usuario responde con 'sí' sin haber iniciado un flujo"""
    phone = "+521234567890"
    response = client.post("/webhook", data={"From": phone, "Body": "sí"})
    text = response.text
    assert "no entendí tu mensaje" in text.lower()
    assert phone not in active_sessions


def test_empty_body_or_non_text_should_reset_session(reset_sessions):
    """Simula mensaje sin texto como audio o archivo"""
    phone = "+521234567890"
    response = client.post("/webhook", data={"From": phone, "Body": ""})
    text = response.text
    assert "solo puedo procesar mensajes de texto" in text.lower()
    assert phone not in active_sessions


@pytest.mark.parametrize("message", ["ok", "hola", "dale", "ya", "va"])
def test_short_words_with_no_context_get_rejected(reset_sessions, message):
    phone = "+521234567890"
    response = client.post("/webhook", data={"From": phone, "Body": message})
    text = response.text
    assert "no entendí tu mensaje" in text.lower()
    assert phone not in active_sessions


def test_cancelar_clears_all_session_states(reset_sessions):
    phone = "+521234567890"
    active_sessions[phone] = {"phase": "waiting_for_months"}
    waiting_for_financing_decision[phone] = True
    active_search_results[phone] = pd.DataFrame()
    waiting_for_plate[phone] = True

    response = client.post("/webhook", data={"From": phone, "Body": "cancelar"})
    text = response.text

    assert "se ha cancelado tu sesión" in text.lower()
    assert phone not in active_sessions
    assert phone not in waiting_for_financing_decision
    assert phone not in waiting_for_plate
