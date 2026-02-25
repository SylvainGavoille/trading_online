# Flux de Travail Complet

[← Retour Architecture](./ARCHITECTURE.md)

## Vue d'ensemble

Ce document décrit le flux de travail complet du système Quantum Trader, de l'initialisation à l'exécution d'un trade.

```mermaid
graph TB
    Start([Démarrage Système]) --> Init[Initialisation]
    Init --> Connect[Connexion IB]
    Connect --> MainLoop[Boucle Principale]

    MainLoop --> DataFetch[Récupération Données]
    DataFetch --> Analysis[Analyse]
    Analysis --> Decision{Signal Fort?}

    Decision -->|Non| Wait[Attendre 60s]
    Decision -->|Oui| Risk[Validation Risque]

    Risk -->|Rejeté| Wait
    Risk -->|Approuvé| Execute[Exécution]

    Execute --> Monitor[Monitoring]
    Monitor --> MainLoop

    Wait --> MainLoop

    style Init fill:#e3f2fd
    style Analysis fill:#fff3e0
    style Risk fill:#ffe0e0
    style Execute fill:#e8f5e9
```

---

## Phase 1 : Initialisation 🚀

```mermaid
sequenceDiagram
    participant User
    participant CLI
    participant Config
    participant TradingLogic
    participant IBClient
    participant Agents

    User->>CLI: uv run run_trader.py --symbols AAPL MSFT
    CLI->>Config: Charger config.yaml
    Config-->>CLI: Configuration

    CLI->>TradingLogic: Initialiser système
    TradingLogic->>IBClient: Créer connecteur IB
    TradingLogic->>Agents: Initialiser agents

    IBClient->>IBGateway: Connexion port 4002
    IBGateway-->>IBClient: Connecté

    Agents-->>TradingLogic: Agents prêts
    TradingLogic-->>CLI: Système initialisé

    CLI-->>User: [OK] Trading started for AAPL, MSFT
```

### Étapes

1. **Chargement configuration**
   ```python
   config = yaml.safe_load('src/config/config.yaml')
   ```

2. **Vérification prérequis**
   - IB Gateway est lancé ✓
   - API activée ✓
   - Port accessible ✓

3. **Initialisation composants**
   - `IBClient` : Connexion Interactive Brokers
   - `TradingSystemDSPy` : Système multi-agents
   - `RiskValidator` : Validateur de risques
   - `TradeExecutor` : Exécuteur d'ordres

4. **Connexion IB**
   ```python
   ib_client.connect('127.0.0.1', 4002, clientId=1)
   ```

5. **Démarrage boucle**
   ```python
   while True:
       process_trading_cycle()
       time.sleep(60)  # Attendre 60 secondes
   ```

---

## Phase 2 : Récupération des Données 📊

```mermaid
graph TB
    Cycle[Nouveau Cycle 60s] --> Request[Requête données]

    Request --> Symbol1[AAPL]
    Request --> Symbol2[MSFT]
    Request --> Symbol3[GOOGL]

    Symbol1 --> Data1[OHLCV + Volume]
    Symbol2 --> Data2[OHLCV + Volume]
    Symbol3 --> Data3[OHLCV + Volume]

    Data1 --> Validate1{Données valides?}
    Data2 --> Validate2{Données valides?}
    Data3 --> Validate3{Données valides?}

    Validate1 -->|Oui| Store1[Stocker]
    Validate2 -->|Oui| Store2[Stocker]
    Validate3 -->|Oui| Store3[Stocker]

    Validate1 -->|Non| Skip1[Ignorer]
    Validate2 -->|Non| Skip2[Ignorer]
    Validate3 -->|Non| Skip3[Ignorer]

    Store1 --> Process[Traitement]
    Store2 --> Process
    Store3 --> Process

    style Store1 fill:#ccffcc
    style Store2 fill:#ccffcc
    style Store3 fill:#ccffcc
```

### Données Récupérées

Pour chaque symbole :

| Donnée | Description | Utilisation |
|--------|-------------|-------------|
| **Open** | Prix d'ouverture | Calcul range journalier |
| **High** | Prix le plus haut | Bollinger Bands, ATR |
| **Low** | Prix le plus bas | Bollinger Bands, ATR |
| **Close** | Prix de clôture | Tous les indicateurs |
| **Volume** | Volume échangé | Confirmation signaux |
| **Timestamp** | Horodatage | Suivi temporel |

### Exemple

