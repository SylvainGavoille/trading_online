# Trading Online - Quantum Trader

Système de trading algorithmique intelligent utilisant une architecture multi-agents pour le trading via Interactive Brokers.

## Vue d'ensemble

Ce projet intègre **Quantum Trader**, un système sophistiqué qui utilise plusieurs agents spécialisés pour analyser les marchés, gérer les risques et exécuter des trades automatiquement.

## 🎯 Trois Versions Disponibles

### 1. **LITE** - 0$ en frais API ⚡ (Recommandée)
- **Fichier** : `run_trader_lite.py`
- **Technologie** : Python pur uniquement
- **Coût** : **0$ en frais API**
- **Performance** : 95% identique à la version FULL
- **Usage** : Analyse technique complète sans agents LLM
- 📖 [Guide détaillé LITE vs FULL](LITE_VS_FULL.md)

### 2. **DSPy** - Multi-LLM flexible 🤖
- **Fichier** : `run_trader_dspy.py`
- **Technologie** : DSPy framework (multi-LLM)
- **Coût** : Variable selon le provider
  - **Ollama (local)** : 0$ API
  - **OpenAI gpt-4o-mini** : ~$3-5/jour
  - **Anthropic Claude** : ~$2-24/jour
- **Performance** : Optimisation automatique des prompts
- **Support** : OpenAI, Anthropic, Ollama (modèles locaux)
- 📖 [Guide DSPy complet](DSPY_GUIDE.md)

### 3. **FULL** - OpenAI Swarm (Original)
- **Fichier** : `run_trader.py`
- **Technologie** : OpenAI Swarm
- **Coût** : ~$3-5/jour (OpenAI uniquement)
- **Performance** : Version originale avec analyse de sentiment
- **Support** : OpenAI seulement

### Architecture Multi-Agents

1. **Agent d'Analyse Technique** - Indicateurs : SMA, EMA, RSI, MACD, Bollinger Bands
2. **Agent d'Analyse de Sentiment** - Analyse des news et réseaux sociaux (FULL et DSPy uniquement)
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
- **Configuration actuelle détectée** :
  - Port : **4002** (IB Gateway Paper Trading)
  - Compte : **DUQ068078**
- **API activée** : Configuration → API → Settings → Enable ActiveX and Socket Clients
- Pour trader : désactiver "Read-Only API" dans les paramètres

## 📊 Comparaison Rapide

| Critère | LITE ⚡ | DSPy 🤖 | FULL (Swarm) |
|---------|--------|---------|--------------|
| **Coût API/jour** | **0$** | 0$ - 24$ | 3$ - 5$ |
| **Clé API requise** | ❌ Non | ✅ Oui* | ✅ Oui (OpenAI) |
| **LLM supportés** | Aucun | OpenAI, Anthropic, Ollama | OpenAI uniquement |
| **Analyse technique** | ✅ Python pur | ✅ LLM + optimisation | ✅ LLM |
| **Analyse sentiment** | ❌ Non | ✅ Oui | ✅ Oui |
| **Performance** | 95% | 100%+ | 100% |
| **Recommandé pour** | Débutants, développement | Production, flexibilité | Version originale |

\* *Sauf avec Ollama (modèles locaux gratuits)*

**Recommandation** : Commencez avec **LITE** (0$ de coût) pour apprendre, puis testez **DSPy avec Ollama** (également 0$) si vous voulez l'analyse de sentiment.

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

#### Version LITE (Recommandée - 0$ API) ⚡

```bash
# Mode paper trading
uv run python run_trader_lite.py --symbols AAPL MSFT --mode paper

# Mode live trading (ATTENTION : trades réels !)
uv run python run_trader_lite.py --symbols AAPL --mode live
```

**Avantages** : Aucune clé API requise, 0$ de coût, 95% des performances

#### Version DSPy (Multi-LLM) 🤖

```bash
# Avec OpenAI (comme Swarm)
export OPENAI_API_KEY=sk-...
uv run python run_trader_dspy.py --symbols AAPL --llm openai --model gpt-4o-mini --mode paper

# Avec Anthropic Claude
export ANTHROPIC_API_KEY=sk-ant-...
uv run python run_trader_dspy.py --symbols AAPL --llm anthropic --model claude-3-5-sonnet-20241022 --mode paper

# Avec Ollama (modèle local - 0$ API)
uv run python run_trader_dspy.py --symbols AAPL --llm ollama --model llama3 --mode paper
```

**Avantages** : Choix du provider, optimisation automatique, compilation pour réduire les coûts

#### Version FULL (OpenAI Swarm - Original)

```bash
# Configurer la clé API OpenAI d'abord
export OPENAI_API_KEY=sk-...

# Mode paper trading
uv run python run_trader.py --symbols AAPL MSFT GOOGL --mode paper

# Mode live trading (ATTENTION : trades réels !)
uv run python run_trader.py --symbols AAPL --mode live
```

**Avantages** : Analyse de sentiment, version originale testée

### 4. Configuration de la clé API (FULL et DSPy uniquement)

📖 [Guide de configuration OpenAI](SETUP_API_KEY.md)

```bash
# Tester votre clé OpenAI
uv run python test_openai_key.py
```

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
- 📖 **[Guide DSPy](DSPY_GUIDE.md)** - Migration de Swarm vers DSPy, multi-LLM
- 📖 **[Configuration API OpenAI](SETUP_API_KEY.md)** - Setup clés API pour FULL et DSPy
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
- **DSPy** : `dspy-ai` - Framework multi-LLM (OpenAI, Anthropic, Ollama)
- **FULL** : `swarm` - Framework multi-agents OpenAI uniquement

## Sécurité

- Commencez TOUJOURS en mode **paper trading**
- Testez vos stratégies pendant plusieurs semaines
- Configurez des limites de risque strictes
- Ne tradez jamais plus que ce que vous pouvez vous permettre de perdre

## Licence

MIT License - Voir [LICENSE](LICENSE)
