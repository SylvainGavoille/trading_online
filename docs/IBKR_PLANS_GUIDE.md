# Guide Complet des Plans IBKR

## 🎯 Choisir le Bon Plan pour Votre Style de Trading

Ce guide vous aide à choisir entre **IBKR Lite**, **IBKR Pro Fixed**, et **IBKR Pro Tiered**.

---

## 📊 Comparaison Rapide

| Caractéristique | IBKR Lite | IBKR Pro Fixed | IBKR Pro Tiered |
|----------------|-----------|----------------|-----------------|
| **Commission actions US** | 🆓 **$0** | $0.005/action | $0.0015-$0.0035/action |
| **Minimum par ordre** | $0 | $1.00 | $0.35 |
| **Rebates (liquidité)** | ❌ Non | ❌ Non | ✅ Oui |
| **Tarification** | Simple | Simple | Volume-based |
| **Idéal pour** | Débutants | Traders actifs | Algos/HFT |
| **Complexité** | 👍 Facile | 👍 Facile | 🔄 Moyenne |

---

## 1️⃣ IBKR LITE — Zero Commission

### 💰 Frais

```yaml
Commission: $0 sur actions/ETF US
Regulatory fees: SEC + FINRA (ventes uniquement)
Market data: Payant (optionnel)
```

### ✅ Avantages

- ✅ **$0 commission** sur actions/ETF US
- ✅ **Pas de minimum** d'activité
- ✅ **Simple** et prévisible
- ✅ **Fractional shares** disponibles
- ✅ Idéal pour **débuter**

### ⚠️ Limitations

- ❌ Pas de rebates pour liquidité
- ❌ Moins d'outils professionnels
- ❌ Pas optimal pour trading très actif

### 📈 Exemple de Coût

```python
# Trade: 100 actions @ $150 → $155

Achat (100 @ $150):
  Commission: $0.00
  Regulatory: $0.00
  Total: $0.00

Vente (100 @ $155):
  Commission: $0.00
  SEC Fee: $0.43
  FINRA TAF: $0.02
  Total: $0.45

Round Trip Total: $0.45 ✅
```

### 🎯 Idéal Pour

- 👶 **Débutants** en trading
- 💼 **Buy & hold** long terme
- 📉 **Faible volume** (<50 trades/mois)
- 🏠 **Investisseurs particuliers**

### ⚙️ Configuration

```yaml
fees:
  ibkr_plan: "lite"
```

---

## 2️⃣ IBKR PRO FIXED — Tarif Prévisible

### 💰 Frais

```yaml
Commission: $0.005 par action
Minimum: $1.00 par ordre
Maximum: 1% de la valeur du trade
Regulatory fees: SEC + FINRA (ventes)
```

### ✅ Avantages

- ✅ **Coût prévisible** et simple
- ✅ **Transparent** ($0.005/action)
- ✅ **Bon pour volume moyen**
- ✅ **Tous les outils pro** disponibles
- ✅ **Pas de surprise** sur la facture

### 📊 Structure de Prix

| Nombre d'Actions | Prix/Action | Commission Calculée | Commission Finale |
|-----------------|-------------|---------------------|-------------------|
| 10 | $50 | $0.05 | **$1.00** (min) |
| 100 | $50 | $0.50 | **$1.00** (min) |
| 500 | $50 | $2.50 | **$2.50** |
| 1000 | $50 | $5.00 | **$5.00** |
| 10000 | $50 | $50.00 | **$50.00** (< max $5000) |

### 📈 Exemple de Coût

```python
# Trade: 100 actions @ $150 → $155

Achat (100 @ $150):
  Commission: $1.00 (100 * $0.005 = $0.50 → $1.00 min)
  Regulatory: $0.00
  Total: $1.00

Vente (100 @ $155):
  Commission: $1.00
  SEC Fee: $0.43
  FINRA TAF: $0.02
  Total: $1.45

Round Trip Total: $2.45
Net P&L: $500 - $2.45 = $497.55
```

### 🎯 Idéal Pour

- 📈 **Traders actifs** (50-200 trades/mois)
- 🤖 **Bots de trading** simples
- 💹 **Day traders** moyens
- 🎲 **Swing traders**

### ⚙️ Configuration

```yaml
fees:
  ibkr_plan: "pro_fixed"
  per_share_rate: 0.005
  min_commission: 1.00
  max_commission_pct: 0.01
```