```json
{
  "symbol": "AAPL",
  "timestamp": "2026-02-20T16:30:00Z",
  "data": {
    "open": 149.50,
    "high": 151.20,
    "low": 148.80,
    "close": 150.75,
    "volume": 45_320_000
  }
}
```

---

## Phase 3 : Analyse Multi-Agents 🤖

```mermaid
sequenceDiagram
    participant Orchestrator
    participant TechAgent
    participant SentAgent
    participant Data

    Orchestrator->>Data: Récupérer données AAPL

    par Analyse Parallèle
        Orchestrator->>TechAgent: Analyser données techniques
        Orchestrator->>SentAgent: Analyser sentiment
    end

    TechAgent->>TechAgent: Calculer RSI, MACD, BB
    SentAgent->>SentAgent: Scanner news & social

    TechAgent-->>Orchestrator: Signal: BUY (conf: 0.75)
    SentAgent-->>Orchestrator: Sentiment: BULLISH (conf: 0.65)

    Orchestrator->>Orchestrator: Combiner signaux
    Note over Orchestrator: (0.75 × 0.7) + (0.65 × 0.3) = 0.72

    Orchestrator->>Orchestrator: Générer recommandation
```

### Analyse Technique

```mermaid
graph LR
    Input[Données OHLCV] --> Calc[Calcul Indicateurs]

    Calc --> RSI[RSI: 28\nSURVENTE]
    Calc --> MACD[MACD: +0.5\nHAUSSIER]
    Calc --> BB[BB: 0.15\nProche bande inf]
    Calc --> SMA[SMA: Prix < SMA20\nBAISSIER faible]

    RSI --> Score1[+0.56]
    MACD --> Score2[+0.46]
    BB --> Score3[-0.70]
    SMA --> Score4[-0.10]

    Score1 --> Avg[Moyenne: +0.31]
    Score2 --> Avg
    Score3 --> Avg
    Score4 --> Avg

    Avg --> TechSignal[Signal Technique:\nBUY faible 0.31]

    style RSI fill:#ccffcc
    style MACD fill:#ccffcc
```

### Analyse Sentiment

```mermaid
graph TB
    Sources[Sources] --> News[12 articles news]
    Sources --> Twitter[45 mentions Twitter]
    Sources --> Reddit[18 posts Reddit]

    News --> NLP1[Analyse NLP]
    Twitter --> NLP2[Analyse NLP]
    Reddit --> NLP3[Analyse NLP]

    NLP1 --> Pos1[8 positifs, 3 négatifs, 1 neutre]
    NLP2 --> Pos2[30 positifs, 10 négatifs, 5 neutres]
    NLP3 --> Pos3[12 positifs, 4 négatifs, 2 neutres]

    Pos1 --> Weight1[Score: +0.67 × 0.6]
    Pos2 --> Weight2[Score: +0.56 × 0.2]
    Pos3 --> Weight3[Score: +0.61 × 0.2]

    Weight1 --> Final[+0.40 + 0.11 + 0.12 = +0.63]
    Weight2 --> Final
    Weight3 --> Final

    Final --> SentSignal[Sentiment:\nBULLISH 0.63]

    style Pos1 fill:#ccffcc
    style Pos2 fill:#ccffcc
    style Pos3 fill:#ccffcc
```

### Combinaison

```python
# Poids configurables
weight_technical = 0.7
weight_sentiment = 0.3

# Signaux individuels
signal_tech = 0.31
signal_sent = 0.63

# Signal combiné
signal_combined = (signal_tech * weight_technical) +
                 (signal_sent * weight_sentiment)
# = (0.31 × 0.7) + (0.63 × 0.3)
# = 0.217 + 0.189
# = 0.41

# Seuil de décision
threshold = 0.65

if signal_combined >= threshold:
    decision = "ACHAT"
elif signal_combined <= -threshold:
    decision = "VENTE"
else:
    decision = "ATTENTE"  # 0.41 < 0.65 → ATTENTE
```

---

## Phase 4 : Décision et Validation 🛡️

