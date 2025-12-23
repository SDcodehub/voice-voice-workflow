"""
Voice-to-Voice Client Setup Instructions
=========================================
Last updated: 2025-12-23

This file documents how to reproduce the E2E testing setup.

=============================================================================
ARCHITECTURE
=============================================================================

    [Mac Client] <--SSH Tunnel--> [Headnode:50051] <--K8s Port-Forward--> [Gateway Pod]
                                                                              |
                                                      +----------+------------+----------+
                                                      |          |                       |
                                                  [Riva ASR]  [LLM NIM]             [Riva TTS]

=============================================================================
STEP 1: SERVER SETUP (on headnode: bcm10-headnode / 10.41.88.111)
=============================================================================

# Start kubectl port-forward (bind to 0.0.0.0 so SSH tunnel can access it)
kubectl port-forward -n voice-workflow svc/voice-gateway-gateway 50051:50051 --address 0.0.0.0

# Keep this running in a tmux/screen session or background:
# nohup kubectl port-forward -n voice-workflow svc/voice-gateway-gateway 50051:50051 --address 0.0.0.0 &

=============================================================================
STEP 2: MAC CLIENT SETUP (on your Mac)
=============================================================================

# Option A: Run the setup script (downloads files, installs deps, generates proto)
curl -s https://raw.githubusercontent.com/sagdesai/voice-voice-workflow/v2/services/voice-gateway/tests/setup_mac_client.sh | bash

# Option B: Manual setup
mkdir -p ~/Desktop/voice-client && cd ~/Desktop/voice-client

# Install uv if not present
curl -LsSf https://astral.sh/uv/install.sh | sh

# Install portaudio (required for PyAudio)
brew install portaudio

# Download files from server
scp sagdesai@10.41.88.111:~/voice-voice-workflow/proto/voice_workflow.proto .
scp sagdesai@10.41.88.111:~/voice-voice-workflow/services/voice-gateway/tests/test_mic_client.py .

# Initialize uv project and install dependencies
uv init --app --no-workspace --name voice-client .
uv add grpcio grpcio-tools pyaudio

# Generate proto code
uv run python -m grpc_tools.protoc -I. --python_out=. --grpc_python_out=. voice_workflow.proto

=============================================================================
STEP 3: RUN THE CLIENT
=============================================================================

# Terminal 1: Start SSH tunnel (keep this running)
ssh -L 50051:localhost:50051 sagdesai@10.41.88.111

# Terminal 2: Run the client
cd ~/Desktop/voice-client
uv run test_mic_client.py

# Speak into your microphone and listen for the AI response!

=============================================================================
CONFIGURATION VALUES
=============================================================================

SERVER_IP       = "10.41.88.111"
SERVER_USER     = "sagdesai"
GRPC_PORT       = 50051
K8S_NAMESPACE   = "voice-workflow"
K8S_SERVICE     = "voice-gateway-gateway"

ASR_LANGUAGE    = "en-US"
ASR_SAMPLE_RATE = 16000
LLM_MODEL       = "meta/llama-3.1-8b-instruct"
TTS_VOICE       = ""  # Default voice

=============================================================================
"""

if __name__ == "__main__":
    print(__doc__)

