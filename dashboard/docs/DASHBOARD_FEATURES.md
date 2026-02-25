# 📊 Dashboard Streamlit - Fonctionnalités Détaillées

## 🎯 Vue d'Ensemble

Le dashboard Streamlit est une **interface web interactive** pour explorer et analyser les marchés financiers avec l'aide de l'intelligence artificielle.

```
┌─────────────────────────────────────────────────────────────┐
│  📈 Quantum Trader - Dashboard Interactif                   │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│  Sidebar                     Main Panel                     │
│  ┌──────────┐               ┌──────────────────────┐       │
│  │ 🔍 Exploration           │  💡 Recherche IA      │       │
│  │ 📊 Portfolio             │  🎯 Sélection Action  │       │
│  │ ⚙️ Config                │  📈 Graphique         │       │
│  │ 📚 Docs                  │  📊 Statistiques      │       │
│  └──────────┘               │  🔍 Curseur          │       │
│                              │  🤖 Analyse IA       │       │
│                              └──────────────────────┘       │
└─────────────────────────────────────────────────────────────┘
```

## 🔥 Fonctionnalités Principales

### 1. 💡 Recherche Assistée par IA

**Interaction en langage naturel**

```
User: "actions technologiques prometteuses"
  ↓
IA (DSPy + Ollama):
  ✅ Suggestions: AAPL, MSFT, NVDA, META, GOOGL
  ✅ Explication: "Ces actions du secteur tech montrent..."
```

**Exemples de requêtes** :
- "secteur énergie renouvelable"
- "dividendes stables avec croissance"
- "small caps prometteuses"
- "tech avec forte innovation"

---

### 2. 🎯 Sélection Multi-Source

**A. Par Catégorie**

```
Tech        →  AAPL, MSFT, GOOGL, META, NVDA, TSLA, AMZN, NFLX
Finance     →  JPM, BAC, WFC, GS, MS, C, USB
Energie     →  XOM, CVX, COP, SLB, OXY, EOG
Santé       →  JNJ, UNH, PFE, ABBV, TMO, LLY
Consomm.    →  WMT, PG, KO, PEP, MCD, NKE
Industrie   →  BA, CAT, GE, MMM, HON, UPS
```

**B. Symbole Personnalisé**

Supports :
- ✅ Actions US : `AAPL`, `TSLA`, `GOOGL`
- ✅ Crypto : `BTC-USD`, `ETH-USD`, `DOGE-USD`
- ✅ Forex : `EUR=X`, `GBP=X`, `JPY=X`
- ✅ Indices : `^GSPC` (S&P 500), `^DJI` (Dow), `^IXIC` (Nasdaq)
- ✅ Matières premières : `GC=F` (Or), `CL=F` (Pétrole)
- ✅ Actions étrangères : `MC.PA` (LVMH), `TSLA.L` (Londres)

---

### 3. 📅 Multi-Périodes

| Période | Durée | Intervalle | Points | Axe X | Usage |
|---------|-------|------------|--------|-------|-------|
| **1 Jour** | 1 jour | 1 minute | ~390 | HH:MM | Intraday trading |
| **5 Jours** | 5 jours | 5 minutes | ~468 | Date | Court terme |
| **1 Mois** | 1 mois | 1 heure | ~150 | Date | Swing trading |
| **6 Mois** | 6 mois | 1 jour | ~120 | Date | Moyen terme |
| **1 An** | 1 an | 1 jour | ~252 | Date | Analyse annuelle |
| **5 Ans** | 5 ans | 1 semaine | ~260 | Date | Tendance long terme |
| **10 Ans** | 10 ans | 1 semaine | ~520 | Date | Analyse historique |

**Optimisation automatique** :
- Périodes courtes (1j-5j) → Intervalles fins (1m-5m)
- Périodes moyennes (1m-6m) → Intervalles horaires/journaliers
- Périodes longues (1an+) → Intervalles hebdomadaires

---

### 4. 📊 Statistiques Calculées

```
┌─────────────────────────────────────────────────────────┐
│  Prix Actuel    │  Minimum     │  Maximum     │  Moyenne  │  Volatilité  │
│  $175.23        │  $145.67     │  $182.94     │  $167.45  │  $12.34      │
│  +2.45%         │              │              │           │              │
└─────────────────────────────────────────────────────────┘
```

