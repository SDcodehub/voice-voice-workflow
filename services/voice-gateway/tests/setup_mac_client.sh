#!/bin/bash
# setup_mac_client.sh
# Run this on your Mac to set up the Voice Workflow Client

set -e

echo "🎤 Setting up Voice Workflow Client on Mac..."

# 1. Check/Install uv
if ! command -v uv &> /dev/null; then
    echo "📦 Installing uv (Python package manager)..."
    curl -LsSf https://astral.sh/uv/install.sh | sh
    source $HOME/.cargo/env 2>/dev/null || true # Attempt to source env if possible, user might need to restart shell
    export PATH="$HOME/.cargo/bin:$PATH" # Temporary PATH update
fi

echo "✅ uv is ready."

# 2. Check/Install PortAudio (Required for PyAudio on Mac)
if ! command -v brew &> /dev/null; then
    echo "⚠️  Homebrew not found. Please ensure 'portaudio' is installed manually if PyAudio fails."
else
    if ! brew list portaudio &> /dev/null; then
        echo "🍺 Installing portaudio via Homebrew..."
        brew install portaudio
    fi
fi

# 3. Create Project Directory
mkdir -p voice-client
cd voice-client

# 4. Download Files (Using scp from the remote server if ssh is configured, else assume files are present or user copies them)
# For this script to be "one-click", we ideally need the files.
# Since we are generating this script on the server, the user will likely copy-paste it or download it.
# We will assume they download the proto/client script alongside this.

if [ ! -f "voice_workflow.proto" ]; then
    echo "⚠️  'voice_workflow.proto' not found in current directory."
    echo "    Please copy it from the server: scp sagdesai@10.41.88.111:~/voice-voice-workflow/proto/voice_workflow.proto ."
fi

if [ ! -f "test_mic_client.py" ]; then
    echo "⚠️  'test_mic_client.py' not found in current directory."
    echo "    Please copy it from the server: scp sagdesai@10.41.88.111:~/voice-voice-workflow/services/voice-gateway/tests/test_mic_client.py ."
fi

# 5. Initialize uv project (ephemeral)
echo "🚀 Initializing Python environment..."
uv init --app --no-workspace --name voice-client . 2>/dev/null || true

# 6. Add Dependencies
echo "📦 Adding dependencies..."
uv add grpcio grpcio-tools pyaudio

# 7. Generate Proto Code
echo "🛠️  Generating gRPC code..."
uv run python -m grpc_tools.protoc -I. --python_out=. --grpc_python_out=. voice_workflow.proto

echo "✅ Setup Complete!"
echo ""
echo "To run the client:"
echo "  uv run test_mic_client.py"
echo ""
echo "Make sure your SSH tunnel is running in another terminal:"
echo "  ssh -L 50051:localhost:50051 sagdesai@10.41.88.111"