```mermaid
stateDiagram-v2
    [*] --> SignalAnalysis: Signal combiné = 0.72

    SignalAnalysis --> StrongSignal: Signal ≥ 0.65
    SignalAnalysis --> WeakSignal: Signal < 0.65

    WeakSignal --> WaitNext: Pas d'action
    WaitNext --> [*]

    StrongSignal --> ProposeTrader: Proposer trade

    ProposeTrader --> RiskCheck1: Check position size

    RiskCheck1 --> RiskCheck2: ✓ Taille OK
    RiskCheck1 --> Rejected: ✗ Trop grand

    RiskCheck2 --> RiskCheck3: ✓ Exposition OK
    RiskCheck2 --> Rejected: ✗ Trop exposé

    RiskCheck3 --> RiskCheck4: ✓ Perte OK
    RiskCheck3 --> Rejected: ✗ Limite atteinte

    RiskCheck4 --> RiskCheck5: ✓ R/R OK
    RiskCheck4 --> Rejected: ✗ Ratio faible

    RiskCheck5 --> Approved: ✓ Stop-loss OK
    RiskCheck5 --> Rejected: ✗ Pas de SL

    Rejected --> LogRejection
    LogRejection --> [*]

    Approved --> Execution
    Execution --> [*]
```

### Calcul des Paramètres de Trade

```python
# Signal fort détecté : ACHAT AAPL
symbol = "AAPL"
signal = 0.72  # Fort signal d'achat
current_price = 150.00

# 1. Calcul stop-loss (ATR)
atr = 2.50
stop_loss = current_price - (atr * 2)  # 150 - 5 = 145

# 2. Calcul take-profit (ratio 3:1)
risk_per_share = current_price - stop_loss  # 5
target_ratio = 3.0
take_profit = current_price + (risk_per_share * target_ratio)
# = 150 + (5 × 3) = 165

# 3. Calcul taille position
capital = 100_000
risk_per_trade = 0.01  # 1%
max_risk = capital * risk_per_trade  # 1000
quantity = max_risk / risk_per_share  # 1000 / 5 = 200

# 4. Limiter par max_position_size
quantity = min(quantity, 100)  # 100 actions max

# Paramètres finaux
trade_params = {
    'symbol': 'AAPL',
    'action': 'BUY',
    'quantity': 100,
    'price': 150.00,
    'stop_loss': 145.00,
    'take_profit': 165.00,
    'risk': 500,      # 100 × 5
    'reward': 1500    # 100 × 15
}
```

---

## Phase 5 : Exécution ⚡

```mermaid
sequenceDiagram
    participant Risk
    participant Executor
    participant IB
    participant Monitor

    Risk->>Executor: Trade approuvé + params
    Executor->>Executor: Choisir type ordre (Limit)

    Executor->>IB: Passer ordre LIMIT\nAAPL × 100 @ $150

    IB-->>Executor: Order ID: 12345
    Executor->>Executor: Démarrer timer (60s)

    alt Ordre rempli
        IB-->>Executor: Ordre exécuté @ $150.05
        Executor->>Monitor: Position ouverte
    else Timeout
        Executor->>IB: Annuler ordre
        IB-->>Executor: Ordre annulé
        Executor-->>Risk: Échec execution (timeout)
    end
```

### Types d'Ordres

#### 1. Market Order (Immédiat)

```python
order = {
    'type': 'MARKET',
    'symbol': 'AAPL',
    'quantity': 100,
    'action': 'BUY'
}

# Exécution immédiate au meilleur prix disponible
# Risque: slippage (prix différent de prévu)
```

#### 2. Limit Order (Contrôlé)

```python
order = {
    'type': 'LIMIT',
    'symbol': 'AAPL',
    'quantity': 100,
    'action': 'BUY',
    'limit_price': 150.00,
    'timeout': 60  # secondes
}

# Exécution uniquement à $150 ou mieux
# Avantage: contrôle du prix
# Risque: ordre non rempli
```

### Gestion du Slippage

```mermaid
graph TB
    Order[Ordre Limit @ $150] --> Wait[Attente exécution]

    Wait --> Filled{Ordre rempli?}

    Filled -->|@ $150.00| Perfect[✓ Prix parfait\nSlippage: 0%]
    Filled -->|@ $150.10| Acceptable[✓ Acceptable\nSlippage: 0.07%]
    Filled -->|@ $150.25| Excessive[✗ Trop élevé\nSlippage: 0.17%]
    Filled -->|Non rempli| Timeout[Timeout 60s]

    Excessive --> Cancel[Annuler]
    Timeout --> Cancel

    Perfect --> Confirm[Confirmer trade]
    Acceptable --> Confirm

    style Perfect fill:#00cc00
    style Acceptable fill:#ccffcc
    style Excessive fill:#ffcccc
```

---

## Phase 6 : Monitoring et Gestion 📈

