# Système Multi-Agents

[← Retour Architecture](./ARCHITECTURE.md)

## Vue d'ensemble

Le système Quantum Trader utilise une **architecture multi-agents** basée sur le framework **Swarm** d'OpenAI. Quatre agents spécialisés collaborent pour analyser, décider et exécuter des trades.

```mermaid
graph TB
    subgraph "Système Multi-Agents"
        Manager[Agent Manager]

        subgraph "Agents d'Analyse"
            TechAgent[Agent Technique]
            SentAgent[Agent Sentiment]
        end

        subgraph "Agents d'Action"
            RiskAgent[Agent Risque]
            ExecAgent[Agent Exécution]
        end
    end

    MarketData[Données Marché] --> Manager
    Manager --> TechAgent
    Manager --> SentAgent

    TechAgent -->|Signal technique| Combiner[Combinaison]
    SentAgent -->|Sentiment| Combiner

    Combiner --> RiskAgent
    RiskAgent -->|Validation| ExecAgent
    ExecAgent -->|Ordre| IB[Interactive Brokers]

    style TechAgent fill:#e3f2fd
    style SentAgent fill:#f3e5f5
    style RiskAgent fill:#fff3e0
    style ExecAgent fill:#e8f5e9
```

## Les 4 Agents

### 1. Agent d'Analyse Technique 📊

**Rôle** : Analyser les données de marché avec des indicateurs techniques

```mermaid
graph LR
    Input[Données OHLCV] --> Agent[Agent Technique]

    Agent --> SMA[Calcul SMA]
    Agent --> EMA[Calcul EMA]
    Agent --> RSI[Calcul RSI]
    Agent --> MACD[Calcul MACD]
    Agent --> BB[Calcul Bollinger Bands]

    SMA --> Combine[Combinaison]
    EMA --> Combine
    RSI --> Combine
    MACD --> Combine
    BB --> Combine

    Combine --> Signal{Signal}
    Signal -->|RSI < 30 + MACD positif| Buy[BUY]
    Signal -->|RSI > 70 + MACD négatif| Sell[SELL]
    Signal -->|Autres| Neutral[NEUTRAL]

    Buy --> Output[Signal + Confiance]
    Sell --> Output
    Neutral --> Output
```

**Indicateurs utilisés** :
- **SMA** (20, 50, 200 périodes) : Tendance long terme
- **EMA** (12, 26) : Tendance court terme
- **RSI** (14) : Surachat/survente
- **MACD** : Momentum
- **Bollinger Bands** : Volatilité

**Sortie** :
```json
{
  "signal": "buy",      // buy, sell, ou neutral
  "confidence": 0.75,   // 0.0 à 1.0
  "indicators": {
    "rsi": 28.5,
    "macd": 0.45,
    "sma_20": 150.2,
    "bollinger_position": "lower"
  }
}
```

[→ Détails des indicateurs](./INDICATORS.md)

---

### 2. Agent d'Analyse de Sentiment 💬

**Rôle** : Évaluer le sentiment du marché via news et réseaux sociaux

```mermaid
graph TB
    subgraph "Sources"
        News[Articles News]
        Twitter[Twitter/X]
        Reddit[Reddit]
    end

    News --> Collector[Collecteur]
    Twitter --> Collector
    Reddit --> Collector

    Collector --> NLP[Traitement NLP]

    NLP --> Positive[Sentiment Positif]
    NLP --> Negative[Sentiment Négatif]
    NLP --> Neutral[Sentiment Neutre]

    Positive --> Weight[Pondération]
    Negative --> Weight
    Neutral --> Weight

    Weight --> Score[Score Final]

    Score -->|> 0.6| Bullish[BULLISH]
    Score -->|< -0.6| Bearish[BEARISH]
    Score -->|autre| NeutralSent[NEUTRAL]
```

**Sources analysées** :
- Articles de presse financière (60% poids)
- Twitter/X (20% poids)
- Reddit (20% poids)

**Configuration** :
```yaml
sentiment_analysis:
  news:
    update_interval: 300  # 5 minutes
    min_articles: 5
  social:
    platforms: ["twitter", "reddit"]
    min_mentions: 10
  weights:
    news: 0.6
    social: 0.4
```

**Sortie** :
```json
{
  "signal": "bullish",    // bullish, bearish, neutral
  "confidence": 0.65,
  "sources": {
    "news_count": 12,
    "social_mentions": 45,
    "overall_tone": "positive"
  }
}
```

