#!/bin/bash
# scripts/dev.sh — Start both backend and frontend for development

set -e

echo "Starting Etsy Listing Agent Web App..."

# Start backend
echo "[Backend] Starting FastAPI on :8000..."
cd "$(dirname "$0")/../backend"
uv run uvicorn app.main:app --reload --port 8000 &
BACKEND_PID=$!

# Start frontend
echo "[Frontend] Starting Next.js on :3000..."
cd "$(dirname "$0")/../frontend"
npm run dev &
FRONTEND_PID=$!

echo ""
echo "Backend:  http://localhost:8000"
echo "Frontend: http://localhost:3000"
echo "API docs: http://localhost:8000/docs"
echo ""
echo "Press Ctrl+C to stop both servers."

# Cleanup on exit
trap "kill $BACKEND_PID $FRONTEND_PID 2>/dev/null" EXIT
wait
