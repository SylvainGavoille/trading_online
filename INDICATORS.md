# Indicateurs Techniques

[← Retour Architecture](./ARCHITECTURE.md)

## Vue d'ensemble

Le système utilise **5 indicateurs techniques** principaux pour analyser les marchés et générer des signaux de trading.

```mermaid
graph TB
    OHLCV[Données OHLCV] --> Indicators[Calcul Indicateurs]

    Indicators --> SMA[SMA]
    Indicators --> EMA[EMA]
    Indicators --> RSI[RSI]
    Indicators --> MACD[MACD]
    Indicators --> BB[Bollinger Bands]

    SMA --> Trend[Analyse Tendance]
    EMA --> Trend

    RSI --> Momentum[Analyse Momentum]
    MACD --> Momentum

    BB --> Volatility[Analyse Volatilité]

    Trend --> Combine[Combinaison]
    Momentum --> Combine
    Volatility --> Combine

    Combine --> Signal[Signal Final]

    Signal -->|> 0.65| Buy[BUY]
    Signal -->|< -0.65| Sell[SELL]
    Signal -->|autre| Neutral[NEUTRAL]

    style Buy fill:#ccffcc
    style Sell fill:#ffcccc
    style Neutral fill:#ffffcc
```

## 1. SMA (Simple Moving Average) 📈

**Description** : Moyenne mobile simple, indique la tendance générale du prix.

### Calcul

```
SMA(n) = (Prix₁ + Prix₂ + ... + Prixₙ) / n
```

### Périodes utilisées

- **SMA 20** : Tendance court terme (1 mois)
- **SMA 50** : Tendance moyen terme (2.5 mois)
- **SMA 200** : Tendance long terme (1 an)

### Interprétation

```mermaid
graph LR
    Price[Prix] --> Compare{Comparaison}

    Compare -->|Prix > SMA 20| Bull1[Signal Haussier]
    Compare -->|Prix < SMA 20| Bear1[Signal Baissier]

    SMA20[SMA 20] --> Cross{Croisement}
    SMA50[SMA 50] --> Cross

    Cross -->|SMA 20 > SMA 50| GoldenCross[Golden Cross\nTrès Haussier]
    Cross -->|SMA 20 < SMA 50| DeathCross[Death Cross\nTrès Baissier]

    style GoldenCross fill:#ccffcc
    style DeathCross fill:#ffcccc
```

### Signaux

| Condition | Signal | Force |
|-----------|--------|-------|
| Prix > SMA 20 > SMA 50 > SMA 200 | Très haussier | +++++ |
| Prix > SMA 20 > SMA 50 | Haussier | +++ |
| Prix > SMA 20 | Faiblement haussier | + |
| Prix < SMA 20 | Faiblement baissier | - |
| Prix < SMA 20 < SMA 50 | Baissier | --- |
| Prix < SMA 20 < SMA 50 < SMA 200 | Très baissier | ----- |

### Configuration

```yaml
technical_analysis:
  indicators:
    sma_periods: [20, 50, 200]
```

---

## 2. EMA (Exponential Moving Average) ⚡

**Description** : Moyenne mobile exponentielle, réagit plus rapidement aux changements de prix que la SMA.

### Calcul

```
EMA(aujourd'hui) = (Prix × Multiplicateur) + (EMA(hier) × (1 - Multiplicateur))

Multiplicateur = 2 / (Période + 1)
```

### Périodes utilisées

- **EMA 12** : Court terme (2.5 semaines)
- **EMA 26** : Moyen terme (5 semaines)

### Différence avec SMA

```mermaid
graph LR
    subgraph "Réactivité"
        SMA[SMA] -->|Lente| Delay[Délai important]
        EMA[EMA] -->|Rapide| Quick[Réponse rapide]
    end

    Price[Prix] --> Change[Changement soudain]

    Change --> SMA
    Change --> EMA

    Delay -->|Bon pour| Trend[Tendances long terme]
    Quick -->|Bon pour| Entry[Points d'entrée]

    style EMA fill:#e3f2fd
    style SMA fill:#fff3e0
```

### Signaux

