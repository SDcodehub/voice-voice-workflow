"""Configuration for Voice Gateway Service."""

from pydantic_settings import BaseSettings
from functools import lru_cache


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""
    
    # Service settings
    service_name: str = "voice-gateway"
    service_host: str = "0.0.0.0"
    service_port: int = 8000
    debug: bool = False
    
    # Downstream services
    asr_service_host: str = "asr-service"
    asr_service_port: int = 50051
    
    llm_service_host: str = "llm-service"
    llm_service_port: int = 50052
    
    tts_service_host: str = "tts-service"
    tts_service_port: int = 50053
    
    # Redis settings
    redis_host: str = "redis"
    redis_port: int = 6379
    redis_db: int = 0
    redis_password: str = ""
    
    # Session settings
    session_timeout_seconds: int = 3600
    max_concurrent_sessions: int = 10000
    
    # Audio settings
    audio_sample_rate: int = 16000
    audio_channels: int = 1
    audio_chunk_size: int = 4096
    
    # Language settings
    default_language: str = "hi-IN"
    supported_languages: list[str] = ["hi-IN", "en-US"]
    
    # Observability
    otlp_endpoint: str = "http://otel-collector:4317"
    enable_tracing: bool = True
    
    class Config:
        env_prefix = "GATEWAY_"
        case_sensitive = False


@lru_cache()
def get_settings() -> Settings:
    """Get cached settings instance."""
    return Settings()

