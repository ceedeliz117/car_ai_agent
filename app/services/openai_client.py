import json
import os

import openai

from app.services.tools import (
    get_car_details_by_index,
    get_user_preferences,
    process_plate_or_fine_intent,
    search_catalog_car,
    simulate_financing,
)


class OpenAIClientService:
    def __init__(self):
        api_key = os.getenv("OPENAI_API_KEY")
        if not api_key:
            raise ValueError(
                "La variable de entorno OPENAI_API_KEY no está configurada."
            )
        openai.api_key = api_key

    def ask(
        self, session_id: str, user_message: str, context: str, conv_manager
    ) -> str:
        conv_manager.add_message(session_id, "user", user_message)

        messages = (
            [
                {"role": "system", "content": context},
            ]
            + conv_manager.get_history(session_id)
            + [{"role": "user", "content": user_message}]
        )

        functions = [
            {
                "name": "process_plate_or_fine_intent",
                "description": "Consulta las multas de una placa de auto",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "plate": {
                            "type": "string",
                            "description": "Placa del auto. Ejemplo: ABC123 o PAH1313",
                        },
                        "phone": {
                            "type": "string",
                            "description": "Número del usuario en WhatsApp",
                        },
                    },
                    "required": ["plate", "phone"],
                },
            },
            {
                "name": "search_catalog_car",
                "description": "Busca autos disponibles en el catálogo aplicando uno o varios filtros. Se puede filtrar por marca, modelo, año, precio, dimensiones u otras características si están en el catálogo.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "phone": {
                            "type": "string",
                            "description": "Número del usuario en WhatsApp para asociar los resultados",
                        }
                    },
                    "additionalProperties": True,
                },
            },
            {
                "name": "get_car_details_by_index",
                "description": "Devuelve detalles completos de un auto previamente listado, usando su número en la lista",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "index": {
                            "type": "integer",
                            "description": "Número del auto mostrado en la lista (ej. 1 para el primero)",
                        },
                        "phone": {
                            "type": "string",
                            "description": "Número del usuario en WhatsApp",
                        },
                    },
                    "required": ["index", "phone"],
                },
            },
            {
                "name": "simulate_financing",
                "description": "Simula un financiamiento para un auto. Si no se indica el precio, se usará el del auto seleccionado previamente.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "price": {
                            "type": "number",
                            "description": "Precio del auto (MXN)",
                        },
                        "downpayment": {
                            "type": "number",
                            "description": "Enganche proporcionado (MXN)",
                        },
                        "months": {
                            "type": "integer",
                            "description": "Plazo del crédito en meses (36, 48, 60)",
                        },
                        "phone": {
                            "type": "string",
                            "description": "Número del usuario de WhatsApp (para recuperar el auto seleccionado)",
                        },
                    },
                },
            },
            {
                "name": "get_user_preferences",
                "description": "Pregunta al usuario sus preferencias generales antes de recomendar autos.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "phone": {"type": "string", "description": "Número del usuario"}
                    },
                    "required": ["phone"],
                },
            },
        ]

        response = openai.ChatCompletion.create(
            model="gpt-4o", messages=messages, functions=functions, function_call="auto"
        )

        message = response.choices[0].message
        print("📥 Mensaje completo del modelo:", message)

        if message.get("function_call"):
            name = message["function_call"]["name"]
            args = json.loads(message["function_call"]["arguments"])

            # Ejecutar la función real
            if name == "search_catalog_car":
                args["phone"] = session_id
                data = search_catalog_car(**args)

            elif name == "simulate_financing":
                args["phone"] = session_id
                data = simulate_financing(conv_manager=conv_manager, **args)

                if "error" in data:
                    error_map = {
                        "MISSING_PRICE": "❌ No tengo el precio del auto. Por favor selecciona un auto antes de simular el financiamiento.",
                        "MISSING_DOWNPAYMENT": f"¿Con cuánto quieres iniciar como enganche? El mínimo es el 10% del valor del auto (al menos ${data.get('min_downpayment', 0):,} MXN).",
                        "DOWNPAYMENT_TOO_LOW": f"❌ El enganche es muy bajo. El mínimo es ${data.get('min_downpayment', 0):,} MXN.",
                        "DOWNPAYMENT_TOO_HIGH": f"❌ El enganche es muy alto. El máximo es ${data.get('max_downpayment', 0):,} MXN.",
                        "MISSING_MONTHS": "¿A cuántos meses te gustaría financiarlo? Por ejemplo, puedes elegir 36, 48 o 60 meses.",
                    }
                    return error_map.get(
                        data["error"], "❌ Hubo un error en la simulación."
                    )

            elif name == "get_car_details_by_index":
                args["phone"] = session_id
                data = get_car_details_by_index(
                    index=args["index"], phone=args["phone"]
                )

                if "error" in data:
                    if data["error"] == "NO_SEARCH_RESULTS":
                        return "❌ No tengo autos recientes para mostrar. Primero realiza una búsqueda."
                    elif data["error"] == "INVALID_INDEX":
                        return f"❌ El número que seleccionaste no es válido. Hay {data['available_range']} autos en la lista."

                conv_manager.set_attribute(session_id, "selected_car", data)

            elif name == "get_user_preferences":
                data = get_user_preferences(phone=session_id)

            elif name == "process_plate_or_fine_intent":
                plate = args.get("placa") or args.get("plate")
                phone = args.get("telefono") or args.get("phone")
                conv_manager.add_message(
                    session_id,
                    "assistant",
                    f"[invocando función consultar_multas para placa: {plate}]",
                )
                return process_plate_or_fine_intent(plate=plate, phone=phone)

            followup_messages = (
                [{"role": "system", "content": context}]
                + conv_manager.get_history(session_id)
                + [
                    {
                        "role": "assistant",
                        "tool_calls": [
                            {
                                "id": f"call_{name}",
                                "type": "function",
                                "function": {
                                    "name": name,
                                    "arguments": json.dumps(args),
                                },
                            }
                        ],
                    },
                    {
                        "role": "tool",
                        "tool_call_id": f"call_{name}",
                        "name": name,
                        "content": json.dumps(data),
                    },
                ]
            )

            response = openai.ChatCompletion.create(
                model="gpt-4o", messages=followup_messages
            )

            reply = response.choices[0].message["content"]
            conv_manager.add_message(session_id, "assistant", reply)
            return reply

        reply = message["content"]
        conv_manager.add_message(session_id, "assistant", reply)

        return reply
