# Trading Online - Quantum Trader

Système de trading algorithmique intelligent utilisant une architecture multi-agents DSPy pour le trading via Interactive Brokers.

## Vue d'ensemble

**Quantum Trader** est un système sophistiqué qui utilise 4 agents spécialisés DSPy pour analyser les marchés, gérer les risques et exécuter des trades automatiquement.

## 🚀 Version Unique - Multi-LLM avec DSPy

- **Fichier** : `run_trader.py`
- **Technologie** : DSPy framework (multi-LLM)
- **Coût** : **0$ avec Ollama** (recommandé) ou variable selon le provider
- **Performance** : Optimisation automatique des prompts, analyse technique + sentiment

### 💰 Options de LLM

| Provider | Modèle | Coût/jour | Usage |
|----------|--------|-----------|-------|
| **Ollama** ⭐ | deepseek-r1:14b | **0$** | **Recommandé** - Local, gratuit, performant |
| OpenAI | gpt-4o-mini | ~$3-5 | Cloud, rapide |
| Anthropic | claude-3-5-sonnet | ~$24 | Cloud, meilleure qualité |

**Par défaut** : Ollama avec DeepSeek-R1 (modèle de raisonnement local, 0$ API)

📖 [Guide Multi-LLM complet](docs/MULTI_LLM_GUIDE.md)

## 🤖 Architecture Multi-Agents

Powered by **DSPy** - Framework avec optimisation automatique des prompts

1. **Agent d'Analyse Technique** - Indicateurs : SMA, EMA, RSI, MACD, Bollinger Bands
2. **Agent d'Analyse de Sentiment** - Analyse des news et réseaux sociaux
3. **Agent de Gestion des Risques** - Limites de position, stop-loss, ratio risk/reward
4. **Agent d'Exécution** - Ordres market/limit, gestion du slippage

## Installation

Ce projet utilise `uv` pour la gestion des dépendances.

```bash
# Installer les dépendances
uv sync
```

## Prérequis

- **Python 3.10+**
- **Interactive Brokers Gateway ou TWS** doit être lancé
- **Ollama installé** (pour utilisation gratuite) : https://ollama.ai
- **Configuration actuelle détectée** :
  - Port : **4002** (IB Gateway Paper Trading)
  - Compte : **DUQ068078**
- **API activée** : Configuration → API → Settings → Enable ActiveX and Socket Clients
- Pour trader : désactiver "Read-Only API" dans les paramètres

## 🚀 Démarrage Rapide

### 1. Installer Ollama (recommandé - 0$ API)

```bash
# Windows / macOS : https://ollama.ai
# Linux :
curl -fsSL https://ollama.ai/install.sh | sh

# Télécharger DeepSeek-R1 (14B)
ollama pull deepseek-r1:14b
```

### 2. Tester la connexion IB

```bash
uv run test_connection.py
```

### 3. Lancer Quantum Trader

```bash
# Mode paper trading (recommandé)
# Utilise automatiquement Ollama + DeepSeek-R1 par défaut
uv run python run_trader.py --symbols AAPL MSFT --mode paper

# Mode live trading (ATTENTION : trades réels !)
uv run python run_trader.py --symbols AAPL --mode live
```

## 📊 Dashboard Interactif (Nouveau !)

**Interface web Streamlit** pour analyser les actions avec l'IA :

```bash
# Lancer le dashboard web
./run_dashboard.sh      # Linux/macOS
run_dashboard.bat       # Windows

# Ou directement
cd dashboard
uv run streamlit run dashboard_app.py
```

**Fonctionnalités** :
- 🔍 **Recherche dynamique** - 60,000+ instruments via Yahoo Finance
- 📈 **Graphiques interactifs** - Chandeliers avec zoom et curseur
- 📊 **Multi-périodes** - 1j, 5j, 1m, 6m, 1an, 5ans, 10ans
- 📉 **Statistiques détaillées** - Min, max, moyenne, volatilité
- 🤖 **Analyse IA** - Génération d'insights automatiques
- 💰 **0$ avec Ollama** - Fonctionne en local

📖 [Guide complet du Dashboard](dashboard/README.md)

---

## Scripts de Deploiement (GCP)

Depuis la racine du repo (`C:\Users\sylva\Documents\Sources\trading_online`) :

