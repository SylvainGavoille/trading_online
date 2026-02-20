# Gestion des Risques - Guide Détaillé

[← Retour Architecture](./ARCHITECTURE.md)

## Vue d'ensemble

La gestion des risques est **le pilier central** du système Quantum Trader. Chaque trade passe par **5 validations** obligatoires avant exécution.

```mermaid
graph TB
    Trade[Proposition Trade] --> Validator[Risk Validator]

    Validator --> Check1[1. Taille Position]
    Validator --> Check2[2. Exposition Portfolio]
    Validator --> Check3[3. Limite Perte Journalière]
    Validator --> Check4[4. Ratio Risk/Reward]
    Validator --> Check5[5. Stop-Loss]

    Check1 -->|✓| Check2
    Check2 -->|✓| Check3
    Check3 -->|✓| Check4
    Check4 -->|✓| Check5
    Check5 -->|✓| Approved[✅ APPROUVÉ]

    Check1 -->|✗| Rejected[❌ REJETÉ]
    Check2 -->|✗| Rejected
    Check3 -->|✗| Rejected
    Check4 -->|✗| Rejected
    Check5 -->|✗| Rejected

    style Approved fill:#ccffcc
    style Rejected fill:#ffcccc
```

---

## 1. Limite de Taille de Position 📏

**Objectif** : Éviter une exposition excessive sur un seul titre.

### Règle

```yaml
risk_management:
  position_limits:
    max_position_size: 100  # Maximum 100 actions par position
```

### Validation

```mermaid
graph LR
    Proposed[Quantité proposée] --> Check{Quantité ≤ Max?}

    Check -->|Oui| Valid[✓ Valide]
    Check -->|Non| Invalid[✗ Invalide]

    Invalid --> Reject[REJETÉ:\n"Position size too large"]

    style Valid fill:#ccffcc
    style Invalid fill:#ffcccc
```

### Exemple

| Symbole | Quantité demandée | Max autorisé | Résultat |
|---------|-------------------|--------------|----------|
| AAPL | 50 | 100 | ✅ Approuvé |
| MSFT | 120 | 100 | ❌ Rejeté : "Taille max = 100" |
| GOOGL | 100 | 100 | ✅ Approuvé (limite exacte) |

### Calcul Dynamique (Optionnel)

Le système peut calculer la taille optimale basée sur le capital :

```python
# Méthode: risk_based
capital_total = 100_000  # $100k
risk_per_trade = 0.01    # 1% du capital
prix_action = 150        # AAPL @ $150
stop_loss_distance = 5   # $5 de risque par action

quantite_max = (capital_total * risk_per_trade) / stop_loss_distance
# = (100_000 * 0.01) / 5 = 200 actions

# Mais limité par max_position_size
quantite_finale = min(quantite_max, max_position_size)
# = min(200, 100) = 100 actions
```

---

## 2. Limite d'Exposition du Portfolio 💼

**Objectif** : Éviter la sur-concentration du capital sur un nombre limité de titres.

### Règle

```yaml
risk_management:
  position_limits:
    max_portfolio_exposure: 0.25  # Maximum 25% du portfolio
```

### Validation

```mermaid
graph TB
    Portfolio[Valeur Portfolio:\n$100,000] --> CurrentExp[Exposition actuelle:\n$20,000 = 20%]

    NewTrade[Nouveau trade:\nAAPL × 50 @ $150\n= $7,500] --> Calc[Calcul nouvelle exposition]

    CurrentExp --> Calc
    Calc --> NewExp[Nouvelle exposition:\n$27,500 = 27.5%]

    NewExp --> Check{27.5% ≤ 25%?}

    Check -->|Non| Reject[❌ REJETÉ:\nExposition excessive]
    Check -->|Oui| Approve[✅ APPROUVÉ]

    style Reject fill:#ffcccc
    style Approve fill:#ccffcc
```

### Exemple Détaillé

**Situation actuelle** :
| Position | Quantité | Prix | Valeur | % Portfolio |
|----------|----------|------|--------|-------------|
| MSFT | 100 | $300 | $30,000 | 15% |
| GOOGL | 50 | $140 | $7,000 | 3.5% |
| Cash | - | - | $63,000 | 31.5% |
| **Total** | - | - | **$100,000** | **50%** |

**Exposition totale actuelle** : $37,000 (18.5%)

**Nouveau trade proposé** : AAPL × 100 @ $150 = $15,000

**Nouvelle exposition** : $37,000 + $15,000 = $52,000 (26%)

**Résultat** : ❌ **REJETÉ** (26% > 25%)

**Solution** : Réduire à AAPL × 46 @ $150 = $6,900
- Nouvelle exposition : $43,900 (21.95%) ✅

### Formule

