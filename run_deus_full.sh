#!/bin/bash
# Launch DEUS Eye with Full Voice Interface
cd "$(dirname "$0")"

# Load environment variables from .env if present
if [ -f .env ]; then
    set -a
    source .env
    set +a
fi

DEUS_VPS_HOST="${DEUS_VPS_HOST:?Error: DEUS_VPS_HOST not set. Copy .env.example to .env and fill in your values.}"
DEUS_SSH_TUNNEL_PORT="${DEUS_SSH_TUNNEL_PORT:-18790}"

echo "=================================="
echo "  Starting DEUS Eye + Voice"
echo "=================================="
echo ""

# Check if SSH tunnel is already running
if ! pgrep -f "ssh.*${DEUS_SSH_TUNNEL_PORT}.*${DEUS_VPS_HOST}" > /dev/null; then
    echo "Starting SSH tunnel..."
    ssh -f -N -L "${DEUS_SSH_TUNNEL_PORT}:127.0.0.1:18789" "root@${DEUS_VPS_HOST}"
    sleep 2
    echo "SSH tunnel connected"
else
    echo "SSH tunnel already running"
fi

# Activate virtual environment
source deus_venv/bin/activate

# Kill any existing DEUS Eye
pkill -f deus_eye.py 2>/dev/null

# Start DEUS Eye animation in background
echo "Starting DEUS Eye animation..."
python deus_eye.py &
EYE_PID=$!

# Give the eye time to load frames
echo "  Loading frames..."
sleep 5
echo "DEUS Eye running"
echo ""

# Start full voice interface
echo "Starting voice interface..."
echo ""
python deus_voice_full.py

# Cleanup
echo ""
echo "Stopping DEUS Eye..."
kill $EYE_PID 2>/dev/null
echo "Done."
