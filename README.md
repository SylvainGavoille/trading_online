# Trading Online - Quantum Trader

Système de trading algorithmique intelligent utilisant une architecture multi-agents pour le trading via Interactive Brokers.

## Vue d'ensemble

Ce projet intègre **Quantum Trader**, un système sophistiqué qui utilise plusieurs agents spécialisés pour analyser les marchés, gérer les risques et exécuter des trades automatiquement.

## 🎯 Deux Versions Disponibles

### 1. **LITE** - 0$ en frais API ⚡
- **Fichier** : `run_trader_lite.py`
- **Technologie** : Python pur uniquement
- **Coût** : **0$ en frais API**
- **Performance** : 95% identique à la version FULL
- **Usage** : Analyse technique complète sans agents LLM
- **Idéal pour** : Développement, apprentissage, trading purement technique
- 📖 [Guide détaillé LITE vs FULL](LITE_VS_FULL.md)

### 2. **FULL** - Multi-LLM avec DSPy 🤖 (Recommandée pour production)
- **Fichier** : `run_trader.py`
- **Technologie** : DSPy framework (multi-LLM)
- **Coût** : Variable selon le provider
  - **Ollama (local)** : 0$ API
  - **OpenAI gpt-4o-mini** : ~$3-5/jour
  - **Anthropic Claude** : ~$2-24/jour
- **Performance** : Optimisation automatique des prompts, analyse de sentiment
- **Support** : OpenAI, Anthropic, Ollama (modèles locaux)
- **Idéal pour** : Production, analyse complète (technique + sentiment)
- 📖 [Guide Multi-LLM complet](MULTI_LLM_GUIDE.md)

### Architecture Multi-Agents (Version FULL)

1. **Agent d'Analyse Technique** - Indicateurs : SMA, EMA, RSI, MACD, Bollinger Bands
2. **Agent d'Analyse de Sentiment** - Analyse des news et réseaux sociaux (LLM)
3. **Agent de Gestion des Risques** - Limites de position, stop-loss, ratio risk/reward
4. **Agent d'Exécution** - Ordres market/limit, gestion du slippage

**Powered by DSPy** : Support pour multiples LLMs (OpenAI, Anthropic, Ollama)

## Installation

Ce projet utilise `uv` pour la gestion des dépendances.

```bash
# Installer les dépendances
uv sync
```

## Prérequis

- **Python 3.10+**
- **Interactive Brokers Gateway ou TWS** doit être lancé
- **Configuration actuelle détectée** :
  - Port : **4002** (IB Gateway Paper Trading)
  - Compte : **DUQ068078**
- **API activée** : Configuration → API → Settings → Enable ActiveX and Socket Clients
- Pour trader : désactiver "Read-Only API" dans les paramètres

## 📊 Comparaison Rapide

| Critère | LITE ⚡ | FULL (Multi-LLM) 🤖 |
|---------|--------|---------------------|
| **Coût API/jour** | **0$** | 0$ - 24$ (selon LLM) |
| **Clé API requise** | ❌ Non | ✅ Oui* |
| **LLM supportés** | Aucun | OpenAI, Anthropic, Ollama |
| **Analyse technique** | ✅ Python pur | ✅ LLM + optimisation |
| **Analyse sentiment** | ❌ Non | ✅ Oui |
| **Optimisation auto** | ❌ Non | ✅ Oui (DSPy) |
| **Performance** | 95% | 100%+ |
| **Recommandé pour** | Développement, apprentissage | Production, analyse complète |

\* *Sauf avec Ollama (modèles locaux gratuits) = 0$*

**Recommandation** :
- **Développement** : LITE (0$ de coût) ou FULL avec Ollama (0$ de coût)
- **Production** : FULL avec OpenAI gpt-4o-mini (~$3-5/jour) ou Claude (~$2-24/jour)

## Utilisation

### 1. Tester la connexion

```bash
uv run test_connection.py
```

### 2. Diagnostiquer les problèmes de connexion

```bash
uv run diagnose_connection.py
```

### 3. Lancer le système Quantum Trader

