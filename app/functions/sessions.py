# app/functions/sessions.py

import time
from datetime import datetime

# 🔄 Estados globales de sesión
active_search_results = {}
active_sessions = {}
waiting_for_financing_decision = {}
session_last_active = {}
waiting_for_plate = {}

SESSION_TIMEOUT_SECONDS = 300


def get_state():
    """Devuelve todas las referencias del estado."""
    return (
        active_search_results,
        active_sessions,
        waiting_for_financing_decision,
        session_last_active,
        waiting_for_plate,
    )


def update_last_active(phone: str):
    session_last_active[phone] = datetime.utcnow()


def clear_user_session(phone: str):
    """Borra toda la información de sesión de un usuario."""
    active_sessions.pop(phone, None)
    active_search_results.pop(phone, None)
    waiting_for_financing_decision.pop(phone, None)
    session_last_active.pop(phone, None)
    waiting_for_plate.pop(phone, None)


def session_cleaner():
    while True:
        now = datetime.utcnow()
        to_delete = []

        for phone, last_active in session_last_active.items():
            elapsed_seconds = (now - last_active).total_seconds()
            if elapsed_seconds > SESSION_TIMEOUT_SECONDS:
                to_delete.append(phone)

        for phone in to_delete:
            print(f"🧹 Limpiando sesión inactiva por timeout: {phone}")
            clear_user_session(phone)

        time.sleep(60)
