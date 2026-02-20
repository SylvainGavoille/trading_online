# Guide des Frais IBKR - Intégration Complète

## 💰 Frais Interactive Brokers Intégrés

Le système calcule maintenant automatiquement **tous les frais IBKR** pour des calculs de P&L précis.

---

## 📊 Structure des Frais IBKR

### IBKR Pro (Par Défaut)

**Commissions** :
- **$0.005 par action**
- **Minimum** : $1.00 par ordre
- **Maximum** : 1% de la valeur du trade

**Frais Réglementaires (Ventes uniquement)** :
- **SEC Fee** : $27.80 par $1,000,000 de principal (0.00278%)
- **FINRA TAF** : $0.166 par 1,000 actions (0.0166 ¢/action)

### IBKR Lite

**Commissions** :
- **$0** pour actions US
- Pas de frais minimum

**Note** : Peut avoir des frais de routing non couverts ici

---

## 🔧 Configuration

**Fichier** : `src/config/config.yaml`

```yaml
fees:
  ibkr_plan: "pro"              # Options: "pro", "lite", "tiered"
  per_share_rate: 0.005         # $0.005 par action
  min_commission: 1.00          # Minimum $1.00 par ordre
  max_commission_pct: 0.01      # Maximum 1% de la valeur
  sec_fee_rate: 0.0000278       # SEC: $27.80 per $1M (ventes)
  finra_taf_rate: 0.000166      # FINRA: $0.166 per 1000 shares (ventes)
```

**Pour passer à IBKR Lite** :
```yaml
fees:
  ibkr_plan: "lite"  # Commissions à $0
```

---

## 💡 Utilisation

### Import
```python
from src.trading.fee_calculator import FeeCalculator

fee_calc = FeeCalculator(config)
```

### Calculer Frais d'Achat

```python
# 100 actions @ $150
fees = fee_calc.calculate_total_fees(
    quantity=100,
    price=150.00,
    side='buy'
)

print(fees)
# {
#     'commission': 1.00,        # max($0.50, $1.00 min) = $1.00
#     'sec_fee': 0.00,          # Pas de SEC fee sur achats
#     'finra_taf': 0.00,        # Pas de FINRA sur achats
#     'total_regulatory': 0.00,
#     'total_fees': 1.00,
#     'trade_value': 15000.00
# }
```

### Calculer Frais de Vente

```python
# 100 actions @ $155
fees = fee_calc.calculate_total_fees(
    quantity=100,
    price=155.00,
    side='sell'
)

print(fees)
# {
#     'commission': 1.00,              # $0.005 * 100 = $0.50 → $1.00 min
#     'sec_fee': 0.43,                # $15,500 * 0.0000278
#     'finra_taf': 0.02,              # 100 * 0.000166
#     'total_regulatory': 0.45,
#     'total_fees': 1.45,
#     'trade_value': 15500.00
# }
```

### Calculer P&L Net (Après Frais)

```python
# Achat: 100 @ $150.00
# Vente: 100 @ $155.00
pnl = fee_calc.calculate_net_pnl(
    quantity=100,
    entry_price=150.00,
    exit_price=155.00
)

print(pnl)
# {
#     'quantity': 100,
#     'entry_price': 150.00,
#     'exit_price': 155.00,
#     'gross_pnl': 500.00,           # ($155 - $150) * 100
#     'total_fees': 2.45,            # Entry $1.00 + Exit $1.45
#     'net_pnl': 497.55,             # $500 - $2.45
#     'gross_return_pct': 3.33,      # 3.33% avant frais
#     'net_return_pct': 3.32,        # 3.32% après frais
#     'fee_impact_pct': 0.49         # Frais = 0.49% du profit
# }
```

### Calculer Prix Cible Ajusté

```python
# Quel prix viser pour 1% de profit NET après frais ?
target = fee_calc.adjust_target_for_fees(
    entry_price=150.00,
    quantity=100,
    min_profit_pct=1.0
)

print(target)
# 151.52  # Besoin de $151.52 pour avoir 1% net après $2.45 frais
```

---

## 🎯 Intégration Automatique

### 1. Risk Validator

**Les frais sont maintenant inclus dans le calcul du Risk/Reward ratio** :

```python
# Avant (sans frais)
Gross R/R = $500 profit / $250 loss = 2.0

# Maintenant (avec frais)
Net R/R = ($500 - $2.45 fees) / ($250 + $2.45 fees) = 1.97

# Si ratio < 2.0 requis → Trade rejeté !
```

**Code** : `src/trading/agents/risk_validator.py`

```python
def _check_risk_reward_ratio(self, trade_params):
    # Calculate fees
    fees = self.fee_calculator.calculate_round_trip_fees(
        position_size, current_price, target_price
    )

    # Adjust for fees
    potential_reward_net = potential_reward_gross - fees['total_round_trip_fees']
    potential_loss_net = potential_loss_gross + fees['total_round_trip_fees']

    # Check net ratio
    risk_reward_ratio_net = potential_reward_net / potential_loss_net
```

### 2. Trade Executor

**Les frais sont calculés et loggés à chaque exécution** :

```python
# Lors de l'exécution
execution_result = {
    'status': 'executed',
    'fees': {
        'entry_fees': 1.00,
        'estimated_exit_fees': 1.45,
        'estimated_total_fees': 2.45,
        'expected_net_pnl': 497.55
    }
}
```

**Log Output** :
```
Trade executed: AAPL 100 @ $150.00 | Fees: $1.00
```

---