```python
def check_portfolio_exposure(portfolio_value, current_positions, new_trade):
    # Valeur totale des positions actuelles
    current_exposure = sum(pos.quantity * pos.price for pos in current_positions)

    # Valeur du nouveau trade
    new_trade_value = new_trade.quantity * new_trade.price

    # Exposition totale après trade
    total_exposure = current_exposure + new_trade_value

    # Ratio d'exposition
    exposure_ratio = total_exposure / portfolio_value

    # Validation
    max_exposure = 0.25  # 25%
    return exposure_ratio <= max_exposure
```

---

## 3. Limite de Perte Journalière 📉

**Objectif** : Limiter les dégâts lors d'une mauvaise journée de trading.

### Règle

```yaml
risk_management:
  loss_limits:
    daily_loss_limit: 1000  # Maximum $1,000 de perte par jour
```

### Suivi en Temps Réel

```mermaid
stateDiagram-v2
    [*] --> DayStart: Nouvelle journée

    DayStart --> Trading: P&L = $0

    Trading --> CheckTrade: Nouveau trade

    CheckTrade --> ExecuteTrade: Exécuter
    CheckTrade --> RejectTrade: Rejeter

    ExecuteTrade --> Win: Trade gagnant (+$200)
    ExecuteTrade --> Loss: Trade perdant (-$300)

    Win --> UpdatePL1: P&L = +$200
    Loss --> UpdatePL2: P&L = -$300

    UpdatePL1 --> CheckLimit1: P&L > -$1000?
    UpdatePL2 --> CheckLimit2: P&L > -$1000?

    CheckLimit1 -->|Oui| Trading
    CheckLimit2 -->|Oui| Trading

    CheckLimit2 -->|Non| LimitReached: LIMITE ATTEINTE

    LimitReached --> StopTrading: Arrêt trading
    StopTrading --> DayEnd: Fin journée

    DayEnd --> [*]
```

### Exemple

**Historique de la journée** :
| Heure | Trade | Résultat | P&L Cumulé |
|-------|-------|----------|------------|
| 09:30 | AAPL ACHAT | +$150 | +$150 |
| 10:15 | MSFT VENTE | -$200 | -$50 |
| 11:00 | GOOGL ACHAT | +$300 | +$250 |
| 13:30 | TSLA ACHAT | -$600 | -$350 |
| 14:45 | NVDA VENTE | -$400 | -$750 |
| **15:20** | **AAPL VENTE** | **-$300** | **-$1,050** ❌ |

**À 15:20** : P&L = -$1,050
- Dépasse limite de -$1,000
- **Système bloque tous les nouveaux trades**
- Notification envoyée à l'utilisateur
- Reprise le lendemain

### Protection Proactive

Le système peut **refuser un trade** si la perte potentielle dépasserait la limite :

```python
current_loss = -750  # Déjà -$750 aujourd'hui
max_daily_loss = -1000
remaining_risk = max_daily_loss - current_loss  # -$250

proposed_trade_risk = -300  # Trade risque -$300

if abs(proposed_trade_risk) > abs(remaining_risk):
    return "REJECTED: Would exceed daily loss limit"
```

---

## 4. Ratio Risk/Reward 🎯

**Objectif** : S'assurer que chaque trade a un potentiel de gain supérieur au risque encouru.

### Règle

```yaml
risk_management:
  risk_reward:
    min_ratio: 2.0    # Minimum 2:1 (gagner 2× ce qui est risqué)
    target_ratio: 3.0 # Idéal 3:1
```

### Calcul

```mermaid
graph TB
    Entry[Prix d'entrée:\n$150] --> Stop[Stop-Loss:\n$148]
    Entry --> Target[Take-Profit:\n$156]

    Stop --> Risk[Risque:\n$150 - $148 = $2]
    Target --> Reward[Gain potentiel:\n$156 - $150 = $6]

    Risk --> Ratio[Ratio:\n$6 / $2 = 3.0]
    Reward --> Ratio

    Ratio --> Check{Ratio ≥ 2.0?}

    Check -->|3.0 ≥ 2.0| Approve[✅ APPROUVÉ\nExcellent ratio!]
    Check -->|< 2.0| Reject[❌ REJETÉ\nRatio insuffisant]

    style Approve fill:#ccffcc
    style Reject fill:#ffcccc
```

### Exemple

| Titre | Prix Entrée | Stop-Loss | Take-Profit | Risque | Gain | Ratio | Résultat |
|-------|-------------|-----------|-------------|--------|------|-------|----------|
| AAPL | $150 | $148 | $156 | $2 | $6 | **3.0** | ✅ Excellent |
| MSFT | $300 | $295 | $308 | $5 | $8 | **1.6** | ❌ Rejeté (< 2.0) |
| GOOGL | $140 | $137 | $146 | $3 | $6 | **2.0** | ✅ Acceptable |
| TSLA | $200 | $198 | $206 | $2 | $6 | **3.0** | ✅ Excellent |

