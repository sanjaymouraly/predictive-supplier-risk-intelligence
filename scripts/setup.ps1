# Windows PowerShell Quick Setup Script for Predictive Supplier Risk Intelligence
$ErrorActionPreference = "Stop"

Write-Host "=== 1. Setting up Python Virtual Environment & Backend Dependencies ===" -ForegroundColor Cyan
Set-Location (Join-Path $PSScriptRoot "..")
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
pip install -r backend\requirements.txt

Write-Host "=== 2. Initializing Database, Seeding Dataset & Training ML Pipeline ===" -ForegroundColor Cyan
Set-Location backend
python -m app.cli bootstrap-all
Set-Location ..

Write-Host "=== 3. Installing Frontend Dependencies ===" -ForegroundColor Cyan
Set-Location frontend
npm install
Set-Location ..

Write-Host "=== Setup Complete! ===" -ForegroundColor Green
Write-Host "To start Backend:  cd backend; ..\.venv\Scripts\uvicorn app.main:app --host 0.0.0.0 --port 8000"
Write-Host "To start Frontend: cd frontend; npm run dev"