| Condition | Signal |
|-----------|--------|
| EMA 12 croise au-dessus EMA 26 | ACHAT (Signal haussier) |
| EMA 12 croise en-dessous EMA 26 | VENTE (Signal baissier) |
| EMA 12 > EMA 26 (écart croissant) | Tendance haussière forte |
| EMA 12 < EMA 26 (écart croissant) | Tendance baissière forte |

---

## 3. RSI (Relative Strength Index) 🎯

**Description** : Indicateur de momentum qui mesure la vitesse et l'amplitude des mouvements de prix. Identifie les conditions de surachat et survente.

### Calcul

```
RSI = 100 - (100 / (1 + RS))

RS = Moyenne des gains / Moyenne des pertes (sur n périodes)
```

### Zones

```mermaid
graph TB
    subgraph "Échelle RSI (0-100)"
        Zone1[0-30: SURVENTE]
        Zone2[30-70: NEUTRE]
        Zone3[70-100: SURACHAT]
    end

    Zone1 -->|Signal| Buy[ACHAT probable]
    Zone2 -->|Signal| Wait[Attendre]
    Zone3 -->|Signal| Sell[VENTE probable]

    style Zone1 fill:#ccffcc
    style Zone2 fill:#ffffcc
    style Zone3 fill:#ffcccc
```

### Interprétation

| RSI | Condition | Signal |
|-----|-----------|--------|
| < 30 | **Survente** | Signal d'achat (prix anormalement bas) |
| 30-40 | Faible | Potentiel d'achat |
| 40-60 | Neutre | Pas de signal clair |
| 60-70 | Élevé | Potentiel de vente |
| > 70 | **Surachat** | Signal de vente (prix anormalement haut) |

### Divergences

```mermaid
graph LR
    subgraph "Divergence Haussière"
        PriceLow1[Prix: Plus bas] --> PriceLow2[Prix: Encore plus bas]
        RSILow1[RSI: Bas] --> RSILow2[RSI: Moins bas]

        PriceLow2 --> Signal1[Signal ACHAT\nRetournement probable]
    end

    subgraph "Divergence Baissière"
        PriceHigh1[Prix: Plus haut] --> PriceHigh2[Prix: Encore plus haut]
        RSIHigh1[RSI: Haut] --> RSIHigh2[RSI: Moins haut]

        PriceHigh2 --> Signal2[Signal VENTE\nRetournement probable]
    end

    style Signal1 fill:#ccffcc
    style Signal2 fill:#ffcccc
```

### Configuration

```yaml
technical_analysis:
  indicators:
    rsi:
      period: 14
      overbought: 70
      oversold: 30
```

---

## 4. MACD (Moving Average Convergence Divergence) 📊

**Description** : Indicateur de momentum basé sur la différence entre deux moyennes mobiles. Excellent pour identifier les retournements de tendance.

### Composantes

```mermaid
graph TB
    EMA12[EMA 12] --> MACD[Ligne MACD]
    EMA26[EMA 26] --> MACD

    MACD -->|Calcul| Formula[MACD = EMA12 - EMA26]

    MACD --> Signal[Ligne Signal]
    Signal -->|Calcul| SignalFormula[Signal = EMA 9 du MACD]

    MACD --> Histogram[Histogramme]
    Signal --> Histogram
    Histogram -->|Calcul| HistFormula[Histo = MACD - Signal]
```

### Calcul

```
MACD Line = EMA(12) - EMA(26)
Signal Line = EMA(9) du MACD
Histogramme = MACD Line - Signal Line
```

### Signaux

```mermaid
graph TB
    MACD[MACD] --> Cross{Croisement}

    Cross -->|MACD > Signal| Bullish[Signal HAUSSIER]
    Cross -->|MACD < Signal| Bearish[Signal BAISSIER]

    MACD --> Zero{Position vs 0}

    Zero -->|MACD > 0| UpTrend[Tendance haussière]
    Zero -->|MACD < 0| DownTrend[Tendance baissière]

    MACD --> Divergence{Divergence}

    Divergence -->|Prix monte,\nMACD descend| TopDiv[Divergence sommet\nVENTE]
    Divergence -->|Prix descend,\nMACD monte| BottomDiv[Divergence creux\nACHAT]

    style Bullish fill:#ccffcc
    style Bearish fill:#ffcccc
    style TopDiv fill:#ffcccc
    style BottomDiv fill:#ccffcc
```

