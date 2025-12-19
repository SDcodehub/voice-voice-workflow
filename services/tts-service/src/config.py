"""Configuration for TTS Service."""

from pydantic_settings import BaseSettings
from functools import lru_cache


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""
    
    # Service settings
    service_name: str = "tts-service"
    service_host: str = "0.0.0.0"
    service_port: int = 50053
    http_port: int = 8003
    debug: bool = False
    
    # Riva TTS settings
    riva_server_url: str = "riva-server:50051"
    riva_use_ssl: bool = False
    riva_ssl_cert: str = ""
    
    # Hindi TTS model configuration
    # Model: FastPitch-based Hindi TTS
    tts_language_code: str = "hi-IN"
    tts_voice_name: str = ""  # Use default voice for language
    
    # Audio output settings
    tts_sample_rate: int = 22050
    tts_encoding: str = "LINEAR_PCM"  # PCM audio
    
    # TTS quality settings
    # Higher values = better quality, slower generation
    tts_quality: int = 20  # Range: 1-40
    
    # Connection pool
    grpc_pool_size: int = 10
    grpc_max_message_size: int = 10 * 1024 * 1024  # 10MB
    
    # Streaming settings
    streaming_chunk_size: int = 4096
    
    # Observability
    otlp_endpoint: str = "http://otel-collector:4317"
    enable_tracing: bool = True
    
    class Config:
        env_prefix = "TTS_"
        case_sensitive = False


@lru_cache()
def get_settings() -> Settings:
    """Get cached settings instance."""
    return Settings()

