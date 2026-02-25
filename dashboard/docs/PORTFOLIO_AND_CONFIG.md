# 📊 Portfolio et Configuration - Guide d'Utilisation

## ✅ Nouvelles Fonctionnalités Ajoutées

### 1. 📊 Onglet Portfolio

**Fonctionnalités:**

- **Résumé Global** avec 6 métriques clés:
  - 🏦 **Capital Disponible** - Cash disponible pour investir
  - 💰 **Capital Investi** - Montant dans les positions
  - 📊 **Valeur Positions** - Valeur actuelle des positions
  - 💎 **Capitalisation Totale** - Positions + Cash disponible
  - 💵 **Plus-Value Nette** - Gain/perte après frais
  - 📦 **Nombre de Positions** - Positions ouvertes

- **Gestion du Capital:**
  - Mettre à jour le capital disponible
  - Définir le capital initial (référence)
  - Visualisation de la répartition capital investi vs cash
  - Recommandations selon le profil de risque

- **Tableau Détaillé des Positions** affichant:
  - Symbole, Nombre d'actions, Prix d'achat, Prix actuel
  - Valeur investie, Valeur actuelle
  - Frais d'achat, Frais de vente (estimés), Frais totaux
  - **Plus-Value ($)** - Gain net après tous les frais
  - **Gain IBKR (%)** - Pourcentage affiché dans IBKR (sans frais)
  - **Gain Réel (%)** - Pourcentage réel après frais ✅
  - Plan IBKR utilisé, Date d'achat

- **Gestion des Positions:**
  - ➕ Ajouter une nouvelle position
  - 🗑️ Supprimer une position existante

- **Légende Explicative** pour comprendre la différence entre:
  - Gain IBKR (%) - Ce que vous voyez dans votre interface IBKR
  - Gain Réel (%) - Votre vrai rendement après frais

### 2. ⚙️ Onglet Configuration

**Fonctionnalités:**

- **Profil de Risque Actuel** avec affichage coloré et métriques:
  - 🎯 Tolérance au Risque
  - ⏳ Horizon Temporel
  - 📊 Volatilité Acceptée
  - 📉 Perte Tolérable

- **4 Onglets de Détails:**
  - 💼 **Allocation Recommandée** - Répartition suggérée des actifs
  - ✅ **Instruments Recommandés** - Actions, ETFs recommandés
  - ❌ **Instruments à Éviter** - Ce qu'il faut éviter selon votre profil
  - ⚙️ **Paramètres** - Taille max par position, fréquence de rééquilibrage

- **Comparaison des Profils** - Tableau comparatif des 4 profils:
  - Conservateur
  - Modéré
  - Agressif
  - Très Agressif

- **Changement de Profil** avec formulaire:
  - Sélection du nouveau profil
  - Configuration de la perte max par trade
  - Configuration du risque max du portfolio

- **Validation du Portfolio** - Vérification automatique:
  - ✅ Positions conformes au profil de risque
  - ⚠️ Positions proches de la limite (>80%)
  - ❌ Positions non conformes (dépassement de limite)

---

## 🎯 Calcul des Frais IBKR

Le système calcule automatiquement les frais selon votre plan IBKR:

### Plan Lite (par défaut)
- **Commission:** 0$
- **Routing fees:** Approximativement 0$ (simplifié)

### Plan Pro Fixed
- **Commission:** $0.005 par action
- **Minimum:** $1 par ordre
- **Maximum:** 1% de la valeur de l'ordre

### Plan Pro Tiered
- **Commission par palier:**
  - 0-10,000 actions: $0.0035 par action
  - 10,001-20,000 actions: $0.0020 par action
  - 20,000+ actions: $0.0015 par action
- **Minimum:** $0.35 par ordre
- **Maximum:** 1% de la valeur de l'ordre

---

## 📊 Profils de Risque Détaillés

### 🟢 Conservateur
- **Objectif:** Préservation du capital avec croissance modérée
- **Tolérance:** Faible
- **Horizon:** Court terme (< 3 ans)
- **Volatilité:** Très faible (< 10%)
- **Allocation:**
  - Actions: 20-30%
  - Obligations: 50-60%
  - Cash: 10-20%
  - Autres: < 10%
- **Max position:** 10% du portfolio
- **Rééquilibrage:** Trimestriel

**Recommandé:**
- ETFs dividendes (VYM, SCHD)
- Obligations (AGG, BND)
- Actions défensives (JNJ, PG, KO)

**À éviter:**
- Actions à forte volatilité
- Cryptomonnaies
- ETFs à effet de levier

---

