"""Prometheus metrics for ASR service - defined once to avoid duplicate registration."""
from prometheus_client import Counter, Histogram

ASR_REQUESTS = Counter(
    'asr_service_requests',
    'Total ASR requests',
    ['language', 'status']
)
ASR_LATENCY = Histogram(
    'asr_service_latency_seconds',
    'ASR processing latency',
    ['language'],
    buckets=[0.1, 0.25, 0.5, 1.0, 2.0, 5.0, 10.0]
)
ASR_AUDIO_DURATION = Histogram(
    'asr_service_audio_duration_seconds',
    'Duration of audio processed',
    buckets=[1, 2, 5, 10, 30, 60, 120]
)

