"""Prometheus metrics for LLM service - defined once to avoid duplicate registration."""
from prometheus_client import Counter, Histogram

LLM_REQUESTS = Counter(
    'llm_service_requests',
    'Total LLM requests',
    ['language', 'status', 'cached']
)
LLM_LATENCY = Histogram(
    'llm_service_latency_seconds',
    'LLM generation latency',
    ['language'],
    buckets=[0.5, 1.0, 2.0, 5.0, 10.0, 30.0]
)
LLM_TOKENS = Counter(
    'llm_service_tokens_generated',
    'Total tokens generated',
    ['language']
)

