#!/usr/bin/env bash
# Ubuntu / Linux / macOS Quick Setup Script for Predictive Supplier Risk Intelligence
set -euo pipefail

echo "=== 1. Setting up Python Virtual Environment & Backend Dependencies ==="
cd "$(dirname "$0")/.."
python3 -m venv .venv
source .venv/bin/activate
pip install --upgrade pip
pip install -r backend/requirements.txt

echo "=== 2. Initializing Database, Seeding Dataset & Training ML Pipeline ==="
cd backend
python3 -m app.cli bootstrap-all
cd ..

echo "=== 3. Installing Frontend Dependencies ==="
cd frontend
npm install
cd ..

echo "=== Setup Complete! ==="
echo "To start Backend:  cd backend && ../.venv/bin/uvicorn app.main:app --host 0.0.0.0 --port 8000"
echo "To start Frontend: cd frontend && npm run dev"
