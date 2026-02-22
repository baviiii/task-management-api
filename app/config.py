from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    DATABASE_URL: str = "postgresql+asyncpg://postgres:postgres@db:5432/taskdb"

    model_config = {"env_file": ".env", "env_file_encoding": "utf-8"}


settings = Settings()
