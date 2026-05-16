#!/bin/bash
cd "$(dirname "$0")"

# Start Phoenix-Evo Dashboard on port 18766
echo "Starting Phoenix-Evo Dashboard on port 18766..."
nohup python -m uvicorn dashboard:app --host 0.0.0.0 --port 18766 > dashboard.log 2>&1 &
DASHBOARD_PID=$!
echo "Dashboard started with PID: $DASHBOARD_PID"

# Start AutoSynth-Bridge on port 18765
echo "Starting AutoSynth-Bridge on port 18765..."
nohup python -m uvicorn bridge:app --host 0.0.0.0 --port 18765 > bridge.log 2>&1 &
BRIDGE_PID=$!
echo "Bridge started with PID: $BRIDGE_PID"

echo "Phoenix-Evo services started."
echo "Dashboard: http://localhost:18766"
echo "Bridge: http://localhost:18765"