### Interprétation

| Condition | Signal | Force |
|-----------|--------|-------|
| MACD croise au-dessus Signal | ACHAT | +++ |
| MACD croise en-dessous Signal | VENTE | --- |
| Histogramme croissant | Momentum haussier | ++ |
| Histogramme décroissant | Momentum baissier | -- |
| MACD > 0 et croissant | Tendance haussière forte | ++++ |
| MACD < 0 et décroissant | Tendance baissière forte | ---- |

### Configuration

```yaml
technical_analysis:
  indicators:
    macd:
      fast_period: 12
      slow_period: 26
      signal_period: 9
```

---

## 5. Bollinger Bands (Bandes de Bollinger) 🎚️

**Description** : Indicateur de volatilité composé de 3 bandes. Identifie les périodes de forte/faible volatilité et les points de retournement potentiels.

### Structure

```mermaid
graph TB
    SMA20[SMA 20] --> Middle[Bande Centrale]

    StdDev[Écart-type] --> Upper[Bande Supérieure]
    StdDev --> Lower[Bande Inférieure]

    Middle --> Upper
    Middle --> Lower

    Upper -->|Calcul| UpperFormula[Sup = SMA + 2×σ]
    Lower -->|Calcul| LowerFormula[Inf = SMA - 2×σ]
```

### Calcul

```
Bande Centrale = SMA(20)
Bande Supérieure = SMA(20) + (2 × Écart-type)
Bande Inférieure = SMA(20) - (2 × Écart-type)
```

### Interprétation

```mermaid
graph TB
    Price[Prix] --> Position{Position}

    Position -->|Prix touche\nbande sup| Upper[Zone de surachat\nVENTE probable]
    Position -->|Prix touche\nbande inf| Lower[Zone de survente\nACHAT probable]
    Position -->|Prix au centre| Middle[Neutre]

    Bands[Largeur bandes] --> Width{Écartement}

    Width -->|Bandes serrées| Squeeze[Squeeze\nÉclatement imminent]
    Width -->|Bandes larges| Expansion[Forte volatilité\nTendance établie]

    Squeeze --> Breakout[Attendre cassure]
    Breakout -->|Cassure haute| BuySignal[Signal ACHAT]
    Breakout -->|Cassure basse| SellSignal[Signal VENTE]

    style Upper fill:#ffcccc
    style Lower fill:#ccffcc
    style BuySignal fill:#ccffcc
    style SellSignal fill:#ffcccc
```

### Signaux

| Condition | Signal |
|-----------|--------|
| Prix touche bande inférieure | Survente → ACHAT probable |
| Prix touche bande supérieure | Surachat → VENTE probable |
| Prix rebondit sur bande centrale | Continuation tendance |
| Bandes se resserrent | Volatilité faible → Éclatement imminent |
| Bandes s'élargissent | Volatilité forte → Tendance en cours |

### Stratégie Squeeze

```mermaid
stateDiagram-v2
    [*] --> Normal: Volatilité normale

    Normal --> Squeeze: Bandes se resserrent
    Squeeze --> Breakout: Prix casse une bande

    Breakout --> UpBreak: Cassure haute
    Breakout --> DownBreak: Cassure basse

    UpBreak --> BuyTrade: ACHAT + Stop sous bande inf
    DownBreak --> SellTrade: VENTE + Stop sur bande sup

    BuyTrade --> Expansion: Bandes s'élargissent
    SellTrade --> Expansion

    Expansion --> Normal: Retour normal
```

### Configuration

```yaml
technical_analysis:
  indicators:
    bollinger_bands:
      period: 20
      std_dev: 2  # Nombre d'écarts-types
```

---

## Combinaison des Indicateurs

Le système combine tous les indicateurs pour générer un signal final :

