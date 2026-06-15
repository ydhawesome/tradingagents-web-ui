@echo off
chcp 65001 >nul
cd /d "%~dp0"
echo Starting TradingAgents Web UI...  http://localhost:8501
if exist ".venv\Scripts\streamlit.exe" (
    ".venv\Scripts\streamlit.exe" run app.py
) else (
    streamlit run app.py
)
pause
