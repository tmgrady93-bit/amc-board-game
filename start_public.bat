@echo off
REM Helper to start Streamlit and ngrok for a quick public URL demo
setlocal

REM Start Streamlit in background
start "Streamlit" cmd /c "C:\GameDevelopment\BasicGameDev\App_Deployment\.venv\Scripts\python.exe -m streamlit run streamlit_app.py"

REM Wait a moment for Streamlit to start
timeout /t 3 /nobreak >nul

REM Start ngrok (assumes ngrok is in PATH)
start "ngrok" cmd /c "ngrok http 8501"

echo Started Streamlit and ngrok. Check the ngrok window for the public URL.
endlocal
