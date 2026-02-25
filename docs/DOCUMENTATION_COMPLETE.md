# Quantum Trader - Documentation Complète

**Système de Trading Algorithmique Multi-Agents**

Version 1.0.0 | 20 Février 2026

---

## Table des Matières

1. [Introduction](#introduction)
2. [Installation et Démarrage](#installation)
3. [Architecture](#architecture)
4. [Système Multi-Agents](#agents)
5. [Indicateurs Techniques](#indicateurs)
6. [Gestion des Risques](#risques)
7. [Flux de Travail](#workflow)
8. [Configuration](#configuration)

---

<div style="page-break-after: always;"></div>

# 1. Introduction {#introduction}

## Qu'est-ce que Quantum Trader ?

Quantum Trader est un système de trading algorithmique autonome qui utilise une **architecture multi-agents** pour analyser les marchés, gérer les risques et exécuter des trades automatiquement via Interactive Brokers.

### Fonctionnalités Principales

- **4 Agents Spécialisés** : Analyse technique, sentiment, risque, exécution
- **5 Indicateurs Techniques** : SMA, EMA, RSI, MACD, Bollinger Bands
- **Gestion des Risques Avancée** : 6 validations avant chaque trade
- **Paper Trading** : Testez sans risquer d'argent réel
- **Hautement Configurable** : Tous les paramètres via YAML

### Prérequis

- **Python 3.10+**
- **Interactive Brokers Gateway ou TWS**
- **Capital recommandé** : Minimum $10,000 pour paper trading
- **Système d'exploitation** : Windows, macOS, Linux

### Installation Rapide

```bash
# 1. Cloner le repository
cd trading_online

# 2. Installer avec uv
uv sync

# 3. Tester la connexion
uv run python test_connection.py

# 4. Lancer le système (paper trading)
uv run python run_trader.py --symbols AAPL MSFT --mode paper
```

---

<div style="page-break-after: always;"></div>

# 2. Architecture du Système {#architecture}

## Vue d'Ensemble

Le système est organisé en **5 couches** principales qui collaborent pour analyser et trader.

### Les 5 Couches

1. **Interface Utilisateur**
   - CLI Interface (ligne de commande)
   - Dashboard (monitoring optionnel)

2. **Orchestrateur (Trading Logic)**
   - Coordonne tous les composants
   - Gère le flux de décision
   - Synchronise les agents

3. **Système Multi-Agents**
   - 4 agents spécialisés (Technique, Sentiment, Risque, Exécution)
   - Communication via DSPy framework
   - Prise de décision collaborative

4. **Analyseurs de Données**
   - Analyse Technique (indicateurs)
   - Analyse Qualitative (sentiment)

5. **Couches de Sécurité**
   - Validation des risques
   - Gestion des positions
   - Stop-loss dynamique

### Flux de Données

```
Marché → IB Gateway → IB Connector → Analyse → Agents → Décision → Validation → Exécution
```

### Cycle de Décision (60 secondes)

1. **Récupération** : Données OHLCV pour chaque symbole
2. **Analyse Technique** : Calcul des 5 indicateurs
3. **Analyse Sentiment** : News + réseaux sociaux
4. **Combinaison** : Signal technique (70%) + sentiment (30%)
5. **Validation** : 6 checks de risque
6. **Exécution** : Si approuvé, passage d'ordre
7. **Monitoring** : Surveillance continue de la position

---

<div style="page-break-after: always;"></div>

# 3. Système Multi-Agents {#agents}

## Les 4 Agents

### 1. Agent d'Analyse Technique 📊

**Rôle** : Analyser les données de marché avec des indicateurs techniques

**Indicateurs utilisés** :
- SMA (20, 50, 200) : Tendance long terme
- EMA (12, 26) : Tendance court terme
- RSI (14) : Surachat/survente
- MACD : Momentum
- Bollinger Bands : Volatilité

**Sortie** :
```json
{
  "signal": "buy",
  "confidence": 0.75,
  "indicators": {
    "rsi": 28.5,
    "macd": 0.45,
    "sma_20": 150.2,
    "bollinger_position": "lower"
  }
}
```

### 2. Agent d'Analyse de Sentiment 💬

**Rôle** : Évaluer le sentiment du marché

**Sources** :
- Articles de presse financière (60% poids)
- Twitter/X (20% poids)
- Reddit (20% poids)

**Sortie** :
```json
{
  "signal": "bullish",
  "confidence": 0.65,
  "sources": {
    "news_count": 12,
    "social_mentions": 45,
    "overall_tone": "positive"
  }
}
```

### 3. Agent de Gestion des Risques 🛡️

**Rôle** : Valider chaque trade avant exécution

**Validations** :
1. Taille de position < max
2. Exposition portfolio < 25%
3. Perte journalière < limite
4. Ratio risk/reward ≥ 2.0
5. Stop-loss calculé
6. Drawdown < maximum

**Sortie** :
```json
{
  "approved": true,
  "calculated_stop_loss": 148.50,
  "position_size": 50
}
```

### 4. Agent d'Exécution ⚡

**Rôle** : Exécuter les trades validés

**Types d'ordres** :
- **Market** : Exécution immédiate
- **Limit** : Exécution à prix limite ou meilleur

**Gestion** :
- Timeout : 60 secondes pour ordres limit
- Slippage : Max 0.1% toléré
- Confirmation : Vérification après exécution

## Communication Inter-Agents

Les agents communiquent séquentiellement :

1. **Orchestrateur** → Agent Technique + Agent Sentiment (parallèle)
2. **Combinaison** des signaux (pondérés 70/30)
3. **Si signal fort** → Agent Risque
4. **Si approuvé** → Agent Exécution
5. **Si exécuté** → Monitoring

### Pondération des Signaux

```
Signal Combiné = (Signal Technique × 0.7) + (Signal Sentiment × 0.3)
```

**Exemple** :
- Signal Technique = 0.80 (BUY)
- Signal Sentiment = 0.70 (BULLISH)
- Signal Combiné = (0.80 × 0.7) + (0.70 × 0.3) = 0.77 ✅

**Seuil** : 0.65 (configurable)

---

<div style="page-break-after: always;"></div>

# 4. Indicateurs Techniques {#indicateurs}

## 1. SMA (Simple Moving Average)

**Description** : Moyenne mobile simple, tendance générale

**Calcul** :
```
SMA(n) = (Prix₁ + Prix₂ + ... + Prixₙ) / n
```

**Périodes** :
- SMA 20 : Court terme (1 mois)
- SMA 50 : Moyen terme (2.5 mois)
- SMA 200 : Long terme (1 an)

**Signaux** :
- Prix > SMA 20 > SMA 50 > SMA 200 : Très haussier
- Prix < SMA 20 < SMA 50 < SMA 200 : Très baissier
- Golden Cross (SMA 20 croise SMA 50 à la hausse) : Signal fort achat
- Death Cross (SMA 20 croise SMA 50 à la baisse) : Signal fort vente

## 2. EMA (Exponential Moving Average)

**Description** : Moyenne mobile exponentielle, plus réactive

**Calcul** :
```
EMA(aujourd'hui) = (Prix × Multiplicateur) + (EMA(hier) × (1 - Multiplicateur))
Multiplicateur = 2 / (Période + 1)
```

**Périodes** :
- EMA 12 : Court terme
- EMA 26 : Moyen terme

**Avantage** : Réagit plus vite aux changements que SMA

## 3. RSI (Relative Strength Index)

**Description** : Indicateur de momentum (0-100)

**Calcul** :
```
RSI = 100 - (100 / (1 + RS))
RS = Moyenne des gains / Moyenne des pertes (14 périodes)
```

**Zones** :
- **< 30** : Survente → Signal ACHAT
- **30-70** : Neutre
- **> 70** : Surachat → Signal VENTE

**Configuration** :
```yaml
rsi:
  period: 14
  overbought: 70
  oversold: 30
```

## 4. MACD (Moving Average Convergence Divergence)

**Description** : Indicateur de momentum et tendance

**Composantes** :
- MACD Line = EMA(12) - EMA(26)
- Signal Line = EMA(9) du MACD
- Histogramme = MACD Line - Signal Line

**Signaux** :
- MACD croise Signal à la hausse : ACHAT
- MACD croise Signal à la baisse : VENTE
- Histogramme croissant : Momentum haussier
- Histogramme décroissant : Momentum baissier

## 5. Bollinger Bands

**Description** : Indicateur de volatilité (3 bandes)

**Calcul** :
```
Bande Centrale = SMA(20)
Bande Supérieure = SMA(20) + (2 × Écart-type)
Bande Inférieure = SMA(20) - (2 × Écart-type)
```

**Signaux** :
- Prix touche bande inférieure : Survente → ACHAT
- Prix touche bande supérieure : Surachat → VENTE
- Bandes serrées : Faible volatilité → Éclatement imminent
- Bandes larges : Forte volatilité → Tendance établie

## Combinaison des Indicateurs

Le système normalise tous les signaux entre -1 et +1, puis les combine :

```python
rsi_signal = (rsi_value - 50) / 50
macd_signal = tanh(macd_value)
bb_signal = 2 * ((prix - bande_inf) / (bande_sup - bande_inf) - 0.5)

signal_final = (rsi_signal + macd_signal + bb_signal) / 3
```

**Interprétation** :
- Signal > 0.65 : ACHAT FORT
- Signal 0.3 à 0.65 : ACHAT FAIBLE
- Signal -0.3 à 0.3 : NEUTRE
- Signal -0.65 à -0.3 : VENTE FAIBLE
- Signal < -0.65 : VENTE FORTE

---

<div style="page-break-after: always;"></div>

# 5. Gestion des Risques {#risques}

## Les 6 Validations Obligatoires

Chaque trade passe par **6 validations** avant exécution :

### 1. Taille de Position

**Règle** : Maximum 100 actions par position (configurable)

**Objectif** : Éviter sur-concentration

**Exemple** :
- Trade proposé : 150 actions → ❌ REJETÉ
- Trade proposé : 80 actions → ✅ APPROUVÉ

### 2. Exposition du Portfolio

**Règle** : Maximum 25% du capital exposé

**Objectif** : Diversification

**Exemple** :
- Portfolio : $100,000
- Positions actuelles : $20,000 (20%)
- Nouveau trade : $7,000
- Nouvelle exposition : $27,000 (27%) → ❌ REJETÉ (> 25%)

**Solution** : Réduire taille trade à $5,000 max

### 3. Limite de Perte Journalière

**Règle** : Maximum $1,000 de perte par jour (configurable)

**Objectif** : Limiter dégâts en cas de mauvaise journée

**Exemple** :
- Perte actuelle : -$750
- Nouveau trade risque : -$300
- Total potentiel : -$1,050 → ❌ REJETÉ

**Action** : Arrêt automatique du trading si limite atteinte

### 4. Ratio Risk/Reward

**Règle** : Minimum 2:1 (gain potentiel / perte potentielle)

**Objectif** : Trading profitable long terme

**Exemple** :
- Prix entrée : $150
- Stop-loss : $148 (risque $2)
- Take-profit : $156 (gain $6)
- Ratio : $6 / $2 = 3.0 → ✅ APPROUVÉ

**Calcul** :
```
Ratio = (Take-Profit - Prix Entrée) / (Prix Entrée - Stop-Loss)
```

### 5. Stop-Loss Dynamique

**Règle** : Calculé avec ATR (Average True Range)

**Formule** :
```
Distance Stop = ATR(14) × 2
Stop-Loss (ACHAT) = Prix - Distance
Stop-Loss (VENTE) = Prix + Distance
```

**Exemple AAPL** :
- Prix actuel : $150
- ATR(14) : $2.50
- Distance : $2.50 × 2 = $5
- Stop-Loss : $150 - $5 = $145

**Objectif** : S'adapter à la volatilité du titre

### 6. Drawdown Maximum

**Règle** : Maximum 15% de baisse depuis le pic

**Calcul** :
```
Drawdown = (Pic Historique - Capital Actuel) / Pic Historique
```

**Exemple** :
- Pic historique : $120,000
- Capital actuel : $105,000
- Drawdown : ($120k - $105k) / $120k = 12.5% → ✅ OK
- Si capital tombe à $101,000 : 15.8% → ❌ ARRÊT TRADING

## Hiérarchie des Contrôles

Ordre d'exécution :
1. Taille position → Si ✗ STOP
2. Exposition portfolio → Si ✗ STOP
3. Perte journalière → Si ✗ STOP
4. Ratio risk/reward → Si ✗ STOP
5. Stop-loss → Si ✗ STOP
6. Drawdown → Si ✗ STOP
7. **Tous ✓** → Exécution autorisée

## Configuration des Risques

```yaml
risk_management:
  position_limits:
    max_position_size: 100
    max_portfolio_exposure: 0.25

  loss_limits:
    daily_loss_limit: 1000
    max_drawdown: 0.15

  stop_loss:
    atr_multiplier: 2
    max_loss_per_trade: 0.02

  risk_reward:
    min_ratio: 2.0
    target_ratio: 3.0
```

**IMPORTANT** : Ajustez selon votre capital !

---

<div style="page-break-after: always;"></div>

# 6. Flux de Travail Complet {#workflow}

## Cycle de Trading (60 secondes)

### Phase 1 : Initialisation

1. Chargement configuration (`config.yaml`)
2. Connexion IB Gateway (port 4002)
3. Initialisation des 4 agents
4. Démarrage boucle principale

### Phase 2 : Récupération Données

Pour chaque symbole (ex: AAPL, MSFT, GOOGL) :
- Récupération OHLCV (Open, High, Low, Close, Volume)
- Validation données
- Stockage temporaire

**Exemple** :
```json
{
  "symbol": "AAPL",
  "timestamp": "2026-02-20T16:30:00Z",
  "open": 149.50,
  "high": 151.20,
  "low": 148.80,
  "close": 150.75,
  "volume": 45_320_000
}
```

### Phase 3 : Analyse Multi-Agents

**Analyse en Parallèle** :

1. **Agent Technique** calcule :
   - RSI = 28 (survente)
   - MACD = +0.5 (haussier)
   - BB position = 0.15 (proche bande inf)
   - SMA : Prix < SMA20 (faiblement baissier)
   - **Signal** : +0.75 (BUY)

2. **Agent Sentiment** analyse :
   - 12 articles news (8 positifs)
   - 45 mentions Twitter (30 positives)
   - 18 posts Reddit (12 positifs)
   - **Signal** : +0.65 (BULLISH)

**Combinaison** :
```
Signal = (0.75 × 0.7) + (0.65 × 0.3) = 0.72
```

### Phase 4 : Décision

**Seuil** : 0.65 (configurable)

- Signal 0.72 > 0.65 → **TRADE PROPOSÉ**

**Calcul paramètres** :
- Symbole : AAPL
- Action : ACHAT
- Prix : $150.00
- Stop-loss : $145.00 (ATR × 2)
- Take-profit : $165.00 (ratio 3:1)
- Quantité : 100 actions
- Risque : $500 (100 × $5)
- Gain potentiel : $1,500 (100 × $15)

### Phase 5 : Validation Risque

**Agent Risque** vérifie :
1. ✅ Taille : 100 ≤ 100 max
2. ✅ Exposition : 23% < 25% max
3. ✅ Perte jour : -$300 < $1,000 max
4. ✅ Ratio R/R : 3.0 ≥ 2.0 min
5. ✅ Stop-loss : $145 calculé
6. ✅ Drawdown : 8% < 15% max

**Résultat** : ✅ **TRADE APPROUVÉ**

### Phase 6 : Exécution

**Agent Exécution** :
1. Choix type ordre : LIMIT (défaut)
2. Passage ordre : AAPL × 100 @ $150
3. Attente exécution (max 60s)
4. Ordre rempli @ $150.05
5. Position ouverte

**Trade confirmé** :
```json
{
  "status": "executed",
  "order_id": "12345",
  "entry_price": 150.05,
  "stop_loss": 145.00,
  "take_profit": 165.00,
  "timestamp": "2026-02-20T16:30:15Z"
}
```

### Phase 7 : Monitoring

**Surveillance continue** (toutes les 10 secondes) :

Vérifications :
- Prix actuel vs Stop-loss
- Prix actuel vs Take-profit
- Nouveaux signaux (retournement)

**Scénarios de sortie** :

1. **Stop-loss atteint** ($145)
   - Fermeture position
   - Perte : -$500
   - Logging

2. **Take-profit atteint** ($165)
   - Fermeture position
   - Gain : +$1,500
   - Logging

3. **Signal inverse** (SELL fort)
   - Fermeture position anticipée
   - P&L variable
   - Logging

## Exemple Complet : Trade AAPL

**Timeline** :
- **09:30** : Récupération données
- **09:31** : Analyse technique → Signal 0.75
- **09:31** : Analyse sentiment → Signal 0.65
- **09:32** : Combinaison → Signal 0.72
- **09:33** : Validation risque → APPROUVÉ
- **09:34** : Ordre LIMIT passé
- **09:35** : Ordre exécuté @ $150.05
- **09:35-11:30** : Monitoring position
- **11:30** : Stop-loss atteint @ $145
- **Résultat** : -$505 (-3.36%)

**Enregistrement** :
```json
{
  "trade_id": "12345",
  "symbol": "AAPL",
  "open_time": "2026-02-20T09:35:00Z",
  "close_time": "2026-02-20T11:30:00Z",
  "entry_price": 150.05,
  "exit_price": 145.00,
  "quantity": 100,
  "pnl": -505.00,
  "pnl_percent": -3.36,
  "exit_reason": "STOP_LOSS",
  "duration_minutes": 115
}
```

---

<div style="page-break-after: always;"></div>

# 7. Configuration Détaillée {#configuration}

## Structure config.yaml

Le fichier `src/config/config.yaml` contrôle tout le système.

### Section 1 : API

```yaml
api:
  tws_endpoint: "127.0.0.1"
  port: 4002
```

**Ports** :
- 4002 : IB Gateway Paper Trading ← **Actuel**
- 4001 : IB Gateway Live Trading
- 7497 : TWS Paper Trading
- 7496 : TWS Live Trading

### Section 2 : Analyse Technique

```yaml
technical_analysis:
  indicators:
    sma_periods: [20, 50, 200]
    ema_periods: [12, 26]

    rsi:
      period: 14
      overbought: 70
      oversold: 30

    macd:
      fast_period: 12
      slow_period: 26
      signal_period: 9

    bollinger_bands:
      period: 20
      std_dev: 2
```

**Personnalisation RSI** :
```yaml
# Trading agressif
rsi:
  period: 9
  overbought: 75
  oversold: 25

# Trading conservateur
rsi:
  period: 21
  overbought: 65
  oversold: 35
```

### Section 3 : Gestion des Risques

```yaml
risk_management:
  position_limits:
    max_position_size: 100
    max_portfolio_exposure: 0.25

  loss_limits:
    daily_loss_limit: 1000
    max_drawdown: 0.15

  trade_frequency:
    min_time_between_trades: 300
    max_daily_trades: 10

  stop_loss:
    atr_multiplier: 2
    max_loss_per_trade: 0.02

  risk_reward:
    min_ratio: 2.0
    target_ratio: 3.0
```

**Ajustement par capital** :

| Capital | Position Max | Exposure Max | Loss Limit | Drawdown Max |
|---------|--------------|--------------|------------|--------------|
| $10k | 50 | 20% | $100 | 10% |
| $50k | 100 | 25% | $500 | 15% |
| $100k | 100 | 25% | $1,000 | 15% |
| $200k+ | 200 | 30% | $2,000 | 20% |

### Section 4 : Système Multi-Agents

```yaml
agent_system:
  update_interval: 60

  confidence_thresholds:
    technical: 0.7
    sentiment: 0.6
    combined: 0.65

  signal_weights:
    technical: 0.7
    sentiment: 0.3

  handoff_timeout: 30
```

**Ajustement par style** :

**Conservateur** (moins de trades, plus fiables) :
```yaml
confidence_thresholds:
  technical: 0.8
  sentiment: 0.7
  combined: 0.75
```

**Agressif** (plus de trades) :
```yaml
confidence_thresholds:
  technical: 0.6
  sentiment: 0.5
  combined: 0.55
```

## Profils Recommandés

### Profil Débutant

```yaml
risk_management:
  position_limits:
    max_position_size: 50
    max_portfolio_exposure: 0.20

  loss_limits:
    daily_loss_limit: 200
    max_drawdown: 0.10

  stop_loss:
    atr_multiplier: 1.5
    max_loss_per_trade: 0.01

agent_system:
  confidence_thresholds:
    technical: 0.8
    sentiment: 0.7
    combined: 0.75
```

### Profil Avancé

```yaml
risk_management:
  position_limits:
    max_position_size: 200
    max_portfolio_exposure: 0.30

  loss_limits:
    daily_loss_limit: 2000
    max_drawdown: 0.20

  stop_loss:
    atr_multiplier: 3
    max_loss_per_trade: 0.03

agent_system:
  confidence_thresholds:
    technical: 0.6
    sentiment: 0.5
    combined: 0.55
```

---

<div style="page-break-after: always;"></div>

# 8. Utilisation Pratique

## Commandes Essentielles

### Test de Connexion
```bash
uv run python test_connection.py
```

Vérifie :
- Connexion à IB Gateway
- Compte actif
- Synchronisation serveur

### Diagnostic Complet
```bash
uv run python diagnose_connection.py
```

Teste :
- Tous les ports (4001, 4002, 7496, 7497)
- Tentatives de connexion
- Affiche recommandations

### Démarrage Rapide
```bash
uv run python quick_start.py
```

Affiche :
- Configuration actuelle
- État de la connexion
- Prochaines étapes

### Lancer le Trader

**Paper Trading** (recommandé) :
```bash
uv run python run_trader.py --symbols AAPL MSFT GOOGL --mode paper
```

**Live Trading** (ATTENTION : argent réel) :
```bash
uv run python run_trader.py --symbols AAPL --mode live
```

## Checklist Avant de Trader

- [ ] IB Gateway lancé et connecté
- [ ] API activée dans Gateway
- [ ] Configuration adaptée à votre capital
- [ ] Tests en paper trading pendant 2+ semaines
- [ ] Compris tous les indicateurs
- [ ] Compris la gestion des risques
- [ ] Limites configurées correctement
- [ ] Stratégie de sortie définie

## Sécurité

### ⚠️ RÈGLES D'OR

1. **TOUJOURS** commencer en paper trading
2. **JAMAIS** trader plus que ce que vous pouvez perdre
3. **TOUJOURS** respecter les stop-loss
4. **JAMAIS** désactiver les validations de risque
5. **TOUJOURS** tester les changements en paper d'abord

### Limites Recommandées

| Règle | Recommandation |
|-------|----------------|
| Risque par trade | Max 1-2% du capital |
| Exposition totale | Max 25% du capital |
| Perte journalière | Max 1% du capital |
| Drawdown max | 10-15% max |
| Stop-loss | Toujours défini (ATR × 1.5-2) |
| Ratio R/R | Minimum 2:1, idéal 3:1 |

---

# Conclusion

## Résumé

Quantum Trader est un système sophistiqué qui :
- Analyse automatiquement les marchés
- Gère les risques de manière stricte
- Exécute les trades de façon autonome
- S'adapte à la volatilité (ATR)
- Protège votre capital (6 validations)

## Points Clés à Retenir

1. **Architecture Multi-Agents** : 4 agents spécialisés collaborent
2. **5 Indicateurs** : SMA, EMA, RSI, MACD, Bollinger Bands
3. **6 Validations** : Chaque trade est vérifié avant exécution
4. **Stop-Loss Dynamique** : Basé sur l'ATR pour s'adapter
5. **Hautement Configurable** : Tout est dans config.yaml

## Prochaines Étapes

1. **Tester** en paper trading pendant 2-4 semaines
2. **Analyser** les résultats et ajuster la configuration
3. **Optimiser** les paramètres selon votre style
4. **Documenter** votre stratégie
5. **Évaluer** si passage en live est approprié

## Support

- **Documentation** : Voir INDEX_DOCS.md
- **Code source** : `src/`
- **Tests** : `tests/`
- **Configuration** : `src/config/config.yaml`

---

**Version** : 1.0.0
**Date** : 20 Février 2026
**Auteur** : Quantum Trader Team

---

**⚠️ AVERTISSEMENT**

Le trading comporte des risques. Les performances passées ne garantissent pas les résultats futurs. N'investissez que ce que vous pouvez vous permettre de perdre. Testez toujours en paper trading avant tout trading réel.

---

# Annexes

## Glossaire

| Terme | Définition |
|-------|------------|
| **Agent** | Programme autonome spécialisé |
| **ATR** | Average True Range - mesure volatilité |
| **Drawdown** | Baisse maximale depuis pic capital |
| **MACD** | Moving Average Convergence Divergence |
| **Paper Trading** | Trading simulé sans argent réel |
| **R/R** | Risk/Reward - ratio gain/perte |
| **RSI** | Relative Strength Index (0-100) |
| **Slippage** | Différence prix attendu/exécuté |
| **Stop-Loss** | Ordre automatique limitant pertes |
| **DSPy** | Framework multi-agents avec optimisation automatique |

## Références

- Interactive Brokers API : https://interactivebrokers.github.io/
- DSPy Documentation : https://dspy-docs.vercel.app/
- ib_insync : https://ib-insync.readthedocs.io/

## Structure des Fichiers

```
trading_online/
├── src/
│   ├── api/                    # Connexion IB
│   ├── analysis/               # Analyse technique/sentiment
│   ├── cli/                    # Interface CLI
│   ├── config/                 # Configuration
│   └── trading/                # Logique trading + agents
├── docs/                       # Documentation détaillée
├── tests/                      # Tests unitaires
├── training/                   # Système de formation
├── ARCHITECTURE.md             # Architecture complète
├── AGENTS_SYSTEM.md            # Système multi-agents
├── INDICATORS.md               # Indicateurs techniques
├── RISK_MANAGEMENT_DETAILED.md # Gestion risques
├── WORKFLOW.md                 # Flux de travail
├── CONFIGURATION.md            # Guide configuration
├── INDEX_DOCS.md               # Index documentation
└── README.md                   # Guide principal
```

---

**Fin du Document**
