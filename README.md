# Trading Online - Quantum Trader

Système de trading algorithmique intelligent utilisant une architecture multi-agents pour le trading via Interactive Brokers.

## Vue d'ensemble

Ce projet intègre **Quantum Trader**, un système sophistiqué qui utilise plusieurs agents spécialisés pour analyser les marchés, gérer les risques et exécuter des trades automatiquement.

### Architecture Multi-Agents

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
- **Configuration actuelle détectée** :
  - Port : **4002** (IB Gateway Paper Trading)
  - Compte : **DUQ068078**
- **API activée** : Configuration → API → Settings → Enable ActiveX and Socket Clients
- Pour trader : désactiver "Read-Only API" dans les paramètres

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

```bash
# Mode paper trading (recommandé pour débuter)
uv run run_trader.py --symbols AAPL MSFT GOOGL --mode paper

# Mode live trading (ATTENTION : trades réels !)
uv run run_trader.py --symbols AAPL --mode live
```

### 4. Programme de formation

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
- `swarm` - Framework multi-agents (OpenAI)
- `pyyaml` - Configuration
- `textblob` - Analyse de sentiment

## Sécurité

- Commencez TOUJOURS en mode **paper trading**
- Testez vos stratégies pendant plusieurs semaines
- Configurez des limites de risque strictes
- Ne tradez jamais plus que ce que vous pouvez vous permettre de perdre

## Licence

MIT License - Voir [LICENSE](LICENSE)