---

## 3️⃣ IBKR PRO TIERED — Optimisé Volume

### 💰 Frais (Volume-Based)

| Volume Mensuel | Commission/Action | Rebate (si liquidité) |
|----------------|-------------------|---------------------|
| 0 - 50k actions | **$0.0035** | $0.0001 |
| 50k - 200k | **$0.0025** | $0.0002 |
| 200k - 1M | **$0.0018** | $0.0003 |
| +1M actions | **$0.0015** | $0.0004 |

**Minimum** : $0.35 par ordre

### ✅ Avantages

- ✅ **Coûts dégressifs** avec le volume
- ✅ **Rebates possibles** (ajouter liquidité)
- ✅ **Optimal pour HFT**
- ✅ **Peut être TRÈS économique** à gros volume
- ✅ **Best pour algos**

### ⚠️ Complexités

- 🔄 Calcul **plus complexe**
- 📊 Nécessite **tracking volume mensuel**
- 💡 Rebates **seulement si limit orders** ajoutent liquidité
- 🎯 **Market orders** = pas de rebate

### 📈 Exemples de Coûts

#### Scénario 1 : Début de Mois (0 volume)

```python
# Trade: 1000 actions @ $100 (market orders)

Tier: 0-50k (rate $0.0035/share, no rebate)

Achat (1000 @ $100):
  Commission: 1000 * $0.0035 = $3.50
  Regulatory: $0.00
  Total: $3.50

Vente (1000 @ $102):
  Commission: 1000 * $0.0035 = $3.50
  SEC Fee: $2.84
  FINRA TAF: $0.17
  Total: $6.51

Round Trip Total: $10.01
```

#### Scénario 2 : 100k Volume (tier 2)

```python
# Trade: 1000 actions @ $100 (limit orders avec liquidité)

Tier: 50k-200k (rate $0.0025/share, rebate $0.0002)

Achat (1000 @ $100):
  Gross Commission: 1000 * $0.0025 = $2.50
  Rebate: 1000 * $0.0002 = $0.20
  Net Commission: $2.30
  Total: $2.30

Vente (1000 @ $102):
  Gross Commission: 1000 * $0.0025 = $2.50
  Rebate: 1000 * $0.0002 = $0.20
  Net Commission: $2.30
  SEC Fee: $2.84
  FINRA TAF: $0.17
  Total: $5.31

Round Trip Total: $7.61 ✅ (vs $10.01 en tier 1)
Savings: $2.40 grâce aux rebates !
```

#### Scénario 3 : 1M+ Volume (tier max)

```python
# Trade: 5000 actions @ $100 (limit orders avec liquidité)

Tier: 1M+ (rate $0.0015/share, rebate $0.0004)

Achat (5000 @ $100):
  Gross Commission: 5000 * $0.0015 = $7.50
  Rebate: 5000 * $0.0004 = $2.00
  Net Commission: $5.50
  Total: $5.50

Vente (5000 @ $102):
  Gross Commission: 5000 * $0.0015 = $7.50
  Rebate: 5000 * $0.0004 = $2.00
  Net Commission: $5.50
  SEC Fee: $14.21
  FINRA TAF: $0.83
  Total: $20.54

Round Trip Total: $26.04
vs Pro Fixed: $51.98
Savings: $25.94 (50%!) ✅
```

### 🎯 Idéal Pour

- 🤖 **Trading algorithmique**
- ⚡ **High frequency trading** (HFT)
- 📊 **Volume élevé** (>200k actions/mois)
- 💹 **Market makers**
- 🏢 **Trading professionnel**

### ⚙️ Configuration

```yaml
fees:
  ibkr_plan: "pro_tiered"
```

---

## 🧮 Comparaison Détaillée

### Cas d'Usage: 100 Trades/Mois (100 actions @ $100 chaque)

| Plan | Commission/Trade | Total/Mois | Notes |
|------|-----------------|------------|-------|
| **Lite** | $0.45 | **$45** | Cheapest! ✅ |
| **Pro Fixed** | $2.45 | **$245** | Prévisible |
| **Pro Tiered** (tier 1) | ~$10 | **$1,000** | ⚠️ Pas optimal |
| **Pro Tiered** (tier 2+) | ~$7.61 | **$761** | Mieux mais... |

