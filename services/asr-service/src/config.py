"""Configuration for ASR Service."""

from pydantic_settings import BaseSettings
from functools import lru_cache


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""
    
    # Service settings
    service_name: str = "asr-service"
    service_host: str = "0.0.0.0"
    service_port: int = 50051
    http_port: int = 8001
    debug: bool = False
    
    # Riva ASR settings
    riva_server_url: str = "riva-server:50051"
    riva_use_ssl: bool = False
    riva_ssl_cert: str = ""
    
    # Hindi ASR model configuration
    # Model: Conformer-based Hindi ASR
    asr_language_code: str = "hi-IN"
    asr_model_name: str = ""  # Use default model for language
    asr_encoding: str = "LINEAR_PCM"  # PCM audio
    asr_sample_rate: int = 16000
    asr_audio_channel_count: int = 1
    
    # ASR options
    asr_enable_automatic_punctuation: bool = True
    asr_enable_word_time_offsets: bool = False
    asr_max_alternatives: int = 1
    asr_profanity_filter: bool = False
    asr_verbatim_transcripts: bool = True
    
    # Streaming settings
    streaming_interim_results: bool = True
    streaming_chunk_duration_ms: int = 100
    
    # Connection pool
    grpc_pool_size: int = 10
    grpc_max_message_size: int = 10 * 1024 * 1024  # 10MB
    
    # Observability
    otlp_endpoint: str = "http://otel-collector:4317"
    enable_tracing: bool = True
    
    class Config:
        env_prefix = "ASR_"
        case_sensitive = False


@lru_cache()
def get_settings() -> Settings:
    """Get cached settings instance."""
    return Settings()