## 📈 Exemples Pratiques

### Exemple 1 : Small Trade (Minimum Commission)

```python
# 10 actions @ $50
fees = fee_calc.calculate_total_fees(10, 50.00, 'buy')
# Commission = 10 * $0.005 = $0.05 → $1.00 minimum
# Total fees = $1.00

# Impact: Sur $500 de trade, $1.00 = 0.20%
```

### Exemple 2 : Large Trade (Pourcentage Max)

```python
# 10,000 actions @ $50
fees = fee_calc.calculate_total_fees(10000, 50.00, 'buy')
# Commission = 10,000 * $0.005 = $50.00
# Max = $500,000 * 0.01 = $5,000
# Capped at $50.00 (sous le max)
# Total fees = $50.00
```

### Exemple 3 : Round Trip Complet

```python
# Achat: 500 actions @ $75
# Vente: 500 actions @ $80

fees = fee_calc.calculate_round_trip_fees(500, 75.00, 80.00)
# {
#     'entry_fees': 2.50,           # 500 * $0.005
#     'exit_fees': 3.68,            # $2.50 + $1.04 SEC + $0.08 FINRA
#     'total_round_trip_fees': 6.18,
#     'total_commission': 5.00,
#     'total_regulatory': 1.12
# }

# Profit analysis
pnl = fee_calc.calculate_net_pnl(500, 75.00, 80.00)
# Gross profit: $2,500
# Net profit: $2,493.82  (après $6.18 frais)
# Fee impact: 0.25% du profit brut
```

### Exemple 4 : Scalping (Impact Élevé)

```python
# Scalping: 1000 actions, gain de $0.10/action
pnl = fee_calc.calculate_net_pnl(1000, 100.00, 100.10)

# Gross profit: $100
# Fees: ~$8.50
# Net profit: $91.50
# Fee impact: 8.5% du profit !

# ⚠️ Warning: Frais mangent une grosse partie du profit
```

---

## 🎓 Comprendre l'Impact des Frais

### Impact par Type de Stratégie

| Stratégie | Trade Typique | Frais | Impact |
|-----------|---------------|-------|--------|
| **Day Trading** | 100 actions @ $50 | $2.45 | 0.10% - 0.50% |
| **Swing Trading** | 500 actions @ $100 | $6.18 | 0.05% - 0.15% |
| **Position Trading** | 1000 actions @ $150 | $10.41 | 0.03% - 0.10% |
| **Scalping** | 1000 actions, $0.10 gain | $8.50 | **5% - 10%** ⚠️ |

### Minimum Profit Requis

Pour couvrir les frais sur un round trip :

```python
# 100 actions @ $100
fees = $2.45 total

# Minimum gain requis = $2.45 / 100 = $0.025/action
# Soit 0.025% du prix

# Pour 1% profit NET: besoin de ~1.025% gain BRUT
```

---

## 🔍 Vérification des Frais

### Test Rapide

```python
from src.trading.fee_calculator import FeeCalculator

fee_calc = FeeCalculator(config)

# Vérifier la configuration
summary = fee_calc.get_fee_summary()
print(summary)
# {
#     'plan': 'pro',
#     'per_share_rate': 0.005,
#     'min_commission': 1.0,
#     'description': 'IBKR Pro: $0.005 per share (min $1.0, max 1%)'
# }

# Test avec trade de 100 actions @ $150
pnl = fee_calc.calculate_net_pnl(100, 150.00, 155.00)
print(f"Profit net: ${pnl['net_pnl']:.2f}")
print(f"Frais totaux: ${pnl['total_fees']:.2f}")
print(f"Impact frais: {pnl['fee_impact_pct']:.2f}%")
```

---

## 📝 Notes Importantes

### 1. Frais Réglementaires (Ventes Uniquement)

Les frais SEC et FINRA s'appliquent **UNIQUEMENT aux ventes** :
- **Achats** : Commission seulement
- **Ventes** : Commission + SEC + FINRA

### 2. Arrondis

Tous les frais sont arrondis à **2 décimales** (centimes).

### 3. Frais de Données

Les frais de données de marché IBKR ne sont **PAS** inclus :
- Market data subscriptions
- Level 2 data
- News feeds

### 4. Cas Particuliers Non Couverts

- Options trading
- Futures
- Forex
- Bonds
- International stocks (non-US)

---

## 🎯 Best Practices

### 1. Toujours Vérifier le Net P&L

```python
# ❌ Mauvais
if gross_profit > 0:
    execute_trade()

# ✅ Bon
pnl = fee_calc.calculate_net_pnl(qty, entry, exit)
if pnl['net_pnl'] > 0:
    execute_trade()
```

### 2. Ajuster Targets pour Frais

```python
# ✅ Calculer prix cible qui donne vraiment 1% net
target = fee_calc.adjust_target_for_fees(
    entry_price=150.00,
    quantity=100,
    min_profit_pct=1.0  # 1% NET souhaité
)
```

### 3. Logger les Frais

```python
# Le système log automatiquement
logger.info(f"Trade executed | Fees: ${fees['total_fees']:.2f}")
```

---

## 🚀 Résumé

✅ **Frais IBKR Pro intégrés automatiquement**
✅ **Commission : $0.005/action (min $1, max 1%)**
✅ **Frais réglementaires sur ventes**
✅ **Calculs P&L nets après frais**
✅ **Risk/Reward ajusté pour frais**
✅ **Logging automatique des coûts**

**Le système calcule maintenant les profits RÉELS après tous les frais !** 💰
