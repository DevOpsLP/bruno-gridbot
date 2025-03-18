#!/bin/bash
echo "Stopping FastAPI..."
pkill -f "uvicorn main:app"
sleep 2
echo "Restarting FastAPI..."
nohup bash -c 'source venv/bin/activate && PYTHONPATH=src venv/bin/uvicorn main:app --host 0.0.0.0 --port 8000 --reload' > fastapi.log 2>&1 &
echo "FastAPI restarted successfully!"