**Conclusion** : Pour ce volume, **Lite gagne** ! 🏆

### Cas d'Usage: Trading Algo (1000 trades/mois, 1000 actions chaque)

| Plan | Commission/Trade | Total/Mois | Rebates |
|------|-----------------|------------|---------|
| **Lite** | $4.50 | **$4,500** | $0 |
| **Pro Fixed** | $6.01 | **$6,010** | $0 |
| **Pro Tiered** (tier max) | ~$5.20 | **$5,200** | $400 💰 |

**Conclusion** : Pour HFT, **Tiered gagne** avec rebates ! 🏆

---

## 💡 Comment Choisir ?

### 🟢 Choisissez LITE si :

```
✓ Vous débutez en trading
✓ Volume < 50 trades/mois
✓ Buy & hold stratégie
✓ Pas besoin outils pro avancés
✓ Voulez la simplicité maximale
```

### 🔵 Choisissez PRO FIXED si :

```
✓ Trading actif (50-200 trades/mois)
✓ Voulez coûts prévisibles
✓ Besoin des outils professionnels
✓ Volume moyen (10k-100k actions/mois)
✓ Stratégie standard day/swing trading
```

### 🟣 Choisissez PRO TIERED si :

```
✓ Très haut volume (>200k actions/mois)
✓ Trading algorithmique
✓ High frequency trading
✓ Utilisez surtout limit orders
✓ Voulez maximiser l'efficacité
✓ Pouvez tracker volume mensuel
```

---

## 📖 Utilisation dans le Code

### Vérifier Plan Actuel

```python
from src.trading.fee_calculator import FeeCalculator

fee_calc = FeeCalculator(config)
summary = fee_calc.get_fee_summary()

print(summary['plan'])
# Output: 'lite', 'pro_fixed', ou 'pro_tiered'

print(summary['description'])
# Description du plan actif
```

### Calculer Avec Rebates (Tiered)

```python
# Avec limit order qui ajoute liquidité
pnl = fee_calc.calculate_net_pnl(
    quantity=1000,
    entry_price=100.00,
    exit_price=102.00,
    entry_provides_liquidity=True,  # Limit buy adds liquidity
    exit_provides_liquidity=True    # Limit sell adds liquidity
)

print(f"Net P&L: ${pnl['net_pnl']:.2f}")
print(f"Rebates: ${pnl['total_rebates']:.4f}")
```

### Comparer Plans

```python
plans = ['lite', 'pro_fixed', 'pro_tiered']
quantity, entry, exit = 100, 150.00, 155.00

for plan in plans:
    config['fees']['ibkr_plan'] = plan
    fee_calc = FeeCalculator(config)

    pnl = fee_calc.calculate_net_pnl(quantity, entry, exit)

    print(f"\n{plan.upper()}:")
    print(f"  Fees: ${pnl['total_fees']:.2f}")
    print(f"  Net P&L: ${pnl['net_pnl']:.2f}")
```

---

## 🎯 Recommandations Finales

### Phase 1: Apprentissage

```
🟢 LITE
- 0$ commission
- Apprenez sans payer
- Testez vos stratégies
```

### Phase 2: Croissance

```
🔵 PRO FIXED
- Coûts prévisibles
- Bon équilibre
- Scalez votre volume
```

### Phase 3: Optimisation

```
🟣 PRO TIERED
- Réduisez coûts avec volume
- Rebates = argent gagné
- Maximum d'efficacité
```

---

## 💾 Changer de Plan

### Dans config.yaml

```yaml
# Option 1: LITE (débutants)
fees:
  ibkr_plan: "lite"

# Option 2: PRO FIXED (traders actifs)
fees:
  ibkr_plan: "pro_fixed"

# Option 3: PRO TIERED (algos/HFT)
fees:
  ibkr_plan: "pro_tiered"
```

Le système recalculera automatiquement tous les frais selon le plan choisi ! ✅

---

## 📊 Résumé

| Votre Profil | Plan Recommandé | Économie |
|--------------|----------------|----------|
| Débutant, <50 trades/mois | **LITE** | Max |
| Actif, 50-200 trades/mois | **PRO FIXED** | Moyen |
| Algo, >200k actions/mois | **PRO TIERED** | Max (avec volume) |

**La bonne nouvelle** : Vous pouvez changer de plan à tout moment ! 🎉