### 🟠 Modéré
- **Objectif:** Équilibre entre croissance et sécurité
- **Tolérance:** Moyenne
- **Horizon:** Moyen terme (3-7 ans)
- **Volatilité:** Modérée (10-20%)
- **Allocation:**
  - Actions: 50-60%
  - Obligations: 25-35%
  - Cash: 5-10%
  - Autres: 5-15%
- **Max position:** 15% du portfolio
- **Rééquilibrage:** Semestriel

**Recommandé:**
- ETFs diversifiés (SPY, VOO, VTI)
- Actions blue-chip (AAPL, MSFT, GOOGL)
- ETFs sectoriels (XLK, XLV, XLF)

**À éviter:**
- ETFs à effet de levier 3x
- Trading spéculatif

---

### 🔴 Agressif
- **Objectif:** Croissance maximale avec forte volatilité
- **Tolérance:** Élevée
- **Horizon:** Long terme (> 7 ans)
- **Volatilité:** Élevée (> 20%)
- **Allocation:**
  - Actions: 70-90%
  - Obligations: 0-10%
  - Cash: 0-5%
  - Autres: 5-20%
- **Max position:** 25% du portfolio
- **Rééquilibrage:** Annuel ou opportuniste

**Recommandé:**
- Actions de croissance (NVDA, TSLA, META)
- ETFs sectoriels concentrés (ARKK, XLK)
- Small/Mid caps (IWM)
- Marchés émergents (VWO, EEM)
- Cryptos (BTC-USD, ETH-USD)

**À éviter:**
- Sur-diversification
- Trop de cash dormant

---

### 🟣 Très Agressif
- **Objectif:** Trading actif, gains rapides, effet de levier
- **Tolérance:** Très élevée
- **Horizon:** Court/Moyen terme (spéculatif)
- **Volatilité:** Très élevée (> 30%)
- **Allocation:**
  - Actions volatiles: 40-60%
  - ETFs à levier: 20-40%
  - Options/Dérivés: 10-20%
  - Cash (marge): 5-10%
- **Max position:** 30% du portfolio
- **Rééquilibrage:** Quotidien/Hebdomadaire

**Recommandé:**
- ETFs à effet de levier 2x/3x (TQQQ, UPRO, SOXL)
- Actions momentum (NVDA, AMD, SMCI)
- Cryptos volatiles
- Options (calls/puts)
- Day/Swing trading

**À éviter:**
- Investir tout son capital en une fois
- Négliger les stop-loss
- Trading émotionnel

**⚠️ AVERTISSEMENTS:**
- Risque de perte totale du capital
- Nécessite surveillance constante
- Frais de trading élevés
- Stress psychologique important

---

## 🚀 Utilisation

### Lancer le Dashboard

**Windows:**
```powershell
run_dashboard.bat
```

**Linux/Mac:**
```bash
./run_dashboard.sh
```

### Navigation

1. **🔍 Exploration** - Recherche et analyse d'actions
2. **📊 Portfolio** - Gérez vos positions et suivez vos gains
3. **⚙️ Configuration** - Configurez votre profil de risque
4. **📚 Documentation** - Guides et ressources

---

## 📁 Fichiers de Configuration

Les données sont sauvegardées automatiquement dans:

- **`dashboard/portfolio.json`** - Vos positions
- **`dashboard/user_config.json`** - Votre profil de risque et paramètres

Ces fichiers sont créés automatiquement au premier lancement.

### Exemple portfolio.json
```json
[
  {
    "symbol": "AAPL",
    "shares": 10,
    "avg_price": 150.0,
    "date_bought": "2024-01-15",
    "ibkr_plan": "Lite"
  }
]
```

### Exemple user_config.json
```json
{
  "risk_profile": "Modéré",
  "capital_initial": 10000.0,
  "available_cash": 8500.0,
  "max_loss_per_trade": 2.0,
  "max_portfolio_risk": 10.0,
  "ibkr_plan": "Lite",
  "trading_frequency": "Moyen terme",
  "objectives": []
}
```

---

## 💡 Exemples d'Utilisation

### Scénario 1: Configurer le Capital Initial

1. Aller dans **📊 Portfolio**
2. Section "Gestion du Capital"
3. Remplir le formulaire:
   - Capital disponible: `10000` (cash que vous avez)
   - Capital initial: `10000` (capital de départ)
4. Cliquer sur "Mettre à jour"

**Résultat:**
- Capital disponible: $10,000.00
- Capitalisation totale: $10,000.00
- Répartition: 100% Cash, 0% Investi

### Scénario 2: Ajouter une Position

