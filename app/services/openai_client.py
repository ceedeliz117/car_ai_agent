import json
import os

import openai

from app.services.tools import (
    get_car_details_by_index,
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
        ]

        response = openai.ChatCompletion.create(
            model="gpt-4o", messages=messages, functions=functions, function_call="auto"
        )

        message = response.choices[0].message
        print("📥 Mensaje completo del modelo:", message)

        if message.get("function_call"):
            name = message["function_call"]["name"]
            args = json.loads(message["function_call"]["arguments"])

            if name == "process_plate_or_fine_intent":
                print("🛠️ LLM está invocando tool: consultar_multas")
                plate = args.get("placa") or args.get("plate")
                phone = args.get("telefono") or args.get("phone")

                conv_manager.add_message(
                    session_id,
                    "assistant",
                    f"[invocando función consultar_multas para placa: {plate}]",
                )
                return process_plate_or_fine_intent(plate=plate, phone=phone)
            elif name == "search_catalog_car":
                args["phone"] = session_id
                reply = search_catalog_car(**args)
                conv_manager.add_message(session_id, "assistant", reply)
                return reply
            elif name == "get_car_details_by_index":
                if "index" not in args and user_message.lower().strip() in [
                    "sí",
                    "simúlalo",
                    "hazlo",
                    "vamos",
                    "ok",
                ]:
                    selected_car = conv_manager.get_attribute(
                        session_id, "selected_car"
                    )
                    if selected_car:
                        return simulate_financing(
                            conv_manager=conv_manager, phone=session_id
                        )

                args["phone"] = session_id
                selected_car = get_car_details_by_index(
                    index=args["index"], phone=args["phone"]
                )
                conv_manager.set_attribute(session_id, "selected_car", selected_car)
                conv_manager.add_message(session_id, "assistant", selected_car)
                return selected_car

            elif name == "simulate_financing":
                if "price" not in args:
                    selected_car = conv_manager.get_attribute(
                        session_id, "selected_car"
                    )
                    if selected_car:
                        args["price"] = selected_car.get("precio")

                args["phone"] = session_id
                reply = simulate_financing(conv_manager=conv_manager, **args)

                conv_manager.set_attribute(
                    session_id,
                    "last_financing",
                    {
                        "downpayment": args["downpayment"],
                        "months": args["months"],
                        "price": args["price"],
                    },
                )

                return reply

        reply = message["content"]
        conv_manager.add_message(session_id, "assistant", reply)

        return reply
