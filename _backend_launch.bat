@echo off
cd /d "D:\Downloads\DND\"
"D:\Downloads\DND\.venv\Scripts\python.exe" -m uvicorn backend.main:app --host 127.0.0.1 --port 8000
