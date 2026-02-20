# Architecture Quantum Trader

## Vue d'ensemble

Quantum Trader est un système de trading algorithmique autonome qui utilise une **architecture multi-agents** pour analyser les marchés, gérer les risques et exécuter des trades automatiquement via Interactive Brokers.

```mermaid
graph TB
    User[Utilisateur] -->|Configure| CLI[Interface CLI]
    CLI -->|Démarre| System[Système Quantum Trader]

    System --> Orchestrator[Orchestrateur Principal]

    Orchestrator --> AgentSystem[Système Multi-Agents]
    Orchestrator --> DataLayer[Couche de Données]
    Orchestrator --> RiskLayer[Couche de Risque]
    Orchestrator --> ExecutionLayer[Couche d'Exécution]

    AgentSystem --> TechAgent[Agent Technique]
    AgentSystem --> SentAgent[Agent Sentiment]
    AgentSystem --> RiskAgent[Agent Risque]
    AgentSystem --> ExecAgent[Agent Exécution]

    DataLayer --> IBConnector[Connecteur IB]
    IBConnector -->|API| IBGateway[IB Gateway/TWS]

    ExecutionLayer --> IBGateway

    style System fill:#e1f5ff
    style AgentSystem fill:#fff4e1
    style IBGateway fill:#ffe1e1
```

## Composants Principaux

Le système est organisé en **5 couches** principales :

### 1. Interface Utilisateur
- **CLI Interface** : Interface ligne de commande pour démarrer et configurer le système
- **Dashboard** : Interface de monitoring en temps réel (optionnel)
- [Documentation CLI →](./docs/cli_interface.md)

### 2. Orchestrateur (Trading Logic)
- Coordonne tous les composants
- Gère le flux de décision
- Synchronise les agents
- [Détails Orchestrateur →](./ORCHESTRATOR.md)

### 3. Système Multi-Agents
- 4 agents spécialisés qui collaborent
- Communication via le framework Swarm (OpenAI)
- Chaque agent a un rôle spécifique
- [Architecture Agents →](./AGENTS_SYSTEM.md)

### 4. Analyseurs de Données
- **Analyse Technique** : Calcul d'indicateurs (RSI, MACD, Bollinger, etc.)
- **Analyse Qualitative** : Sentiment de marché (news, réseaux sociaux)
- [Indicateurs Techniques →](./INDICATORS.md)
- [Analyse de Sentiment →](./docs/sentiment_analysis.md)

### 5. Couches de Sécurité
- **Validation des Risques** : Vérification avant exécution
- **Gestion des Positions** : Limites de taille et exposition
- **Stop-Loss Dynamique** : Protection contre les pertes
- [Gestion des Risques →](./RISK_MANAGEMENT_DETAILED.md)

## Flux de Décision

```mermaid
sequenceDiagram
    participant User
    participant CLI
    participant Orchestrator
    participant TechAgent
    participant SentAgent
    participant RiskAgent
    participant ExecAgent
    participant IB

    User->>CLI: Démarrer avec symboles AAPL, MSFT
    CLI->>Orchestrator: Initialiser système

    loop Toutes les 60 secondes
        Orchestrator->>IB: Récupérer données marché
        IB-->>Orchestrator: Prix, volume, historique

        par Analyse Parallèle
            Orchestrator->>TechAgent: Analyser données techniques
            Orchestrator->>SentAgent: Analyser sentiment
        end

        TechAgent-->>Orchestrator: Signal: BUY (conf: 0.75)
        SentAgent-->>Orchestrator: Sentiment: BULLISH (conf: 0.65)

        Orchestrator->>Orchestrator: Combiner signaux

        alt Signal combiné > seuil
            Orchestrator->>RiskAgent: Valider trade proposé

            alt Risque acceptable
                RiskAgent-->>Orchestrator: APPROVED
                Orchestrator->>ExecAgent: Exécuter trade
                ExecAgent->>IB: Passer ordre
                IB-->>ExecAgent: Ordre confirmé
                ExecAgent-->>Orchestrator: Trade exécuté
            else Risque trop élevé
                RiskAgent-->>Orchestrator: REJECTED (exposition > limite)
            end
        else Signal faible
            Orchestrator->>Orchestrator: Attendre prochain cycle
        end
    end
```

