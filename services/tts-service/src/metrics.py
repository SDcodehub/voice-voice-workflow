"""Prometheus metrics for TTS service - defined once to avoid duplicate registration."""
from prometheus_client import Counter, Histogram

TTS_REQUESTS = Counter(
    'tts_service_requests',
    'Total TTS requests',
    ['language', 'status']
)
TTS_LATENCY = Histogram(
    'tts_service_latency_seconds',
    'TTS synthesis latency',
    ['language'],
    buckets=[0.1, 0.25, 0.5, 1.0, 2.0, 5.0]
)
TTS_AUDIO_DURATION = Histogram(
    'tts_service_audio_duration_seconds',
    'Duration of audio generated',
    buckets=[1, 2, 5, 10, 30, 60]
)
TTS_TEXT_LENGTH = Histogram(
    'tts_service_text_length_chars',
    'Length of text synthesized',
    buckets=[10, 50, 100, 200, 500, 1000]
)

