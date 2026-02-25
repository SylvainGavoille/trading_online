#!/bin/bash
# Lancement du Dashboard Streamlit - Quantum Trader

echo ""
echo "========================================"
echo "  Quantum Trader - Dashboard Streamlit"
echo "========================================"
echo ""
echo "Démarrage du dashboard..."
echo ""

# Lancer Streamlit
uv run streamlit run dashboard_app.py --server.port 8501
