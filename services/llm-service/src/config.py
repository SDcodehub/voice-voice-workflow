"""Configuration for LLM Service."""

from pydantic_settings import BaseSettings
from functools import lru_cache


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""
    
    # Service settings
    service_name: str = "llm-service"
    service_host: str = "0.0.0.0"
    service_port: int = 50052
    http_port: int = 8002
    debug: bool = False
    
    # LLM Backend settings
    # Supports: nvidia_nim, openai, vllm, tgi
    llm_backend: str = "nvidia_nim"
    
    # NVIDIA NIM settings (recommended for production)
    nim_api_url: str = "http://nim-llm:8000/v1"
    nim_api_key: str = ""
    nim_model: str = "meta/llama-3.1-8b-instruct"
    
    # OpenAI-compatible settings (fallback)
    openai_api_url: str = "http://vllm:8000/v1"
    openai_api_key: str = ""
    openai_model: str = "meta-llama/Llama-3.1-8B-Instruct"
    
    # Generation settings
    max_tokens: int = 512
    temperature: float = 0.7
    top_p: float = 0.9
    frequency_penalty: float = 0.0
    presence_penalty: float = 0.0
    
    # Conversation settings
    max_history_turns: int = 10
    system_prompt_hindi: str = """आप एक सहायक AI असिस्टेंट हैं जो हिंदी में बात करते हैं। 
आप संक्षिप्त, सटीक और मददगार जवाब देते हैं। 
कृपया अपने जवाब को बातचीत के लिए उपयुक्त रखें - बहुत लंबा नहीं।
अगर उपयोगकर्ता अंग्रेजी में बात करें तो आप अंग्रेजी में जवाब दे सकते हैं।"""
    
    system_prompt_english: str = """You are a helpful AI assistant that communicates naturally.
You provide concise, accurate, and helpful responses.
Keep your responses conversational and not too long.
If the user speaks in Hindi, respond in Hindi."""
    
    # Redis cache settings
    redis_host: str = "redis"
    redis_port: int = 6379
    redis_db: int = 1
    cache_ttl_seconds: int = 3600
    enable_cache: bool = True
    
    # Rate limiting
    max_requests_per_minute: int = 100
    
    # Observability
    otlp_endpoint: str = "http://otel-collector:4317"
    enable_tracing: bool = True
    
    class Config:
        env_prefix = "LLM_"
        case_sensitive = False


@lru_cache()
def get_settings() -> Settings:
    """Get cached settings instance."""
    return Settings()