```mermaid
graph TB
    subgraph "Analyse Tendance"
        SMA[SMA 20/50/200]
        EMA[EMA 12/26]
    end

    subgraph "Analyse Momentum"
        RSI[RSI 14]
        MACD[MACD]
    end

    subgraph "Analyse Volatilité"
        BB[Bollinger Bands]
    end

    SMA --> TrendScore[Score Tendance]
    EMA --> TrendScore

    RSI --> MomentumScore[Score Momentum]
    MACD --> MomentumScore

    BB --> VolatilityScore[Score Volatilité]

    TrendScore --> Normalize[Normalisation -1 à +1]
    MomentumScore --> Normalize
    VolatilityScore --> Normalize

    Normalize --> Combine[Combinaison pondérée]

    Combine --> Final{Signal Final}

    Final -->|> 0.65| StrongBuy[ACHAT FORT]
    Final -->|0.3 à 0.65| WeakBuy[ACHAT FAIBLE]
    Final -->|-0.3 à 0.3| Neutral[NEUTRE]
    Final -->|-0.65 à -0.3| WeakSell[VENTE FAIBLE]
    Final -->|< -0.65| StrongSell[VENTE FORTE]

    style StrongBuy fill:#00cc00
    style WeakBuy fill:#ccffcc
    style Neutral fill:#ffffcc
    style WeakSell fill:#ffcccc
    style StrongSell fill:#cc0000
```

### Formule de Combinaison

```python
# Normalisation RSI
rsi_signal = (rsi_value - 50) / 50  # -1 à +1

# Normalisation MACD
macd_signal = tanh(macd_value)  # -1 à +1

# Position Bollinger
bb_position = (prix - bande_inf) / (bande_sup - bande_inf)
bb_signal = 2 * (bb_position - 0.5)  # -1 à +1

# Signal combiné
signal_final = (rsi_signal + macd_signal + bb_signal) / 3
```

### Poids par Indicateur

| Indicateur | Poids | Justification |
|------------|-------|---------------|
| SMA/EMA | 30% | Tendance générale |
| RSI | 25% | Surachat/survente |
| MACD | 25% | Momentum et retournements |
| Bollinger | 20% | Volatilité et extrêmes |

---

## Visualisation des Signaux

```mermaid
graph LR
    subgraph "Exemple: AAPL @ 150$"
        Data[Données] --> Calc[Calculs]

        Calc --> R[RSI = 28\nSURVENTE]
        Calc --> M[MACD = +0.5\nHAUSSIER]
        Calc --> B[BB Position = 0.15\nProche bande inf]
        Calc --> S[SMA 20 = 152$\nPrix sous SMA]

        R --> Score1[Score: +0.56]
        M --> Score2[Score: +0.46]
        B --> Score3[Score: -0.70]
        S --> Score4[Score: -0.10]

        Score1 --> Final[Signal: +0.31]
        Score2 --> Final
        Score3 --> Final
        Score4 --> Final

        Final --> Decision[ACHAT FAIBLE]
    end

    style R fill:#ccffcc
    style M fill:#ccffcc
    style Decision fill:#ccffcc
```

---

## Implémentation

### Fichier source

`src/analysis/technical_analysis.py`

### Classes et méthodes

```python
class TechnicalAnalysis:
    def __init__(self, data: pd.DataFrame)

    # Moyennes mobiles
    def sma(self, period: int) -> pd.Series
    def ema(self, period: int) -> pd.Series

    # Momentum
    def rsi(self, period: int = 14) -> pd.Series
    def macd(self, fast: int = 12, slow: int = 26, signal: int = 9) -> tuple

    # Volatilité
    def bollinger_bands(self, period: int = 20, std_dev: int = 2) -> tuple

    # Évaluation globale
    def evaluate(self, market_data: pd.DataFrame) -> float
```

---

**Navigation**
- [← Architecture](./ARCHITECTURE.md)
- [← Système Multi-Agents](./AGENTS_SYSTEM.md)
- [→ Gestion des Risques](./RISK_MANAGEMENT_DETAILED.md)
- [→ Flux de Travail](./WORKFLOW.md)
