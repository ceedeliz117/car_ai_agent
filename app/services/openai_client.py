import openai
import os

class OpenAIClientService:
    def __init__(self):
        api_key = os.getenv("OPENAI_API_KEY")
        if not api_key:
            raise ValueError("La variable de entorno OPENAI_API_KEY no está configurada.")
        openai.api_key = api_key

    def ask(self, user_message: str, context: str) -> str:
        try:
            response = openai.ChatCompletion.create(
                model="gpt-4o",  # Usamos GPT-4o como te pide el proyecto
                messages=[
                    {
                        "role": "system",
                        "content": (
                            "Eres un asesor experto de Kavak. Solo puedes responder usando "
                            "la siguiente información autorizada que representa los servicios de Kavak. "
                            "Si no encuentras la respuesta en el contexto, por favor indica que el usuario puede visitar kavak.com para más información.\n\n"
                            f"{context}"
                        )
                    },
                    {
                        "role": "user",
                        "content": user_message
                    }
                ],
                temperature=0.2,  # Respuestas más precisas y menos aleatorias
                max_tokens=500,   # Limitar la respuesta para WhatsApp
            )
            return response['choices'][0]['message']['content'].strip()
        except Exception as e:
            print(f"❌ Error consultando OpenAI: {e}")
            return "🚧 Lo siento, hubo un problema procesando tu solicitud en este momento."
