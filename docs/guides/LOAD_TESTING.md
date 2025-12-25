# Load Testing Guide

End-to-end load testing for the Voice Gateway pipeline.

## Architecture

```
┌──────────────────────────────────────────────────────────────────────────────┐
│                           LOAD TEST FRAMEWORK                                 │
├──────────────────────────────────────────────────────────────────────────────┤
│                                                                               │
│   ┌─────────────────┐     ┌─────────────────┐     ┌─────────────────┐        │
│   │  LoadTestConfig │     │   AudioPool     │     │ ResultsCollector│        │
│   │  (scenarios)    │     │ (WAV files)     │     │ (metrics)       │        │
│   └─────────────────┘     └─────────────────┘     └─────────────────┘        │
│           │                       │                       ▲                   │
│           ▼                       ▼                       │                   │
│   ┌───────────────────────────────────────────────────────┴───────────────┐  │
│   │                      LoadTestRunner (asyncio)                          │  │
│   │   ┌───────────┐  ┌───────────┐  ┌───────────┐       ┌───────────┐     │  │
│   │   │ Worker 1  │  │ Worker 2  │  │ Worker 3  │  ...  │ Worker N  │     │  │
│   │   └─────┬─────┘  └─────┬─────┘  └─────┬─────┘       └─────┬─────┘     │  │
│   │         └──────────────┴──────────────┴───────────────────┘           │  │
│   └───────────────────────────────────────────────────────────────────────┘  │
│                                        │                                      │
└────────────────────────────────────────┼──────────────────────────────────────┘
                                         │ gRPC BiDi Stream
                                         ▼
                              ┌────────────────────┐
                              │  Voice Gateway     │
                              │  (port 50051)      │
                              └────────────────────┘
                                         │
                              Prometheus metrics (port 8080)
                                         │
                                         ▼
                              ┌────────────────────┐
                              │  Grafana Dashboard │
                              │  "Load Testing"    │
                              └────────────────────┘
```

## Quick Start

### 1. Prepare Test Audio

Create a directory with 16kHz WAV files:

```bash
mkdir -p ~/voice-voice-workflow/services/voice-gateway/tests/load/test_audio
cd ~/voice-voice-workflow/services/voice-gateway/tests/load

# Option A: Create silence for testing
python load_test.py --create-test-audio --audio-dir ./test_audio

# Option B: Copy real audio files (recommended for accurate testing)
cp /path/to/your/test-queries/*.wav ./test_audio/
```

### 2. Setup Port Forwarding

```bash
# On the server (headnode)
kubectl port-forward -n voice-workflow svc/voice-gateway-gateway 50051:50051 --address 0.0.0.0
```

### 3. Run Load Test

```bash
cd ~/voice-voice-workflow/services/voice-gateway/tests/load

# Baseline test (1 user)
python load_test.py --scenario baseline --audio-dir ./test_audio

# Light load (5 users)
python load_test.py --scenario light --audio-dir ./test_audio

# Medium load (20 users)
python load_test.py --scenario medium --audio-dir ./test_audio --output results.json

# Heavy load (50 users)
python load_test.py --scenario heavy --audio-dir ./test_audio -v
```

## Test Scenarios

| Scenario | Users | Ramp Up | Hold | Purpose |
|----------|-------|---------|------|---------|
| `baseline` | 1 | 0s | 30s | Establish latency baseline |
| `light` | 5 | 10s | 2min | Normal operation |
| `medium` | 20 | 30s | 5min | Typical peak load |
| `heavy` | 50 | 60s | 5min | Stress test |
| `spike` | 100 | 5s | 30s | Sudden burst |
| `endurance` | 20 | 30s | 30min | Stability test |

## Custom Configuration

```bash
# Custom user count and duration
python load_test.py --users 30 --duration 180 --ramp-up 60 --audio-dir ./test_audio

# With output files
python load_test.py --scenario medium \
    --audio-dir ./test_audio \
    --output report.json \
    --output-raw raw_results.json \
    -v
```

## CLI Options

