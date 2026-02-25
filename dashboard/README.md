# 📊 Dashboard Streamlit - Quantum Trader

Interface web interactive pour l'exploration et l'analyse des marchés financiers.

## 🚀 Démarrage Rapide

### Depuis la racine du projet

```bash
# Windows
..\run_dashboard.bat

# Linux/macOS
../run_dashboard.sh

# Ou directement
cd dashboard
uv run streamlit run dashboard_app.py
```

### Depuis le répertoire dashboard

```bash
# Windows
launch_dashboard.bat

# Linux/macOS
./launch_dashboard.sh

# Ou commande directe
uv run streamlit run dashboard_app.py
```

Le dashboard s'ouvrira automatiquement sur `http://localhost:8501`

## 📁 Structure

```
dashboard/
├── dashboard_app.py          # Application principale Streamlit
├── test_dashboard.py         # Tests des dépendances
├── launch_dashboard.sh       # Script de lancement (Linux/macOS)
├── launch_dashboard.bat      # Script de lancement (Windows)
├── .streamlit/               # Configuration Streamlit
│   └── config.toml          # Thème et paramètres
└── docs/                     # Documentation
    ├── DASHBOARD_GUIDE.md            # Guide complet
    ├── DASHBOARD_FEATURES.md         # Fonctionnalités détaillées
    ├── QUICK_START_DASHBOARD.md      # Démarrage rapide
    ├── STOCK_SEARCH_AGENT.md         # Agent de recherche
    └── DYNAMIC_SEARCH_SYSTEM.md      # Système dynamique
```

## 🎯 Fonctionnalités

### 🔍 Onglet Exploration

**Recherche Intelligente d'Actions**
- Recherche dynamique via Yahoo Finance
- 60,000+ instruments accessibles
- Affichage en tableau structuré
- Sélection rapide en 1 clic

**Graphiques Interactifs**
- Chandeliers (candlestick)
- 7 périodes (1j → 10ans)
- Zoom, pan, export
- Curseur de navigation

**Statistiques**
- Prix actuel, min, max
- Moyenne, volatilité
- Volume

**Analyse IA** (si Ollama configuré)
- Génération d'insights
- Points clés automatiques

### 📊 Onglets à Venir

- **Portfolio** : Positions, P&L, performance
- **Configuration** : Paramètres personnalisés
- **Documentation** : Guide interactif

## 🔧 Dépendances

Installées automatiquement avec `uv sync` :

- streamlit >= 1.41.0
- yfinance >= 0.2.50
- plotly >= 6.0.0
- pandas >= 2.0.0
- dspy-ai >= 3.1.3

## 💡 Configuration

### Thème (`.streamlit/config.toml`)

```toml
[theme]
primaryColor = "#26a69a"      # Vert cyan
backgroundColor = "#0e1117"    # Noir
secondaryBackgroundColor = "#262730"
textColor = "#fafafa"
```

### LLM (optionnel)

Par défaut : **Ollama + DeepSeek-R1** (gratuit)

Alternative : OpenAI ou Anthropic
```yaml
# ../src/config/config.yaml
multi_agent:
  llm_provider: openai  # ou anthropic
  model_name: gpt-4o-mini
```

## 📖 Documentation

### Guides Complets

- **[DASHBOARD_GUIDE.md](docs/DASHBOARD_GUIDE.md)** - Guide d'utilisation complet
- **[DASHBOARD_FEATURES.md](docs/DASHBOARD_FEATURES.md)** - Fonctionnalités détaillées
- **[QUICK_START_DASHBOARD.md](docs/QUICK_START_DASHBOARD.md)** - Démarrage en 3 étapes

### Système de Recherche

- **[STOCK_SEARCH_AGENT.md](docs/STOCK_SEARCH_AGENT.md)** - Agent de recherche intelligent
- **[DYNAMIC_SEARCH_SYSTEM.md](docs/DYNAMIC_SEARCH_SYSTEM.md)** - Système dynamique Yahoo Finance

## 🧪 Tests

```bash
# Tester les dépendances
uv run python test_dashboard.py

# Vérifier que tout fonctionne
uv run streamlit run dashboard_app.py
```

## 🎯 Exemples d'Utilisation

### 1. Analyser AAPL sur 1 mois

1. Lancer le dashboard
2. Onglet **🔍 Exploration**
3. Sélection : Catégorie **Tech** → **AAPL**
4. Période : **1 Mois**
5. Cliquer **📥 Charger les données**

### 2. Rechercher des ETF tech

1. Ouvrir **💡 Recherche Intelligente d'Actions**
2. Entrer : `ETF tech`
3. Cliquer **🔍 Rechercher**
4. Voir le tableau avec QQQ, XLK, VGT...
5. Cliquer sur un symbole pour l'analyser

### 3. Analyser Bitcoin

1. Recherche : `bitcoin`
2. Résultats : BTC-USD, IBIT, BITO...
3. Sélectionner BTC-USD
4. Période : 1 An
5. Observer la volatilité

## 💰 Coût

**0$ avec Ollama** (recommandé)
- Modèle local DeepSeek-R1
- Pas de limite d'utilisation
- Données privées

**Alternative cloud** :
- OpenAI : ~$3-5/jour
- Anthropic : ~$24/jour

## 🐛 Dépannage

### Dashboard ne démarre pas

```bash
# Vérifier les dépendances
cd ..
uv sync

# Relancer
cd dashboard
uv run streamlit run dashboard_app.py
```

### Erreur d'import

```bash
# Vérifier que vous êtes dans le bon répertoire
pwd  # Devrait afficher .../trading_online/dashboard

# Ou lancer depuis la racine
cd ..
./run_dashboard.sh
```

### Port déjà utilisé

```bash
# Utiliser un autre port
uv run streamlit run dashboard_app.py --server.port 8502
```

## 📚 Liens Utiles

- [Streamlit Docs](https://docs.streamlit.io)
- [Plotly Charts](https://plotly.com/python/)
- [Yahoo Finance](https://finance.yahoo.com)
- [DSPy Framework](https://dspy-docs.vercel.app/)

---

**Version** : 2.0.0
**Date** : 2026-02-20
**Réorganisation** : Code dashboard isolé dans `dashboard/`
