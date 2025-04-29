from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    openai_api_key: str
    twilio_account_sid: str
    twilio_auth_token: str
    twilio_whatsapp_number: str

    class Config:
        env_file = ".env"


settings = Settings()