### Formule

```python
def calculate_risk_reward(entry_price, stop_loss, take_profit):
    risk = abs(entry_price - stop_loss)
    reward = abs(take_profit - entry_price)

    if risk == 0:
        return None  # Éviter division par zéro

    ratio = reward / risk

    return {
        'ratio': ratio,
        'approved': ratio >= 2.0,
        'risk_amount': risk,
        'reward_amount': reward
    }
```

### Placement Optimal

```mermaid
graph TB
    subgraph "Trade AAPL"
        Entry[Entrée: $150]

        Entry -->|Risque -2%| SL[Stop-Loss: $147]
        Entry -->|Gain +4%| TP1[Take-Profit 1: $156]
        Entry -->|Gain +6%| TP2[Take-Profit 2: $159]

        SL -->|Ratio| R1[Ratio TP1: 2.0 ✅]
        TP1 -->|Ratio| R1

        SL -->|Ratio| R2[Ratio TP2: 3.0 ✅✅]
        TP2 -->|Ratio| R2
    end

    style R1 fill:#ccffcc
    style R2 fill:#00cc00
```

---

## 5. Stop-Loss Dynamique 🛑

**Objectif** : Limiter les pertes sur chaque position individuelle.

### Calcul avec ATR

Le stop-loss est calculé dynamiquement en utilisant l'**ATR (Average True Range)** :

```mermaid
graph TB
    Price[Prix actuel:\n$150] --> ATR[ATR 14:\n$2.50]

    ATR --> Multiplier[Multiplicateur:\n×2]

    Multiplier --> Distance[Distance stop-loss:\n$2.50 × 2 = $5]

    Distance --> StopLong[ACHAT:\nStop = $150 - $5 = $145]
    Distance --> StopShort[VENTE:\nStop = $150 + $5 = $155]
```

### Configuration

```yaml
risk_management:
  stop_loss:
    atr_multiplier: 2  # 2× l'ATR
    max_loss_per_trade: 0.02  # Max 2% du capital par trade
```

### Exemple ACHAT

**Données** :
- Prix actuel AAPL : **$150**
- ATR(14) : **$2.50**
- Multiplicateur : **2**

**Calcul** :
```
Distance = ATR × Multiplicateur = $2.50 × 2 = $5
Stop-Loss = Prix - Distance = $150 - $5 = $145
Risque par action = $5
```

**Validation avec capital** :
```
Capital total : $100,000
Max perte par trade : 2% = $2,000
Quantité max = $2,000 / $5 = 400 actions

Mais limité par max_position_size = 100 actions
Quantité finale = 100 actions
Risque total = 100 × $5 = $500 ✅
```

### Stop-Loss Trailing

Une fois le trade en profit, le stop-loss **suit** le prix :

```mermaid
stateDiagram-v2
    [*] --> EntryLong: Achat AAPL @ $150

    EntryLong --> InitialStop: Stop initial = $145

    InitialStop --> PriceUp1: Prix monte à $152

    PriceUp1 --> TrailingStop1: Nouveau stop = $147\n(suit prix)

    TrailingStop1 --> PriceUp2: Prix monte à $155

    PriceUp2 --> TrailingStop2: Nouveau stop = $150\n(breakeven)

    TrailingStop2 --> PriceUp3: Prix monte à $158

    PriceUp3 --> TrailingStop3: Nouveau stop = $153\n(profit garanti)

    TrailingStop3 --> PriceDown: Prix redescend à $153

    PriceDown --> StopHit: Stop atteint!

    StopHit --> CloseTrade: Fermeture position\nProfit: +$3/action

    CloseTrade --> [*]
```

### Code d'implémentation

```python
def calculate_dynamic_stop_loss(current_price, atr_value, multiplier=2, position_type='long'):
    """
    Calcule le stop-loss dynamique basé sur l'ATR

    Args:
        current_price: Prix actuel du titre
        atr_value: Valeur de l'ATR(14)
        multiplier: Multiplicateur ATR (default: 2)
        position_type: 'long' ou 'short'

    Returns:
        Prix du stop-loss
    """
    distance = atr_value * multiplier

    if position_type == 'long':
        stop_loss = current_price - distance
    else:  # short
        stop_loss = current_price + distance

    return round(stop_loss, 2)
```

---

## 6. Drawdown Maximum 📊

**Objectif** : Limiter la baisse maximale du capital depuis le pic historique.

### Règle

```yaml
risk_management:
  loss_limits:
    max_drawdown: 0.15  # Maximum 15% de baisse depuis le pic
```

### Calcul