## Architecture des Données

```mermaid
graph LR
    subgraph "Sources de Données"
        IB[Interactive Brokers]
        News[API News]
        Social[Réseaux Sociaux]
    end

    subgraph "Collecte"
        IBConn[IB Connector]
        NewsCollector[News Collector]
        SocialCollector[Social Collector]
    end

    subgraph "Stockage"
        MarketData[(Market Data)]
        SentimentData[(Sentiment Data)]
        TradeHistory[(Trade History)]
    end

    subgraph "Traitement"
        TechAnalysis[Analyse Technique]
        SentAnalysis[Analyse Sentiment]
    end

    IB --> IBConn
    News --> NewsCollector
    Social --> SocialCollector

    IBConn --> MarketData
    NewsCollector --> SentimentData
    SocialCollector --> SentimentData

    MarketData --> TechAnalysis
    SentimentData --> SentAnalysis

    TechAnalysis --> Decision{Décision}
    SentAnalysis --> Decision

    Decision -->|Validé| Execution[Exécution]
    Decision -->|Rejeté| Wait[Attente]

    Execution --> TradeHistory
```

## Cycle de Vie d'un Trade

```mermaid
stateDiagram-v2
    [*] --> Monitoring: Système démarré

    Monitoring --> DataCollection: Nouvelle itération (60s)
    DataCollection --> TechnicalAnalysis: Données reçues

    TechnicalAnalysis --> SentimentAnalysis: Analyse terminée
    SentimentAnalysis --> SignalCombination: Sentiment évalué

    SignalCombination --> WeakSignal: Signal < seuil
    SignalCombination --> StrongSignal: Signal ≥ seuil

    WeakSignal --> Monitoring: Pas d'action

    StrongSignal --> RiskValidation: Proposer trade

    RiskValidation --> RiskRejected: Risque > limite
    RiskValidation --> RiskApproved: Risque OK

    RiskRejected --> Monitoring: Trade annulé

    RiskApproved --> OrderPlacement: Créer ordre
    OrderPlacement --> OrderPending: Ordre envoyé à IB

    OrderPending --> OrderFilled: Exécuté
    OrderPending --> OrderCancelled: Timeout/Erreur

    OrderFilled --> PositionMonitoring: Position ouverte
    OrderCancelled --> Monitoring: Retour monitoring

    PositionMonitoring --> StopLossHit: Prix atteint stop-loss
    PositionMonitoring --> TargetHit: Prix atteint objectif
    PositionMonitoring --> ManualClose: Décision de fermeture

    StopLossHit --> ClosePosition: Limiter perte
    TargetHit --> ClosePosition: Prendre profit
    ManualClose --> ClosePosition: Signal contraire

    ClosePosition --> TradeComplete: Position fermée
    TradeComplete --> Monitoring: Retour monitoring
```

## Structure du Code

```
src/
├── api/                      # Connexion Interactive Brokers
│   └── ib_connector.py      # IBClient - Gestion API
│
├── analysis/                 # Moteurs d'analyse
│   ├── technical_analysis.py   # Calcul indicateurs techniques
│   └── qualitative_analysis.py # Analyse sentiment
│
├── trading/                  # Logique de trading
│   ├── trading_logic.py     # Orchestrateur principal
│   ├── trading_agents.py    # Système multi-agents (Swarm)
│   │
│   └── agents/              # Agents spécialisés
│       ├── agent_manager.py    # Gestionnaire d'agents
│       ├── signal_analyzer.py  # Analyse signaux
│       ├── risk_validator.py   # Validation risques
│       ├── trade_executor.py   # Exécution trades
│       └── response_parser.py  # Parsing réponses agents
│
├── cli/                      # Interfaces utilisateur
│   ├── cli_interface.py     # Interface ligne de commande
│   └── dashboard.py         # Dashboard temps réel
│
└── config/                   # Configuration
    └── config.yaml          # Paramètres du système
```

