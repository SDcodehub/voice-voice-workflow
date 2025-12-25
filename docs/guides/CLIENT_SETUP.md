# Client Setup Guide

How to connect to the Voice Gateway from different clients.

## Mac Client (Development/Testing)

### Prerequisites

- Python 3.10+
- [uv](https://github.com/astral-sh/uv) package manager
- PortAudio (for PyAudio)

```bash
# Install uv
curl -LsSf https://astral.sh/uv/install.sh | sh

# Install PortAudio (macOS)
brew install portaudio
```

### Setup

**Step 1: Start Port-Forward on Server**

```bash
# On the server (headnode)
kubectl port-forward -n voice-workflow \
  svc/voice-gateway-gateway 50051:50051 \
  --address 0.0.0.0
```

**Step 2: SSH Tunnel from Mac**

```bash
# Terminal 1 on Mac - keep this running
ssh -L 50051:localhost:50051 user@server-ip
```

**Step 3: Setup Client Environment**

```bash
# Terminal 2 on Mac
mkdir -p ~/Desktop/voice-client && cd ~/Desktop/voice-client

# Copy files from server
scp user@server:~/voice-voice-workflow/proto/voice_workflow.proto .
scp user@server:~/voice-voice-workflow/services/voice-gateway/tests/test_mic_client.py .

# Initialize project
uv init --app --no-workspace --name voice-client .
uv add grpcio grpcio-tools pyaudio

# Generate proto
uv run python -m grpc_tools.protoc \
  -I. --python_out=. --grpc_python_out=. \
  voice_workflow.proto
```

**Step 4: Run Client**

```bash
uv run test_mic_client.py
```

### Using Headphones (Recommended)

To avoid echo/feedback loop, use headphones while testing. The microphone will pick up speaker output otherwise.

## Quick Reference

```bash
# Server
kubectl port-forward -n voice-workflow svc/voice-gateway-gateway 50051:50051 --address 0.0.0.0

# Mac Terminal 1
ssh -L 50051:localhost:50051 user@server

# Mac Terminal 2
cd ~/Desktop/voice-client
uv run test_mic_client.py
```

## Mobile Client (Future)

### iOS

```swift
// Use AVAudioSession with voice chat mode (AEC enabled)
let session = AVAudioSession.sharedInstance()
try session.setCategory(.playAndRecord, mode: .voiceChat)
try session.setActive(true)

// Connect to gRPC gateway
let channel = ClientConnection.insecure(group: group)
  .connect(host: "gateway.example.com", port: 50051)
```

### Android

```kotlin
// Use AudioManager in communication mode (AEC enabled)
val audioManager = getSystemService(AUDIO_SERVICE) as AudioManager
audioManager.mode = AudioManager.MODE_IN_COMMUNICATION

// Connect to gRPC gateway
val channel = ManagedChannelBuilder
  .forAddress("gateway.example.com", 50051)
  .usePlaintext()
  .build()
```

## Troubleshooting

### PyAudio Installation Fails

```bash
# macOS
brew install portaudio
pip install pyaudio

# Linux
sudo apt-get install portaudio19-dev
pip install pyaudio
```

### Connection Refused

1. Check port-forward is running on server
2. Check SSH tunnel is active
3. Verify gateway pod is Ready

```bash
kubectl get pods -n voice-workflow -l app=voice-gateway
```

### No Audio Output

1. Check system audio output device
2. Try different sample rate (16000 vs 22050)
3. Check TTS logs for errors

### Echo/Feedback Loop

**Symptom**: Assistant responds to its own voice

**Solutions**:
1. Use headphones (immediate fix)
2. Reduce speaker volume
3. Move mic away from speakers

See [ROADMAP.md](../ROADMAP.md) for future AEC implementation.