1. Aller dans **📊 Portfolio**
2. Remplir le formulaire "Ajouter une Position":
   - Symbole: `AAPL`
   - Nombre d'actions: `10`
   - Prix d'achat: `150.00`
   - Date d'achat: `2024-01-15`
   - Plan IBKR: `Lite`
3. Cliquer sur "Ajouter la Position"

**Résultat:**
- Position ajoutée au tableau
- Frais calculés automatiquement selon le plan IBKR
- Gain IBKR vs Gain Réel affiché
- **Métriques mises à jour:**
  - Capital investi: $1,500.00 (10 × $150)
  - Capital disponible: $8,500.00 (reste à investir)
  - Capitalisation totale: $10,000.00 (si prix stable)
  - Répartition: 15% Investi, 85% Cash

### Scénario 3: Suivre l'Évolution du Portfolio

**Situation:**
- Capital initial: $10,000
- Position AAPL: 10 actions à $150 = $1,500 investi
- Prix actuel AAPL: $165 (+10%)

**Dashboard affiche:**
- 🏦 Capital Disponible: $8,500.00
- 💰 Capital Investi: $1,500.00
- 📊 Valeur Positions: $1,650.00 (10 × $165)
- 💎 **Capitalisation Totale: $10,150.00** ✅
- 💵 Plus-Value Nette: +$150.00 (après frais)
- Répartition: 16.3% Investi, 83.7% Cash

**Rendement total:** +1.5% sur capital total ($150 / $10,000)

### Scénario 4: Changer de Profil de Risque

1. Aller dans **⚙️ Configuration**
2. Comparer les profils dans le tableau
3. Sélectionner un nouveau profil (ex: "Agressif")
4. Ajuster les paramètres:
   - Perte max par trade: `3%`
   - Risque max portfolio: `15%`
5. Cliquer sur "Sauvegarder les Modifications"

**Résultat:**
- Profil changé à "Agressif"
- Nouvelles recommandations affichées
- Validation automatique du portfolio actuel
- Alertes si positions non conformes

### Scénario 5: Valider la Conformité

1. Aller dans **⚙️ Configuration**
2. Scroller jusqu'à "Validation du Portfolio"
3. Le système vérifie automatiquement:
   - ✅ Position AAPL: 8% (OK, max 15%)
   - ⚠️ Position TSLA: 12% (Proche limite 15%)
   - ❌ Position NVDA: 18% (Dépassement, max 15%)

---

## 🔍 Comprendre les Gains

### Exemple Concret

**Position:**
- Achat: 100 actions à 50$ = 5000$
- Frais d'achat (Pro Fixed): 100 × $0.005 = $0.50 (min $1) → **$1**
- Prix actuel: 55$
- Valeur actuelle: 100 × 55$ = 5500$
- Frais de vente estimés: **$1**
- Frais totaux: **$2**

**Calculs:**

1. **Gain IBKR (%)** (affiché dans IBKR):
   - `(55 - 50) / 50 × 100 = +10%`

2. **Gain Réel (%)** (après frais):
   - Plus-value brute: 5500 - 5000 = $500
   - Plus-value nette: 500 - 2 = $498
   - `498 / 5000 × 100 = +9.96%`

**Différence:** 0.04% de frais (impact faible avec plan Lite/Pro)

---

## 🛠️ Dépannage

### Le portfolio ne se charge pas
- Vérifier que `portfolio.json` existe dans `dashboard/`
- Si fichier corrompu, supprimer et relancer (sera recréé)

### Les prix ne se mettent pas à jour
- Les prix sont mis en cache pendant 5 minutes
- Recharger la page pour forcer la mise à jour
- Vérifier la connexion Internet (utilise Yahoo Finance)

### Erreur lors du calcul des frais
- Vérifier que le plan IBKR est correct (Lite/Pro Fixed/Pro Tiered)
- Vérifier que le prix et le nombre d'actions sont > 0

### Position non conforme au profil de risque
- Vérifier la taille de la position (valeur / portfolio total)
- Ajuster le profil de risque ou réduire la position

---

## 📊 Prochaines Améliorations Possibles

- [ ] Graphiques d'évolution du portfolio dans le temps
- [ ] Export des données en CSV/Excel
- [ ] Alertes de prix sur positions
- [ ] Analyse de diversification sectorielle
- [ ] Calcul de métriques avancées (Sharpe ratio, etc.)
- [ ] Import automatique depuis IBKR API
- [ ] Backtesting de stratégies
- [ ] Notifications par email

---

**Version:** 1.0.0
**Date:** 2026-02-20
**Status:** ✅ Production Ready
