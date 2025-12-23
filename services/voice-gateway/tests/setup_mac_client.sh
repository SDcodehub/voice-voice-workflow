#!/bin/bash
# setup_mac_client.sh
# Run this on your Mac to set up the Voice Workflow Client
# Last updated: 2025-12-23

set -e

# =============================================================================
# CONFIGURATION - Update these for your environment
# =============================================================================
SERVER_IP="10.41.88.111"
SERVER_USER="sagdesai"
GRPC_PORT="50051"
PROJECT_DIR="$HOME/Desktop/voice-client"

# =============================================================================
# PREREQUISITES (Run on Server FIRST before running this script)
# =============================================================================
cat << 'EOF'
================================================================================
📋 STEP 0: SERVER-SIDE SETUP (Run on headnode FIRST)
================================================================================

SSH into the server and run these commands:

  # 1. Start port-forward from K8s to server (bind to 0.0.0.0 for SSH access)
  kubectl port-forward -n voice-workflow svc/voice-gateway-gateway 50051:50051 --address 0.0.0.0

  # Keep this running in a terminal or use tmux/screen

================================================================================
EOF

read -p "Have you started the port-forward on the server? (y/n) " -n 1 -r
echo
if [[ ! $REPLY =~ ^[Yy]$ ]]; then
    echo "Please start the port-forward on the server first, then re-run this script."
    exit 1
fi

echo ""
echo "🎤 Setting up Voice Workflow Client on Mac..."
echo ""

# =============================================================================
# STEP 1: Install uv (Python package manager)
# =============================================================================
if ! command -v uv &> /dev/null; then
    echo "📦 Installing uv (Python package manager)..."
    curl -LsSf https://astral.sh/uv/install.sh | sh
    source $HOME/.local/bin/env 2>/dev/null || true
    export PATH="$HOME/.local/bin:$PATH"
fi
echo "✅ uv is ready."

# =============================================================================
# STEP 2: Install PortAudio (Required for PyAudio on Mac)
# =============================================================================
if ! command -v brew &> /dev/null; then
    echo "⚠️  Homebrew not found. Install from https://brew.sh if PyAudio fails."
else
    if ! brew list portaudio &> /dev/null; then
        echo "🍺 Installing portaudio via Homebrew..."
        brew install portaudio
    fi
    echo "✅ portaudio is ready."
fi

# =============================================================================
# STEP 3: Create Project Directory
# =============================================================================
echo "📁 Creating project directory: $PROJECT_DIR"
mkdir -p "$PROJECT_DIR"
cd "$PROJECT_DIR"

# =============================================================================
# STEP 4: Download Files from Server
# =============================================================================
echo "📥 Downloading files from server..."

if [ ! -f "voice_workflow.proto" ]; then
    scp ${SERVER_USER}@${SERVER_IP}:~/voice-voice-workflow/proto/voice_workflow.proto . || {
        echo "❌ Failed to download proto file. Check SSH access."
        exit 1
    }
fi

if [ ! -f "test_mic_client.py" ]; then
    scp ${SERVER_USER}@${SERVER_IP}:~/voice-voice-workflow/services/voice-gateway/tests/test_mic_client.py . || {
        echo "❌ Failed to download client file. Check SSH access."
        exit 1
    }
fi

echo "✅ Files downloaded."

# =============================================================================
# STEP 5: Initialize uv project
# =============================================================================
echo "🚀 Initializing Python environment..."
if [ ! -f "pyproject.toml" ]; then
    uv init --app --no-workspace --name voice-client .
fi

# =============================================================================
# STEP 6: Add Dependencies
# =============================================================================
echo "📦 Adding dependencies..."
uv add grpcio grpcio-tools pyaudio

# =============================================================================
# STEP 7: Generate Proto Code
# =============================================================================
echo "🛠️  Generating gRPC code..."
uv run python -m grpc_tools.protoc -I. --python_out=. --grpc_python_out=. voice_workflow.proto

# =============================================================================
# DONE - Print Instructions
# =============================================================================
cat << EOF

================================================================================
✅ SETUP COMPLETE!
================================================================================

📁 Project location: $PROJECT_DIR

To test the voice-to-voice pipeline:

  1. Open a NEW terminal and start SSH tunnel:
     ssh -L ${GRPC_PORT}:localhost:${GRPC_PORT} ${SERVER_USER}@${SERVER_IP}

  2. In THIS terminal, run the client:
     cd $PROJECT_DIR
     uv run test_mic_client.py

  3. Speak into your microphone and listen for the response!

================================================================================
🔧 TROUBLESHOOTING
================================================================================

If connection fails:
  - Check SSH tunnel is running
  - Check port-forward is running on server:
    kubectl port-forward -n voice-workflow svc/voice-gateway-gateway 50051:50051 --address 0.0.0.0

If no audio input:
  - Grant microphone permission to Terminal in System Preferences

If no audio output:
  - Check speaker volume
  - Verify audio output device

================================================================================
EOF