```powershell
# Aide
.\scripts\deploy.ps1 -Target help

# Build image dans GCP (Cloud Build)
.\scripts\deploy.ps1 -Target cloud-build -ProjectId sylvain-488510

# Terraform only (infra Cloud Run / Scheduler / VPC connector)
.\scripts\deploy.ps1 -Target tf-only -ProjectId sylvain-488510 -AutoApprove

# Setup complet VM IB Gateway (+ secrets, firewall, bootstrap logiciel)
.\scripts\deploy.ps1 -Target ib-gateway-setup -ProjectId sylvain-488510 -Region us-central1 -Zone us-central1-b -IbVmName ib-gateway-vm -IbApiPort 4002 -IbSourceRanges 10.8.0.0/28 -InstallIbSoftware -TunnelThroughIap -AutoApprove

# Lister les jobs Cloud Run disponibles
gcloud run jobs list --region us-central1 --project sylvain-488510

# Executer les jobs Cloud Run (mode split recommande)
gcloud run jobs execute quantum-daily-ml-refresh --region us-central1 --project sylvain-488510 --wait
gcloud run jobs execute quantum-daily-ml-pipeline --region us-central1 --project sylvain-488510 --wait

# Mode legacy (job unique), seulement si split_jobs_enabled=false dans Terraform
gcloud run jobs execute quantum-daily-ml --region us-central1 --project sylvain-488510 --wait

# Verifier les donnees generees
gcloud storage ls -r gs://quantum-ml-bucket/price_historical/**/*.parquet --project=sylvain-488510
gcloud storage ls -r gs://quantum-ml-bucket/options_snapshot/**/*.parquet --project=sylvain-488510
```

Documentation associee:

- `scripts/deploy_ib_gateway.md`
- `docs/IBKR_VM_DOCUMENTATION.md`

## 💡 Options Avancées

### Option 1 : Ollama (Par défaut - 0$ API)

```bash
# Utilise DeepSeek-R1 par défaut
uv run python run_trader.py --symbols AAPL MSFT --mode paper

# Ou spécifier explicitement
uv run python run_trader.py --symbols AAPL MSFT --llm ollama --model deepseek-r1:14b --mode paper

# Autres modèles Ollama
uv run python run_trader.py --symbols AAPL --llm ollama --model llama3:8b --mode paper
```

### Option 2 : OpenAI

```bash
export OPENAI_API_KEY=sk-...
uv run python run_trader.py --symbols AAPL MSFT --llm openai --model gpt-4o-mini --mode paper
```

### Option 3 : Anthropic Claude

```bash
export ANTHROPIC_API_KEY=sk-ant-...
uv run python run_trader.py --symbols AAPL --llm anthropic --model claude-3-5-sonnet-20241022 --mode paper
```

## 📖 Configuration de la clé API

Pour OpenAI ou Anthropic : [Guide de configuration API](docs/SETUP_API_KEY.md)

**Note** : Ollama ne nécessite aucune clé API (modèle local).

## Configuration

Modifiez `src/config/config.yaml` pour ajuster :

- **Connexion API** : port, endpoint
- **Gestion des risques** : limites de position, stop-loss, drawdown
- **Analyse technique** : périodes des indicateurs, seuils
- **Exécution** : type d'ordres, slippage toléré
- **Frais IBKR** : Choix du plan (Lite, Pro Fixed, Pro Tiered)

**Configuration actuelle** : Port 4002 (IB Gateway Paper Trading)

## Structure du projet

```
trading_online/
├── src/                        # Code source principal
│   ├── api/                   # Connexion IB
│   ├── analysis/              # Analyse technique et qualitative
│   ├── cli/                   # Interface ligne de commande
│   ├── config/                # Fichiers de configuration
│   ├── data/                  # Données et recherche dynamique
│   ├── agents/                # Agents de recherche
│   └── trading/               # Logique de trading et agents DSPy
├── dashboard/                  # 📊 Dashboard Streamlit (NOUVEAU)
│   ├── dashboard_app.py       # Application Streamlit
│   ├── test_dashboard.py      # Tests
│   ├── .streamlit/            # Configuration Streamlit
│   └── docs/                  # Documentation dashboard
├── docs/                       # Documentation détaillée
├── tests/                      # Tests unitaires
├── training/                   # Système de formation
├── test_connection.py         # Test de connexion simple
├── diagnose_connection.py     # Diagnostic complet
├── run_trader.py              # Script principal trading
└── run_dashboard.sh/bat       # Scripts de lancement dashboard

```

