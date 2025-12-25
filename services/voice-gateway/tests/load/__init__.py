"""
Voice Gateway Load Testing Framework
====================================

A comprehensive load testing tool for the voice-to-voice AI pipeline.
Supports concurrent users, multiple test scenarios, and detailed metrics collection.

Architecture:
    ┌─────────────────────────────────────────────────────┐
    │              LoadTestRunner                          │
    │  ┌─────────┐ ┌─────────┐ ┌─────────┐               │
    │  │Worker 1 │ │Worker 2 │ │Worker N │  (asyncio)    │
    │  └────┬────┘ └────┬────┘ └────┬────┘               │
    │       └───────────┼───────────┘                     │
    │                   │                                  │
    │           ┌───────┴───────┐                         │
    │           │   AudioPool   │                         │
    │           │  (WAV files)  │                         │
    │           └───────────────┘                         │
    └─────────────────────────────────────────────────────┘
                        │
                        ▼ gRPC BiDi Stream
    ┌─────────────────────────────────────────────────────┐
    │              Voice Gateway                           │
    │         (instrumented with metrics.py)               │
    └─────────────────────────────────────────────────────┘
                        │
                        ▼ Prometheus Scrape
    ┌─────────────────────────────────────────────────────┐
    │              Grafana Dashboard                       │
    │         (voice-gateway-dashboard.json)               │
    └─────────────────────────────────────────────────────┘

Usage:
    # CLI (recommended)
    cd services/voice-gateway/tests/load
    python load_test.py --scenario baseline --audio-dir ./test_audio
    
    # Programmatic
    from load import LoadTestConfig, LoadTestRunner, TestScenario
    
    config = LoadTestConfig.from_scenario(TestScenario.MEDIUM)
    runner = LoadTestRunner(config)
    collector = await runner.run()
    report = collector.generate_report()

Scenarios:
    - baseline:   1 user, 10 requests (establish latency baseline)
    - light:      5 users, 2 minutes (normal operation)
    - medium:    20 users, 5 minutes (typical peak)
    - heavy:     50 users, 5 minutes (stress test)
    - spike:    100 users, sudden burst
    - endurance: 20 users, 30 minutes (stability test)

Requirements:
    - Test audio files (16kHz WAV) in audio_dir
    - Voice gateway running and accessible
    - Prometheus + Grafana for visualization (optional but recommended)
"""

from .config import LoadTestConfig, TestScenario
from .audio_pool import AudioPool, AudioFile, SelectionStrategy, create_test_audio
from .collector import ResultsCollector, RequestResult, AggregateStats
from .worker import VoiceWorker, WorkerConfig
from .runner import LoadTestRunner, run_load_test

__version__ = "1.0.0"

__all__ = [
    # Config
    "LoadTestConfig",
    "TestScenario",
    # Audio
    "AudioPool",
    "AudioFile", 
    "SelectionStrategy",
    "create_test_audio",
    # Collector
    "ResultsCollector",
    "RequestResult",
    "AggregateStats",
    # Worker
    "VoiceWorker",
    "WorkerConfig",
    # Runner
    "LoadTestRunner",
    "run_load_test",
]