```mermaid
graph TB
    Peak[Pic historique:\n$120,000] --> Current[Capital actuel:\n$105,000]

    Current --> Calc[Drawdown:\n($120k - $105k) / $120k]

    Calc --> Result[= $15k / $120k\n= 12.5%]

    Result --> Check{12.5% ≤ 15%?}

    Check -->|Oui| Safe[✅ Dans les limites\nTrading continue]
    Check -->|Non| Danger[❌ Limite dépassée\nArrêt trading]

    style Safe fill:#ccffcc
    style Danger fill:#ffcccc
```

### Exemple Détaillé

**Historique du capital** :

| Date | Capital | Pic précédent | Drawdown | Action |
|------|---------|---------------|----------|--------|
| 01/01 | $100,000 | $100,000 | 0% | ✅ Trading |
| 15/01 | $115,000 | $115,000 | 0% | ✅ Trading |
| 01/02 | $108,000 | $115,000 | 6.1% | ✅ Trading |
| 15/02 | $102,000 | $115,000 | 11.3% | ✅ Trading |
| 01/03 | $97,500 | $115,000 | **15.2%** | ❌ **STOP** |

**Le 01/03** :
- Drawdown = ($115,000 - $97,500) / $115,000 = 15.2%
- Dépasse la limite de 15%
- **Tous les trades sont bloqués**
- Notification d'urgence envoyée
- Nécessite intervention manuelle pour reprendre

### Graphique de Suivi

```mermaid
graph LR
    subgraph "Évolution Capital"
        T0[T0: $100k\nPeak: $100k\nDD: 0%]
        T1[T1: $115k\nPeak: $115k\nDD: 0%]
        T2[T2: $108k\nPeak: $115k\nDD: 6.1%]
        T3[T3: $102k\nPeak: $115k\nDD: 11.3%]
        T4[T4: $97.5k\nPeak: $115k\nDD: 15.2%]

        T0 --> T1
        T1 --> T2
        T2 --> T3
        T3 --> T4

        T4 -->|STOP| Alert[🚨 Trading arrêté]
    end

    style T0 fill:#ccffcc
    style T1 fill:#ccffcc
    style T2 fill:#ffffcc
    style T3 fill:#ffddcc
    style T4 fill:#ffcccc
    style Alert fill:#cc0000,color:#fff
```

---

## Hiérarchie des Validations

```mermaid
graph TB
    Start[Nouveau Trade Proposé] --> V1{1. Position Size}

    V1 -->|✗| R1[Rejeté: Taille excessive]
    V1 -->|✓| V2{2. Portfolio Exposure}

    V2 -->|✗| R2[Rejeté: Exposition excessive]
    V2 -->|✓| V3{3. Daily Loss}

    V3 -->|✗| R3[Rejeté: Limite journalière]
    V3 -->|✓| V4{4. Risk/Reward}

    V4 -->|✗| R4[Rejeté: Ratio insuffisant]
    V4 -->|✓| V5{5. Stop-Loss}

    V5 -->|✗| R5[Rejeté: Stop manquant]
    V5 -->|✓| V6{6. Drawdown}

    V6 -->|✗| R6[Rejeté: Drawdown max]
    V6 -->|✓| Approved[✅ TRADE APPROUVÉ]

    R1 --> Log[Logging + Stats]
    R2 --> Log
    R3 --> Log
    R4 --> Log
    R5 --> Log
    R6 --> Log

    Approved --> Execute[Exécution]

    style Approved fill:#ccffcc
    style R1 fill:#ffcccc
    style R2 fill:#ffcccc
    style R3 fill:#ffcccc
    style R4 fill:#ffcccc
    style R5 fill:#ffcccc
    style R6 fill:#ffcccc
```

---

## Configuration Complète

```yaml
risk_management:
  # Limites de position
  position_limits:
    max_position_size: 100
    max_portfolio_exposure: 0.25

  # Limites de perte
  loss_limits:
    daily_loss_limit: 1000
    max_drawdown: 0.15

  # Fréquence de trading
  trade_frequency:
    min_time_between_trades: 300  # 5 minutes
    max_daily_trades: 10

  # Stop-loss
  stop_loss:
    atr_multiplier: 2
    max_loss_per_trade: 0.02

  # Risk/Reward
  risk_reward:
    min_ratio: 2.0
    target_ratio: 3.0
```

---

## Fichiers d'Implémentation

| Fichier | Responsabilité |
|---------|----------------|
| `src/trading/agents/risk_validator.py` | Validation principale |
| `src/config/config.yaml` | Paramètres de risque |
| `docs/risk_management.md` | Documentation originale |

---

**Navigation**
- [← Architecture](./ARCHITECTURE.md)
- [← Système Multi-Agents](./AGENTS_SYSTEM.md)
- [← Indicateurs Techniques](./INDICATORS.md)
- [→ Flux de Travail](./WORKFLOW.md)