**Métriques disponibles** :
- `Prix Actuel` : Dernier prix de clôture + variation %
- `Minimum` : Prix le plus bas sur la période
- `Maximum` : Prix le plus haut sur la période
- `Moyenne` : Prix moyen (mean)
- `Volatilité` : Écart-type (std dev)
- `Volume Moyen` : Volume moyen échangé
- `Volume Total` : Somme des volumes

**Calcul de variation** :
```
Variation $ = Prix Final - Prix Initial
Variation % = (Prix Final - Prix Initial) / Prix Initial × 100
```

---

### 5. 📈 Graphique Interactif

#### Graphique en Chandelier (Candlestick)

```
     High ─┐
          │
 Open ────┤  ┌─ Close (si Close > Open → Vert)
          │  │
     Low ─┴──┘

Couleurs:
 🟢 Vert  : Clôture > Ouverture (hausse)
 🔴 Rouge : Clôture < Ouverture (baisse)
```

#### Interactions

| Action | Résultat |
|--------|----------|
| **Scroll** | Zoom in/out |
| **Drag** | Pan (déplacer) |
| **Hover** | Afficher valeurs exactes |
| **Double-click** | Reset zoom |
| **📷 Bouton** | Export image PNG |
| **🔍 Bouton** | Zoom sélection |

#### Graphique de Volume

- Barre sous le graphique de prix
- Même code couleur (vert/rouge)
- Affiche l'activité de trading

---

### 6. 🔍 Curseur d'Exploration

**Navigation temporelle fluide**

```
[━━━━━━━━━━━━━━━━━━●━━━━━━━━━━]  Slider
                    ↑
            Point sélectionné

┌───────────────────────────────────────┐
│  Date : 15/01/2026                    │
│  Ouverture : $175.23                  │
│  Clôture   : $177.45  (+1.27%)        │
│  Haut      : $178.90                  │
│  Bas       : $174.12                  │
│  Volume    : 52,345,678               │
└───────────────────────────────────────┘
```

**Utilisation** :
1. Déplacez le curseur avec la souris
2. Les valeurs se mettent à jour en temps réel
3. Explorez point par point l'historique

---

### 7. 🤖 Analyse IA (DSPy)

**Génération automatique d'insights**

```
Input:
  Symbol : AAPL
  Data   : Prix, Stats, Période
    ↓
  DSPy + Ollama (DeepSeek-R1)
    ↓
Output:
  📝 Analyse détaillée
  ⚡ Points clés (bullet points)
```

**Exemple d'analyse** :

```
📝 Analyse détaillée:
"Apple (AAPL) montre une tendance haussière sur les 6 derniers mois
avec une volatilité modérée de $12.34. Le prix a progressé de +15.3%,
dépassant la moyenne du marché. Le volume de trading a augmenté de
23% sur cette période, indiquant un fort intérêt..."

⚡ Points clés:
• Tendance: Haussière (+15.3% sur 6 mois)
• Volatilité: Modérée ($12.34)
• Volume: En hausse (+23%)
• Support: $145.67 (minimum période)
• Résistance: $182.94 (maximum période)
```

---

## 🎨 Interface Utilisateur

### Thème

- **Mode** : Dark (optimisé pour longues sessions)
- **Couleur primaire** : `#26a69a` (vert cyan)
- **Police** : Sans-serif moderne
- **Layout** : Wide (pleine largeur)

### Navigation

```
Sidebar
├── 🔍 Exploration  ← Tab actif
├── 📊 Portfolio    (à venir)
├── ⚙️ Configuration (à venir)
└── 📚 Documentation (à venir)
```

### Responsive

- ✅ Desktop : Optimisé
- ✅ Tablette : Supporté
- ⚠️  Mobile : Limité (graphiques complexes)

---

## ⚡ Performance

### Cache

```python
@st.cache_data(ttl=300)  # 5 minutes
def download_stock_data(...)

@st.cache_resource
def setup_dspy(...)
```

**Avantages** :
- Données mises en cache 5 minutes
- Pas de re-téléchargement inutile
- Configuration DSPy persistante
- Navigation rapide

### Optimisations

