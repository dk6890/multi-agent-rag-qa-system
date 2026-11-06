@echo off
setlocal
cd /d "%~dp0..\rag-python"
if exist ".venv\Scripts\python.exe" (
    ".venv\Scripts\python.exe" -m uvicorn app:app --host 127.0.0.1 --port 8000 > rag-python-run.log 2> rag-python-run.err.log
) else (
    python -m uvicorn app:app --host 127.0.0.1 --port 8000 > rag-python-run.log 2> rag-python-run.err.log
)
