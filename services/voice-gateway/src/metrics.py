"""
Prometheus metrics for Voice Gateway observability.

Design Principles:
1. ZERO LATENCY IMPACT - Metrics are stored in memory, not in request path
2. Separate HTTP server on port 8080 for /metrics endpoint
3. Pre-defined histogram buckets optimized for voice latency
4. Async-compatible context managers for timing

Usage:
    from metrics import METRICS, metrics_server
    
    # Start metrics server (separate from gRPC)
    await metrics_server.start()
    
    # Time operations
    with METRICS.asr_latency.time():
        result = await asr_client.transcribe(audio)
    
    # Or manually observe
    METRICS.asr_latency.observe(duration_seconds)
"""

import time
import logging
from contextlib import contextmanager
from typing import Optional
from prometheus_client import (
    Counter,
    Histogram,
    Gauge,
    Info,
    start_http_server,
    REGISTRY,
)

logger = logging.getLogger(__name__)

# =============================================================================
# Histogram Buckets (optimized for voice latency - seconds)
# =============================================================================
# Voice latency ranges:
#   - Excellent: < 200ms
#   - Good: 200-500ms
#   - Acceptable: 500ms-1s
#   - Poor: > 1s

# ASR buckets: typically 50ms - 2s for streaming transcription
ASR_LATENCY_BUCKETS = (0.05, 0.1, 0.2, 0.3, 0.5, 0.75, 1.0, 1.5, 2.0, 3.0, 5.0)

# LLM TTFT buckets: time to first token, typically 100ms - 2s
LLM_TTFT_BUCKETS = (0.1, 0.2, 0.3, 0.5, 0.75, 1.0, 1.5, 2.0, 3.0, 5.0)

# LLM total generation buckets: 500ms - 30s depending on response length
LLM_TOTAL_BUCKETS = (0.5, 1.0, 2.0, 3.0, 5.0, 7.5, 10.0, 15.0, 20.0, 30.0)

# TTS buckets: typically 50ms - 2s for synthesis
TTS_LATENCY_BUCKETS = (0.05, 0.1, 0.2, 0.3, 0.5, 0.75, 1.0, 1.5, 2.0, 3.0, 5.0)

# E2E buckets: full pipeline, typically 500ms - 10s
E2E_LATENCY_BUCKETS = (0.5, 1.0, 1.5, 2.0, 3.0, 5.0, 7.5, 10.0, 15.0, 20.0, 30.0)


# =============================================================================
# Metrics Definitions
# =============================================================================

class VoiceGatewayMetrics:
    """Container for all Voice Gateway metrics."""
    
    def __init__(self):
        # -------------------------------------------------------------------------
        # Latency Histograms
        # -------------------------------------------------------------------------
        
        # ASR (Speech-to-Text) latency
        self.asr_latency = Histogram(
            'voice_gateway_asr_latency_seconds',
            'ASR transcription latency (time from first audio chunk to final transcript)',
            ['language'],
            buckets=ASR_LATENCY_BUCKETS,
        )
        
        # LLM Time-to-First-Token (critical for perceived responsiveness)
        self.llm_ttft = Histogram(
            'voice_gateway_llm_ttft_seconds',
            'LLM time to first token (measures inference start latency)',
            ['model'],
            buckets=LLM_TTFT_BUCKETS,
        )
        
        # LLM Total Generation Time
        self.llm_total = Histogram(
            'voice_gateway_llm_total_seconds',
            'LLM total response generation time',
            ['model'],
            buckets=LLM_TOTAL_BUCKETS,
        )
        
        # LLM Token Count
        self.llm_tokens = Histogram(
            'voice_gateway_llm_tokens_total',
            'Number of tokens generated per LLM response',
            ['model'],
            buckets=(10, 25, 50, 100, 200, 500, 1000, 2000),
        )
        
        # TTS (Text-to-Speech) latency per sentence
        self.tts_latency = Histogram(
            'voice_gateway_tts_latency_seconds',
            'TTS synthesis latency per sentence',
            ['language'],
            buckets=TTS_LATENCY_BUCKETS,
        )
        
        # TTS characters processed
        self.tts_characters = Histogram(
            'voice_gateway_tts_characters_total',
            'Number of characters synthesized per TTS call',
            ['language'],
            buckets=(10, 25, 50, 100, 200, 500, 1000),
        )
        
        # End-to-End latency (user speaks -> first audio response)
        self.e2e_latency = Histogram(
            'voice_gateway_e2e_latency_seconds',
            'End-to-end latency from final ASR transcript to first TTS audio chunk',
            buckets=E2E_LATENCY_BUCKETS,
        )
        
        # -------------------------------------------------------------------------
        # Counters
        # -------------------------------------------------------------------------
        
        self.requests_total = Counter(
            'voice_gateway_requests_total',
            'Total number of voice requests processed',
            ['status'],  # success, error
        )
        
        self.asr_errors = Counter(
            'voice_gateway_asr_errors_total',
            'Total ASR errors',
            ['error_type'],
        )
        
        self.llm_errors = Counter(
            'voice_gateway_llm_errors_total',
            'Total LLM errors',
            ['error_type'],
        )
        
        self.tts_errors = Counter(
            'voice_gateway_tts_errors_total',
            'Total TTS errors',
            ['error_type'],
        )
        
        # -------------------------------------------------------------------------
        # Gauges
        # -------------------------------------------------------------------------
        
        self.active_streams = Gauge(
            'voice_gateway_active_streams',
            'Number of currently active voice streams',
        )
        
        # -------------------------------------------------------------------------
        # Info
        # -------------------------------------------------------------------------
        
        self.info = Info(
            'voice_gateway',
            'Voice Gateway service information',
        )
    
    def set_info(self, version: str, model: str, asr_lang: str):
        """Set service info labels."""
        self.info.info({
            'version': version,
            'llm_model': model,
            'asr_language': asr_lang,
        })