[→ Documentation complète](./docs/sentiment_analysis.md)

---

### 3. Agent de Gestion des Risques 🛡️

**Rôle** : Valider chaque trade avant exécution

```mermaid
graph TD
    Trade[Proposition Trade] --> Agent[Agent Risque]

    Agent --> Check1{Taille position\n< max?}
    Check1 -->|Non| Reject1[REJETÉ:\nPosition trop grande]
    Check1 -->|Oui| Check2{Exposition portfolio\n< 25%?}

    Check2 -->|Non| Reject2[REJETÉ:\nExposition excessive]
    Check2 -->|Oui| Check3{Perte journalière\n< limite?}

    Check3 -->|Non| Reject3[REJETÉ:\nLimite perte atteinte]
    Check3 -->|Oui| Check4{Ratio risk/reward\n> 2.0?}

    Check4 -->|Non| Reject4[REJETÉ:\nRatio insuffisant]
    Check4 -->|Oui| Check5{Stop-loss\ncalculé?}

    Check5 -->|Non| Reject5[REJETÉ:\nPas de stop-loss]
    Check5 -->|Oui| Approve[✅ APPROUVÉ]

    Reject1 --> Log[Logging]
    Reject2 --> Log
    Reject3 --> Log
    Reject4 --> Log
    Reject5 --> Log

    style Approve fill:#ccffcc
    style Reject1 fill:#ffcccc
    style Reject2 fill:#ffcccc
    style Reject3 fill:#ffcccc
    style Reject4 fill:#ffcccc
    style Reject5 fill:#ffcccc
```

**Validations effectuées** :

1. **Taille de position**
   - Max : 100 actions par défaut
   - Configurable dans `config.yaml`

2. **Exposition du portfolio**
   - Max : 25% du capital total
   - Évite la sur-concentration

3. **Limite de perte journalière**
   - Max : $1000 par défaut
   - Arrêt automatique si atteint

4. **Ratio Risk/Reward**
   - Min : 2.0 (gain potentiel / perte potentielle)
   - Assure un trading profitable long terme

5. **Stop-Loss dynamique**
   - Calculé avec ATR (Average True Range)
   - Multiplié par 2 par défaut

**Sortie** :
```json
{
  "approved": true,
  "risk_parameters": {
    "position_size": "valid",
    "portfolio_exposure": "valid",
    "daily_loss": "valid",
    "risk_reward_ratio": "valid",
    "stop_loss": "calculated"
  },
  "calculated_stop_loss": 148.50,
  "position_size": 50
}
```

[→ Gestion des risques détaillée](./RISK_MANAGEMENT_DETAILED.md)

---

### 4. Agent d'Exécution ⚡

**Rôle** : Exécuter les trades validés sur Interactive Brokers

```mermaid
graph LR
    Approved[Trade Approuvé] --> Agent[Agent Exécution]

    Agent --> Type{Type d'ordre}

    Type -->|Market| Market[Ordre Market]
    Type -->|Limit| Limit[Ordre Limit]

    Market --> Execute1[Exécution immédiate]
    Limit --> Wait[Attente]

    Wait --> Timeout{Timeout\n60s}
    Timeout -->|Expiré| Cancel[Annulation]
    Timeout -->|Exécuté| Execute2[Rempli]

    Execute1 --> Confirm[Confirmation IB]
    Execute2 --> Confirm
    Cancel --> Log[Logging]

    Confirm --> Monitor[Monitoring Position]
    Monitor --> StopLoss[Stop-Loss]
    Monitor --> Target[Take-Profit]
```

**Types d'ordres** :

| Type | Description | Usage |
|------|-------------|-------|
| **Market** | Exécution immédiate au prix marché | Urgence, forte liquidité |
| **Limit** | Exécution à un prix limite ou meilleur | Contrôle prix, faible slippage |

**Configuration** :
```yaml
execution:
  order_types: ["market", "limit"]
  default_order_type: "limit"
  limit_order_timeout: 60  # secondes
  slippage_tolerance: 0.001  # 0.1%
  position_sizing:
    method: "risk_based"  # ou "fixed_size"
    risk_per_trade: 0.01  # 1% du capital
```

**Gestion du Slippage** :
- Tolérance max : 0.1% par défaut
- Si slippage > tolérance → Annulation