## Composants Clés

| Composant | Fichier | Description | Documentation |
|-----------|---------|-------------|---------------|
| **CLI Interface** | `cli/cli_interface.py` | Point d'entrée principal | [→ Détails](./docs/cli_interface.md) |
| **Trading Logic** | `trading/trading_logic.py` | Orchestrateur central | [→ Détails](./ORCHESTRATOR.md) |
| **Agent System** | `trading/trading_agents.py` | Coordination multi-agents | [→ Détails](./AGENTS_SYSTEM.md) |
| **IB Connector** | `api/ib_connector.py` | Communication avec IB | [→ Détails](./docs/ib_connector.md) |
| **Technical Analysis** | `analysis/technical_analysis.py` | Indicateurs techniques | [→ Détails](./INDICATORS.md) |
| **Risk Validator** | `trading/agents/risk_validator.py` | Gestion des risques | [→ Détails](./RISK_MANAGEMENT_DETAILED.md) |
| **Trade Executor** | `trading/agents/trade_executor.py` | Exécution ordres | [→ Détails](./EXECUTION.md) |

## Configuration

Le système est configuré via `src/config/config.yaml` :

```yaml
api:
  tws_endpoint: "127.0.0.1"
  port: 4002  # IB Gateway Paper Trading

risk_management:
  position_limits:
    max_position_size: 100
    max_portfolio_exposure: 0.25
  loss_limits:
    daily_loss_limit: 1000
    max_drawdown: 0.15

technical_analysis:
  indicators:
    sma_periods: [20, 50, 200]
    rsi:
      period: 14
      overbought: 70
      oversold: 30

agent_system:
  update_interval: 60  # secondes
  confidence_thresholds:
    technical: 0.7
    sentiment: 0.6
    combined: 0.65
```

[→ Configuration complète](./CONFIGURATION.md)

## Prochaines Étapes

1. **[Comprendre le système multi-agents](./AGENTS_SYSTEM.md)** - Architecture des agents
2. **[Découvrir les indicateurs techniques](./INDICATORS.md)** - RSI, MACD, Bollinger Bands
3. **[Apprendre la gestion des risques](./RISK_MANAGEMENT_DETAILED.md)** - Limites et protections
4. **[Voir le flux de travail complet](./WORKFLOW.md)** - De l'analyse à l'exécution
5. **[Configurer le système](./CONFIGURATION.md)** - Personnaliser les paramètres

## Modes d'Exécution

### Mode Paper Trading (Recommandé)
- Utilise un compte de démonstration IB
- Aucun argent réel n'est risqué
- Parfait pour tester et apprendre
- Port par défaut : **4002**

### Mode Live Trading (ATTENTION)
- Utilise un compte réel
- Trades avec de l'argent réel
- Nécessite une validation stricte
- Port par défaut : **4001**

## Sécurité et Contrôles

```mermaid
graph TD
    Trade[Proposition de Trade] --> Check1{Position size OK?}
    Check1 -->|Non| Reject[REJETÉ]
    Check1 -->|Oui| Check2{Exposition OK?}

    Check2 -->|Non| Reject
    Check2 -->|Oui| Check3{Perte journalière OK?}

    Check3 -->|Non| Reject
    Check3 -->|Oui| Check4{Ratio risk/reward OK?}

    Check4 -->|Non| Reject
    Check4 -->|Oui| Check5{Stop-loss calculé?}

    Check5 -->|Non| Reject
    Check5 -->|Oui| Approve[APPROUVÉ]

    Approve --> Execute[Exécution]
    Reject --> Log[Log + Notification]

    style Reject fill:#ffcccc
    style Approve fill:#ccffcc
```

---

**Navigation**
- [Système Multi-Agents →](./AGENTS_SYSTEM.md)
- [Indicateurs Techniques →](./INDICATORS.md)
- [Gestion des Risques →](./RISK_MANAGEMENT_DETAILED.md)
- [Flux de Travail →](./WORKFLOW.md)
- [Configuration →](./CONFIGURATION.md)