# =============================================================================
# Timer Context Managers (Zero-overhead timing)
# =============================================================================

class Timer:
    """
    Non-blocking timer for measuring operation latency.
    
    Usage:
        timer = Timer()
        timer.start()
        # ... do work ...
        timer.stop()
        METRICS.asr_latency.labels(language='en-US').observe(timer.duration)
    
    Or as context manager:
        with Timer() as t:
            # ... do work ...
        METRICS.asr_latency.labels(language='en-US').observe(t.duration)
    """
    
    def __init__(self):
        self.start_time: Optional[float] = None
        self.end_time: Optional[float] = None
    
    def start(self):
        self.start_time = time.perf_counter()
    
    def stop(self):
        self.end_time = time.perf_counter()
    
    @property
    def duration(self) -> float:
        """Returns duration in seconds."""
        if self.start_time is None:
            return 0.0
        end = self.end_time if self.end_time else time.perf_counter()
        return end - self.start_time
    
    def __enter__(self):
        self.start()
        return self
    
    def __exit__(self, *args):
        self.stop()


@contextmanager
def observe_latency(histogram, labels: dict = None):
    """
    Context manager for observing latency without blocking.
    
    Usage:
        with observe_latency(METRICS.asr_latency, {'language': 'en-US'}):
            result = await asr_client.transcribe(audio)
    """
    timer = Timer()
    timer.start()
    try:
        yield timer
    finally:
        timer.stop()
        if labels:
            histogram.labels(**labels).observe(timer.duration)
        else:
            histogram.observe(timer.duration)


# =============================================================================
# Metrics Server
# =============================================================================

class MetricsServer:
    """
    Manages the Prometheus metrics HTTP server.
    
    Runs on a SEPARATE port from gRPC to ensure zero impact on main flow.
    """
    
    def __init__(self, port: int = 8080):
        self.port = port
        self._started = False
    
    def start(self):
        """Start the metrics HTTP server (non-blocking, runs in background thread)."""
        if self._started:
            logger.warning("Metrics server already started")
            return
        
        try:
            start_http_server(self.port)
            self._started = True
            logger.info(f"Metrics server started on port {self.port}")
        except Exception as e:
            logger.error(f"Failed to start metrics server: {e}")
            raise


# =============================================================================
# Global Instances
# =============================================================================

# Single instance of metrics - import this in other modules
METRICS = VoiceGatewayMetrics()

# Metrics server instance
metrics_server = MetricsServer()


# =============================================================================
# Utility Functions
# =============================================================================

def get_metrics_text() -> str:
    """Get current metrics in Prometheus text format (for debugging)."""
    from prometheus_client import generate_latest
    return generate_latest(REGISTRY).decode('utf-8')

