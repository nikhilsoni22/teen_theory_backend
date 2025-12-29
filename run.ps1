# Teen Theory Backend Startup Script
Write-Host "Starting Teen Theory Backend..." -ForegroundColor Green

# Activate virtual environment and run the server
& "E:/Nikhil Soni/teen_theory_backend/.venv/Scripts/python.exe" -m uvicorn main:app --reload --host 0.0.0.0 --port 8000
