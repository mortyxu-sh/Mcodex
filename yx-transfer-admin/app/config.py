from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    app_host: str = "0.0.0.0"
    app_port: int = 18098
    transfer_api_base: str = "http://127.0.0.1:8098"
    request_timeout: int = 15

    class Config:
        env_file = ".env"
        extra = "ignore"

settings = Settings()
