@echo off
REM Lancement du Dashboard Streamlit - Quantum Trader
echo.
echo ========================================
echo   Quantum Trader - Dashboard Streamlit
echo ========================================
echo.
echo Demarrage du dashboard...
echo.

REM Lancer Streamlit
uv run streamlit run dashboard_app.py --server.port 8501

pause
