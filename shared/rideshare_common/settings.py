from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    service_name: str = "rideshare-service"
    service_port: int = 8500
    environment: str = "dev"

    postgres_dsn: str = "postgresql+psycopg://rideshare:rideshare@postgres:5432/rideshare"
    redis_url: str = "redis://redis:6379/0"
    rabbitmq_url: str = "amqp://guest:guest@rabbitmq:5672/"

    maps_provider_url: str = "https://www.openstreetmap.org"
    mapbox_api_base: str = "https://api.mapbox.com"

    jwt_secret: str = "rideshare-dev-secret"
    encryption_key: str = "rideshare-dev-encryption-key"

    payment_commission_rate: float = 0.1
    search_target_seconds: float = 2.0
    booking_target_seconds: float = 5.0
    daily_capacity_target: int = 100000

    trip_service_url: str = "http://trip-service:8501"
    search_service_url: str = "http://search-service:8502"
    booking_service_url: str = "http://booking-service:8503"
    payment_service_url: str = "http://payment-service:8504"
    rating_service_url: str = "http://rating-service:8505"
    verification_service_url: str = "http://verification-service:8506"
    chat_service_url: str = "http://chat-service:8507"
    notification_service_url: str = "http://notification-service:8508"

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()