**Sortie** :
```json
{
  "status": "executed",
  "order_id": "12345",
  "symbol": "AAPL",
  "quantity": 50,
  "price": 150.25,
  "timestamp": "2026-02-20T16:30:00Z",
  "stop_loss": 148.50,
  "take_profit": 154.00
}
```

---

## Communication Inter-Agents

Les agents communiquent via le framework **Swarm** :

```mermaid
sequenceDiagram
    participant Manager as Agent Manager
    participant Tech as Agent Technique
    participant Sent as Agent Sentiment
    participant Risk as Agent Risque
    participant Exec as Agent Exécution

    Manager->>Tech: Analyser AAPL
    Manager->>Sent: Analyser sentiment AAPL

    Tech-->>Manager: Signal BUY (0.75)
    Sent-->>Manager: Sentiment BULLISH (0.65)

    Manager->>Manager: Combiner signaux
    Note over Manager: (0.75 * 0.7) + (0.65 * 0.3) = 0.72

    alt Signal combiné > 0.65
        Manager->>Risk: Valider trade AAPL
        Risk->>Risk: Vérifier limites
        Risk-->>Manager: APPROUVÉ + params

        Manager->>Exec: Exécuter trade
        Exec->>IB: Passer ordre
        IB-->>Exec: Confirmation
        Exec-->>Manager: Trade exécuté
    else Signal trop faible
        Manager->>Manager: Attendre
    end
```

## Pondération des Signaux

Les signaux des agents sont combinés avec des poids configurables :

```yaml
agent_system:
  signal_weights:
    technical: 0.7   # 70% du poids
    sentiment: 0.3   # 30% du poids
```

**Formule** :
```
Signal_Combiné = (Signal_Technique × 0.7) + (Signal_Sentiment × 0.3)
```

**Seuils de décision** :
```yaml
agent_system:
  confidence_thresholds:
    technical: 0.7    # Seuil min pour signal technique
    sentiment: 0.6    # Seuil min pour sentiment
    combined: 0.65    # Seuil min pour signal combiné
```

**Exemple** :
```
Signal Technique = 0.80 (BUY)
Signal Sentiment = 0.70 (BULLISH)

Signal Combiné = (0.80 × 0.7) + (0.70 × 0.3)
              = 0.56 + 0.21
              = 0.77

0.77 > 0.65 → Trade proposé ✅
```

## Gestion des Erreurs

```mermaid
graph TD
    Error[Erreur Détectée] --> Type{Type}

    Type -->|Connexion IB| Retry1[Reconnexion\n3 tentatives]
    Type -->|Données invalides| Skip[Ignorer cycle]
    Type -->|Agent timeout| Fallback[Mode dégradé]
    Type -->|Limite risque| Stop[Arrêt trading]

    Retry1 -->|Succès| Resume[Reprendre]
    Retry1 -->|Échec| Alert1[Alerte utilisateur]

    Skip --> Wait[Attendre prochain cycle]
    Fallback --> Manual[Mode manuel]
    Stop --> Alert2[Notification critique]

    Resume --> Normal[Fonctionnement normal]
    Wait --> Normal
```

## Fichiers Concernés

| Fichier | Responsabilité |
|---------|----------------|
| `src/trading/agents/agent_manager.py` | Gestionnaire principal des agents |
| `src/trading/agents/signal_analyzer.py` | Analyse et combinaison des signaux |
| `src/trading/agents/risk_validator.py` | Validation des risques |
| `src/trading/agents/trade_executor.py` | Exécution des ordres |
| `src/trading/agents/response_parser.py` | Parsing des réponses agents |
| `src/trading/trading_agents.py` | Système Swarm complet |

## Configuration Complète

```yaml
agent_system:
  update_interval: 60  # Secondes entre chaque cycle

  # Seuils de confiance minimum
  confidence_thresholds:
    technical: 0.7
    sentiment: 0.6
    combined: 0.65

  # Pondération des signaux
  signal_weights:
    technical: 0.7
    sentiment: 0.3

  # Timeout pour handoffs entre agents
  handoff_timeout: 30  # secondes
```

---

**Navigation**
- [← Architecture](./ARCHITECTURE.md)
- [→ Indicateurs Techniques](./INDICATORS.md)
- [→ Gestion des Risques](./RISK_MANAGEMENT_DETAILED.md)
- [→ Flux de Travail](./WORKFLOW.md)