```
--target, -t        Target URL (default: localhost:50051)
--audio-dir, -a     Directory with test WAV files
--scenario, -s      Predefined scenario (baseline/light/medium/heavy/spike/endurance)
--users, -u         Max concurrent users (overrides scenario)
--duration, -d      Hold duration in seconds
--ramp-up           Ramp up time in seconds
--ramp-down         Ramp down time in seconds
--think-time        Pause between requests per user (default: 1s)
--output, -o        JSON report output file
--output-raw        Raw results output file
--verbose, -v       Verbose output
--debug             Debug output
```

## Metrics & Visualization

### Grafana Dashboard

The load test results are automatically visible in the Grafana dashboard:

1. Access Grafana (see [OBSERVABILITY.md](./OBSERVABILITY.md))
2. Open "Voice Gateway Performance" dashboard
3. Scroll to "Load Testing" section

Key panels:
- **Concurrent Users Over Time**: Shows ramp-up/down pattern
- **Throughput (Requests/min)**: Request rate over time
- **Latency vs Load**: Correlation between users and latency
- **Latency Distribution**: Requests by latency bucket

### Interpreting Results

**Good Results:**
- P95 latency < 3s
- Error rate < 1%
- Latency doesn't spike with more users
- GPU utilization < 90%

**Warning Signs:**
- Latency increases linearly with users → GPU bottleneck
- Error rate spikes → Memory/connection limits
- P99 >> P95 → Outlier issues

## Programmatic Usage

```python
import asyncio
from load import LoadTestConfig, LoadTestRunner, TestScenario

async def main():
    # Use predefined scenario
    config = LoadTestConfig.from_scenario(
        TestScenario.MEDIUM,
        target_url="localhost:50051",
        audio_dir="./test_audio",
    )
    
    # Or custom config
    config = LoadTestConfig(
        target_url="localhost:50051",
        audio_dir="./test_audio",
        max_users=25,
        ramp_up_time=30,
        hold_time=120,
        think_time=2.0,
    )
    
    # Run test
    runner = LoadTestRunner(config)
    collector = await runner.run()
    
    # Get report
    report = collector.generate_report()
    print(f"Success rate: {report['summary']['success_rate']*100:.1f}%")
    print(f"P95 latency: {report['latency']['e2e']['p95']*1000:.0f}ms")
    
    # Save results
    collector.save_report("report.json", config.to_dict())

asyncio.run(main())
```

## Creating Test Audio

For accurate testing, use real voice queries:

```bash
# Record with Mac
# 1. Open QuickTime Player
# 2. File > New Audio Recording
# 3. Record your query
# 4. Export as WAV (16kHz, mono, 16-bit)

# Convert existing audio to correct format
ffmpeg -i input.mp3 -ar 16000 -ac 1 -acodec pcm_s16le output.wav
```

Test audio recommendations:
- **Short queries** (1-3s): "What time is it?"
- **Medium queries** (3-10s): Technical questions
- **Long queries** (10s+): Detailed requests

## Troubleshooting

### "No WAV files found"
```bash
# Check audio directory
ls -la ./test_audio/*.wav

# Create test audio
python load_test.py --create-test-audio --audio-dir ./test_audio
```

### "Connection refused"
```bash
# Verify port forwarding
kubectl port-forward -n voice-workflow svc/voice-gateway-gateway 50051:50051 --address 0.0.0.0

# Check service
kubectl get svc -n voice-workflow
```

### "Sample rate mismatch"
```bash
# Check file sample rate
ffprobe test.wav 2>&1 | grep "Stream"

# Convert to 16kHz
ffmpeg -i test.wav -ar 16000 test_16k.wav
```

### High error rates
```bash
# Check gateway logs
kubectl logs -n voice-workflow deploy/voice-gateway-gateway -f

# Check GPU memory
kubectl exec -n voice-workflow deploy/voice-gateway-gateway -- nvidia-smi
```

## Best Practices

1. **Baseline First**: Always run baseline before load tests
2. **Realistic Audio**: Use real voice queries, not silence
3. **Monitor GPU**: Watch GPU utilization during tests
4. **Gradual Increase**: Start with light load, increase gradually
5. **Multiple Runs**: Run each scenario 2-3 times for consistency
6. **Cool Down**: Wait 1-2 minutes between heavy tests