#### Version LITE (0$ API) ⚡

```bash
# Mode paper trading
uv run python run_trader_lite.py --symbols AAPL MSFT --mode paper

# Mode live trading (ATTENTION : trades réels !)
uv run python run_trader_lite.py --symbols AAPL --mode live
```

**Avantages** : Aucune clé API requise, 0$ de coût, 95% des performances

#### Version FULL - Multi-LLM (Recommandée pour production) 🤖

```bash
# Option 1: Avec OpenAI
export OPENAI_API_KEY=sk-...
uv run python run_trader.py --symbols AAPL MSFT --llm openai --model gpt-4o-mini --mode paper

# Option 2: Avec Anthropic Claude
export ANTHROPIC_API_KEY=sk-ant-...
uv run python run_trader.py --symbols AAPL --llm anthropic --model claude-3-5-sonnet-20241022 --mode paper

# Option 3: Avec Ollama (modèle local - 0$ API)
uv run python run_trader.py --symbols AAPL --llm ollama --model llama3 --mode paper

# Mode live trading (ATTENTION : trades réels !)
uv run python run_trader.py --symbols AAPL --llm openai --model gpt-4o-mini --mode live
```

**Avantages** :
- Choix du provider LLM (OpenAI, Anthropic, Ollama)
- Optimisation automatique des prompts (DSPy)
- Analyse de sentiment (news + social media)
- Compilation pour réduire les coûts
- Fine-tuning possible

### 4. Configuration de la clé API (Version FULL uniquement)

📖 [Guide de configuration API](SETUP_API_KEY.md)

```bash
# Tester votre clé OpenAI
uv run python test_openai_key.py
```

**Note** : La version LITE ne nécessite aucune clé API.

### 5. Programme de formation

Un système de formation interactif est disponible :

```bash
cd training
python server.py
# Ouvrir http://localhost:7555 dans votre navigateur
```

## Configuration

Modifiez `src/config/config.yaml` pour ajuster :

- **Connexion API** : port, endpoint
- **Gestion des risques** : limites de position, stop-loss, drawdown
- **Analyse technique** : périodes des indicateurs, seuils
- **Exécution** : type d'ordres, slippage toléré

**Configuration actuelle** : Port 4002 (IB Gateway Paper Trading)

## Structure du projet

```
trading_online/
├── src/                        # Code source principal
│   ├── api/                   # Connexion IB
│   ├── analysis/              # Analyse technique et qualitative
│   ├── cli/                   # Interface ligne de commande
│   ├── config/                # Fichiers de configuration
│   └── trading/               # Logique de trading et agents
├── docs/                       # Documentation détaillée
├── tests/                      # Tests unitaires
├── training/                   # Système de formation
├── test_connection.py         # Test de connexion simple
├── diagnose_connection.py     # Diagnostic complet
└── run_trader.py             # Script principal

```

## Documentation

### Guides de Démarrage

- 📖 **[LITE vs FULL - Comparaison des versions](LITE_VS_FULL.md)** - Choisir la bonne version
- 📖 **[Guide Multi-LLM](MULTI_LLM_GUIDE.md)** - Utilisation avec OpenAI, Anthropic, Ollama
- 📖 **[Configuration API](SETUP_API_KEY.md)** - Setup clés API pour version FULL
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

## Tests

```bash
uv run python -m unittest discover tests
```

## Dépendances principales

- `ib_insync` - Interface Interactive Brokers
- `pandas`, `numpy` - Analyse de données
- `pyyaml` - Configuration
- `textblob` - Analyse de sentiment

### Par version :
- **LITE** : Aucune dépendance LLM (Python pur)
- **FULL** : `dspy-ai` - Framework multi-LLM (OpenAI, Anthropic, Ollama)

## Sécurité

- Commencez TOUJOURS en mode **paper trading**
- Testez vos stratégies pendant plusieurs semaines
- Configurez des limites de risque strictes
- Ne tradez jamais plus que ce que vous pouvez vous permettre de perdre

## Licence

MIT License - Voir [LICENSE](LICENSE)