1. **Lazy Loading** : Données chargées à la demande
2. **Session State** : Données conservées entre interactions
3. **Plotly** : Rendu GPU accéléré
4. **Intervalle adaptatif** : Moins de points pour périodes longues

---

## 🔌 Intégrations

### Yahoo Finance (yfinance)

```python
ticker = yf.Ticker("AAPL")
df = ticker.history(period="1mo", interval="1h")
```

**Sources de données** :
- Prix OHLC (Open, High, Low, Close)
- Volume
- Historique complet
- Gratuit (délai ~15 min)

### DSPy Framework

```python
class StockSuggestion(dspy.Signature):
    user_query: str = dspy.InputField(...)
    suggestions: List[str] = dspy.OutputField(...)

suggest_stocks = dspy.ChainOfThought(StockSuggestion)
```

**Providers supportés** :
- ✅ Ollama (local, gratuit)
- ✅ OpenAI (cloud, $3-5/jour)
- ✅ Anthropic Claude (cloud, $24/jour)

### Plotly

```python
fig = go.Candlestick(
    x=df.index,
    open=df['Open'],
    high=df['High'],
    low=df['Low'],
    close=df['Close']
)
```

**Avantages** :
- Interactivité native
- Export haute qualité
- Customisation complète
- Responsive

---

## 🚀 Cas d'Usage

### 1. Analyse Rapide d'une Action

```
1. Ouvrir dashboard
2. Catégorie → Tech
3. Symbole → AAPL
4. Période → 1 Mois
5. Charger données
6. Analyser graphique + stats
Temps: ~30 secondes
```

### 2. Recherche de Nouvelles Actions

```
1. Recherche IA → "secteur santé stable"
2. IA suggère → JNJ, UNH, PFE, ABBV, TMO
3. Tester chacune sur 6 mois
4. Comparer volatilité
5. Décision
Temps: ~5 minutes
```

### 3. Analyse Technique Détaillée

```
1. Symbole → TSLA
2. Période → 5 Ans
3. Identifier tendances long terme
4. Changer → 1 Mois
5. Analyser pattern récent
6. Curseur → Points d'entrée/sortie
7. Analyse IA pour confirmation
Temps: ~10 minutes
```

### 4. Surveillance Crypto

```
1. Symbole → BTC-USD
2. Période → 1 Jour (intraday)
3. Observer volatilité
4. Curseur → Identifier patterns
5. Comparer avec ETH-USD
Temps: ~3 minutes
```

---

## 🎓 Prochaines Fonctionnalités

### Phase 2 : Onglet Portfolio

- [ ] Connexion Interactive Brokers
- [ ] Positions en temps réel
- [ ] P&L tracking
- [ ] Graphique de performance
- [ ] Allocation d'actifs

### Phase 3 : Indicateurs Techniques

- [ ] RSI (Relative Strength Index)
- [ ] MACD (Moving Average Convergence Divergence)
- [ ] Bollinger Bands
- [ ] SMA / EMA (Moyennes mobiles)
- [ ] Volume Profile

### Phase 4 : Alertes

- [ ] Alertes de prix (seuils)
- [ ] Alertes de volume
- [ ] Alertes RSI (surachat/survente)
- [ ] Notifications email/SMS
- [ ] Alertes IA personnalisées

### Phase 5 : Backtesting

- [ ] Définir stratégies custom
- [ ] Tester sur historique
- [ ] Métriques de performance
- [ ] Comparaison stratégies
- [ ] Export rapports

### Phase 6 : Multi-Actions

- [ ] Comparaison côte à côte
- [ ] Corrélation entre actions
- [ ] Heatmap de secteurs
- [ ] Screener d'actions
- [ ] Watchlist personnalisée

---

## 📚 Ressources

- **Code** : `dashboard_app.py`
- **Guide** : [DASHBOARD_GUIDE.md](DASHBOARD_GUIDE.md)
- **Test** : `python test_dashboard.py`
- **Lancement** : `uv run streamlit run dashboard_app.py`

---

**Développé avec** ❤️ **pour Quantum Trader**

**Technologies** :
- Streamlit (Interface)
- Plotly (Graphiques)
- Yahoo Finance (Données)
- DSPy + Ollama (IA)
- Pandas (Analyse)

**Version** : 1.0.0
**Date** : 2026-02-20