## Documentation

### Guides de Démarrage

- 📖 **[Guide Multi-LLM](docs/MULTI_LLM_GUIDE.md)** - Utilisation avec OpenAI, Anthropic, Ollama
- 📖 **[Configuration API](docs/SETUP_API_KEY.md)** - Setup clés API (si OpenAI/Anthropic)
- 📖 **[Guide des Frais IBKR](docs/IBKR_PLANS_GUIDE.md)** - Choisir votre plan IBKR
- 📖 **[Index de la documentation complète](docs/INDEX_DOCS.md)** - Toute la documentation

### Documentation Technique Détaillée

- [Architecture du système](docs/ARCHITECTURE.md)
- [Système d'agents](docs/AGENTS_SYSTEM.md)
- [Indicateurs techniques](docs/INDICATORS.md)
- [Gestion des risques](docs/RISK_MANAGEMENT_DETAILED.md)
- [Workflow de trading](docs/WORKFLOW.md)
- [Configuration](docs/CONFIGURATION.md)

### Documentation d'origine

- [CLI Interface](docs/cli_interface.md)
- [IB Connector](docs/ib_connector.md)
- [Trading Logic](docs/trading_logic.md)
- [Technical Analysis](docs/technical_analysis.md)
- [Sentiment Analysis](docs/sentiment_analysis.md)
- [Risk Management](docs/risk_management.md)

## Diagnostics

```bash
# Test de connexion IB
uv run python test_connection.py

# Diagnostic complet
uv run python diagnose_connection.py
```

## Tests

```bash
uv run python -m unittest discover tests
```

## Dépendances principales

- `ib_insync` - Interface Interactive Brokers
- `dspy-ai` - Framework multi-LLM avec optimisation automatique
- `pandas`, `numpy` - Analyse de données
- `pyyaml` - Configuration
- `textblob` - Analyse de sentiment

## 🎓 Programme de formation

Un système de formation interactif est disponible :

```bash
cd training
python server.py
# Ouvrir http://localhost:7555 dans votre navigateur
```

## ✅ Recommandations

### Pour Débutants

```bash
# 1. Installer Ollama (gratuit)
# https://ollama.ai

# 2. Télécharger DeepSeek-R1
ollama pull deepseek-r1:14b

# 3. Tester en paper trading
uv run python run_trader.py --symbols AAPL --mode paper --cycles 1
```

**Coût** : 0$ API ✅

### Pour Production

**Option A - Économique (0$)** :
```bash
# Ollama + DeepSeek-R1 (local, gratuit)
uv run python run_trader.py --symbols AAPL MSFT GOOGL --mode paper
```

**Option B - Cloud** :
```bash
# OpenAI gpt-4o-mini (~$3-5/jour)
uv run python run_trader.py --symbols AAPL MSFT --llm openai --model gpt-4o-mini --mode paper
```

**Option C - Qualité Max** :
```bash
# Anthropic Claude (~$24/jour)
uv run python run_trader.py --symbols AAPL MSFT --llm anthropic --model claude-3-5-sonnet-20241022 --mode paper
```

## 🛡️ Sécurité

- Commencez TOUJOURS en mode **paper trading**
- Testez vos stratégies pendant plusieurs semaines minimum
- Configurez des limites de risque strictes
- Ne tradez jamais plus que ce que vous pouvez vous permettre de perdre
- Utilisez le kill switch en cas d'urgence

## 💡 Pourquoi Ollama + DeepSeek-R1 ?

- ✅ **0$ de coût API** - Complètement gratuit
- ✅ **Local** - Aucune donnée envoyée au cloud
- ✅ **Performant** - Modèle de raisonnement 14B paramètres
- ✅ **Pas de limite** - Utilisez autant que vous voulez
- ✅ **Rapide** - Avec GPU : ~30-50 tokens/sec

**Alternative cloud** : OpenAI gpt-4o-mini si vous préférez le cloud (~$3-5/jour)

## Licence

MIT License - Voir [LICENSE](LICENSE)