```mermaid
stateDiagram-v2
    [*] --> PositionOpen: Trade exécuté

    PositionOpen --> MonitorPrice: Surveiller prix

    MonitorPrice --> CheckStop: Vérifier stop-loss
    MonitorPrice --> CheckTarget: Vérifier take-profit
    MonitorPrice --> CheckSignal: Vérifier signaux

    CheckStop --> StopHit: Prix ≤ Stop
    CheckTarget --> TargetHit: Prix ≥ Target
    CheckSignal --> SignalReverse: Signal inverse

    StopHit --> ClosePosition: Fermer (perte limitée)
    TargetHit --> ClosePosition: Fermer (profit)
    SignalReverse --> ClosePosition: Fermer (signal contraire)

    CheckStop --> MonitorPrice: OK
    CheckTarget --> MonitorPrice: OK
    CheckSignal --> MonitorPrice: OK

    ClosePosition --> RecordTrade: Enregistrer résultat
    RecordTrade --> UpdateStats: MAJ statistiques
    UpdateStats --> [*]
```

### Exemple Complet

```mermaid
gantt
    title Cycle de Vie Trade AAPL
    dateFormat HH:mm
    axisFormat %H:%M

    section Analyse
    Récupération données     :done, 09:30, 1m
    Analyse technique        :done, 09:31, 2m
    Analyse sentiment        :done, 09:31, 2m
    Combinaison signaux      :done, 09:33, 1m

    section Validation
    Validation risque        :done, 09:34, 1m
    Calcul paramètres        :done, 09:35, 1m

    section Exécution
    Passage ordre            :active, 09:36, 2m
    Position ouverte         :crit, 09:38, 120m

    section Monitoring
    Surveillance continue    :09:38, 120m
    Stop-loss atteint        :milestone, 11:38, 0m

    section Clôture
    Fermeture position       :11:38, 1m
    Enregistrement           :11:39, 1m
```

**Détails** :
- 09:30 : Récupération données AAPL
- 09:33 : Signal combiné = 0.72 (BUY)
- 09:35 : Trade validé (100 actions @ $150, SL $145)
- 09:38 : Position ouverte
- 11:38 : Stop-loss atteint @ $145
- **Résultat** : -$500 (100 × -$5)

---

## Cycle Complet Résumé

```mermaid
graph TB
    Start([Démarrage]) --> Init[Initialisation]

    Init --> Loop{Boucle 60s}

    Loop --> Fetch[1. Récupération données]
    Fetch --> Tech[2. Analyse technique]
    Fetch --> Sent[2. Analyse sentiment]

    Tech --> Combine[3. Combinaison]
    Sent --> Combine

    Combine --> Decision{Signal ≥ 0.65?}

    Decision -->|Non| Wait[Attendre]
    Wait --> Loop

    Decision -->|Oui| Risk[4. Validation risque]

    Risk -->|Rejeté| Log[Logging]
    Log --> Loop

    Risk -->|Approuvé| Exec[5. Exécution]

    Exec -->|Succès| Monitor[6. Monitoring]
    Exec -->|Échec| Loop

    Monitor --> Close{Position fermée?}

    Close -->|Non| Monitor
    Close -->|Oui| Record[Enregistrement]

    Record --> Loop

    style Init fill:#e3f2fd
    style Tech fill:#fff3e0
    style Sent fill:#f3e5f5
    style Risk fill:#ffe0e0
    style Exec fill:#e8f5e9
    style Monitor fill:#fff9e0
```

---

## Métriques et Logging

### Données Enregistrées

Pour chaque cycle :
```json
{
  "timestamp": "2026-02-20T09:30:00Z",
  "symbol": "AAPL",
  "signal_technical": 0.75,
  "signal_sentiment": 0.65,
  "signal_combined": 0.72,
  "decision": "BUY",
  "risk_validation": "APPROVED",
  "execution": "SUCCESS",
  "entry_price": 150.05,
  "stop_loss": 145.00,
  "take_profit": 165.00,
  "quantity": 100
}
```

Pour chaque trade fermé :
```json
{
  "trade_id": "12345",
  "open_time": "2026-02-20T09:38:00Z",
  "close_time": "2026-02-20T11:38:00Z",
  "symbol": "AAPL",
  "quantity": 100,
  "entry_price": 150.05,
  "exit_price": 145.00,
  "pnl": -505.00,
  "pnl_percent": -3.36,
  "exit_reason": "STOP_LOSS",
  "duration_minutes": 120
}
```

---

**Navigation**
- [← Architecture](./ARCHITECTURE.md)
- [← Système Multi-Agents](./AGENTS_SYSTEM.md)
- [← Indicateurs Techniques](./INDICATORS.md)
- [← Gestion des Risques](./RISK_MANAGEMENT_DETAILED.md)
- [→ Configuration](./CONFIGURATION.md)
