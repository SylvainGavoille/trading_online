# 🔍 Agent de Recherche d'Actions - Documentation

## Vue d'Ensemble

L'agent de recherche d'actions est un système intelligent qui permet de trouver rapidement des actions, ETFs, indices ou cryptomonnaies dans une base de données complète de plus de **100 instruments financiers**.

## 🎯 Fonctionnalités

### 1. Base de Données Étendue

**Plus de 100 instruments** répertoriés avec :
- **Symbole** : Ticker (ex: AAPL, QQQ, BTC-USD)
- **Nom complet** : Nom de l'entreprise/produit
- **Type** : Stock, ETF, Index, Crypto, Commodity, Forex
- **Secteur** : Technology, Finance, Energy, Healthcare, etc.
- **Description détaillée** : Activité, produits, services

### 2. Recherche Multi-Critères

L'agent recherche dans **tous les champs** :
- ✅ Symbole (AAPL, GOOGL, etc.)
- ✅ Nom de l'entreprise
- ✅ Type d'instrument
- ✅ Secteur d'activité
- ✅ Mots-clés dans la description

### 3. Score de Pertinence

Chaque résultat est **noté automatiquement** :
- Symbole exact : +10 points
- Nom correspondant : +8 points
- Secteur correspondant : +7 points
- Type correspondant : +5 points
- Description contenant le mot-clé : +3 points
- Bonus : +2 à +4 pour chaque mot-clé supplémentaire

Les résultats sont **triés par pertinence** décroissante.

## 📊 Catégories Disponibles

### Actions (Stocks)

**Technology** (13 actions)
- AAPL (Apple), MSFT (Microsoft), GOOGL (Alphabet)
- META (Meta/Facebook), NVDA (NVIDIA), TSLA (Tesla)
- AMZN (Amazon), NFLX (Netflix), AMD, INTC, CRM, ORCL, ADBE

**Finance** (8 actions)
- JPM (JPMorgan), BAC (Bank of America), WFC (Wells Fargo)
- GS (Goldman Sachs), MS (Morgan Stanley), V (Visa)
- MA (Mastercard), BLK (BlackRock)

**Energy** (5 actions)
- XOM (Exxon), CVX (Chevron), COP (ConocoPhillips)
- SLB (Schlumberger), NEE (NextEra Energy - renouvelable)

**Healthcare** (7 actions)
- JNJ (Johnson & Johnson), UNH (UnitedHealth), PFE (Pfizer)
- ABBV (AbbVie), TMO (Thermo Fisher), LLY (Eli Lilly), MRNA (Moderna)

**Consumer** (7 actions)
- WMT (Walmart), PG (Procter & Gamble), KO (Coca-Cola)
- PEP (PepsiCo), MCD (McDonald's), NKE (Nike), SBUX (Starbucks)

**Industrials** (5 actions)
- BA (Boeing), CAT (Caterpillar), GE (General Electric)
- MMM (3M), UPS (United Parcel Service)

### ETFs (40+ ETFs)

**Tech ETFs**
- QQQ (Nasdaq-100), XLK (S&P Tech), VGT (Vanguard IT), ARKK (ARK Innovation)

**Broad Market ETFs**
- SPY (S&P 500), VOO (Vanguard S&P 500), VTI (Total Market), IWM (Russell 2000)

**Sector ETFs**
- XLF (Finance), XLE (Energy), XLV (Healthcare), XLI (Industrials)
- XLP (Consumer Staples), XLY (Consumer Discretionary)

**Energy ETFs**
- ICLN (Clean Energy), TAN (Solar)

**International ETFs**
- VEA (Developed Markets), VWO (Emerging Markets)
- EWJ (Japan), EWG (Germany), FXI (China)

**Dividend ETFs**
- VYM (High Dividend), SCHD (Dividend Growth), DGRO (Dividend Growth)

**Bond ETFs**
- AGG (Aggregate Bond), BND (Total Bond), TLT (Long Treasury)

**Real Estate & Commodities**
- VNQ (Real Estate), IYR (Real Estate)
- GLD (Gold), SLV (Silver), USO (Oil)

**Crypto ETFs**
- BITO (Bitcoin Futures), IBIT (Bitcoin Spot - BlackRock)

### Cryptomonnaies

- BTC-USD (Bitcoin)
- ETH-USD (Ethereum)
- DOGE-USD (Dogecoin)

### Indices

- ^GSPC (S&P 500)
- ^DJI (Dow Jones)
- ^IXIC (Nasdaq Composite)

### Forex

- EUR=X (Euro/USD)
- GBP=X (Pound/USD)
- JPY=X (Yen/USD)

### Matières Premières

- GC=F (Gold Futures)
- CL=F (Crude Oil Futures)

## 🚀 Utilisation dans le Dashboard

### Recherche Simple

1. Ouvrir le dashboard : `uv run streamlit run dashboard_app.py`
2. Aller dans **🔍 Exploration**
3. Ouvrir **💡 Recherche Intelligente d'Actions**
4. Entrer une requête (ex: "ETF tech")
5. Cliquer **🔍 Rechercher**

### Résultats Affichés

**Tableau structuré** avec :
- 📌 **Symbole** : Ticker
- 🏢 **Nom** : Nom complet
- 📝 **Description** : Activité détaillée

**Sélection rapide** :
- Boutons cliquables pour charger directement l'action

### Exemples de Requêtes

| Requête | Résultats Attendus |
|---------|-------------------|
| `tech ETF` | QQQ, XLK, VGT, ARKK |
| `energie renouvelable` | NEE, ICLN, TAN |
| `bitcoin` | BTC-USD, BITO, IBIT |
| `dividendes` | VYM, SCHD, DGRO |
| `S&P 500` | SPY, VOO, ^GSPC |
| `finance` | JPM, BAC, XLF, V, MA |
| `cloud` | MSFT, AMZN, GOOGL, CRM |
| `vaccin` | PFE, MRNA, JNJ |
| `or` | GLD, GC=F |
| `japon` | EWJ |

## 🔧 Architecture Technique

### Fichiers

```
src/
├── data/
│   └── stocks_database.py     # Base de données complète (100+ instruments)
└── agents/
    └── stock_search_agent.py  # Agent de recherche intelligent
```

### Fonctions Principales

**stocks_database.py**
```python
search_stocks(query: str, max_results: int) -> list[dict]
# Recherche par score de pertinence

get_stocks_by_sector(sector: str) -> list[dict]
# Filtrer par secteur

get_stocks_by_type(stock_type: str) -> list[dict]
# Filtrer par type (Stock, ETF, etc.)
```

**stock_search_agent.py**
```python
simple_stock_search(query: str, max_results: int) -> tuple[list[dict], str]
# Recherche simple sans LLM (toujours disponible)

StockSearchAgent.forward(user_query: str, max_results: int)
# Recherche avec LLM DSPy (nécessite Ollama)
```

### Modes de Fonctionnement

**Mode 1 : Recherche Simple (Toujours Disponible)**
- Pas besoin d'Ollama
- Recherche par mots-clés
- Score de pertinence algorithmique
- Retour immédiat

**Mode 2 : Recherche Intelligente (Avec Ollama)**
- Nécessite Ollama + DSPy configuré
- Le LLM comprend l'intention
- Sélection contextuelle des meilleurs résultats
- Explication générée par l'IA

## 💡 Avantages

### Par rapport à l'ancien système

**Avant** :
- ❌ Suggestions LLM génériques (AAPL, GOOGL...)
- ❌ Pas de descriptions
- ❌ ETFs non couverts
- ❌ Pas de recherche structurée

**Maintenant** :
- ✅ Base de données complète et structurée
- ✅ 100+ instruments (actions, ETFs, crypto, indices)
- ✅ Descriptions détaillées
- ✅ Recherche multi-critères
- ✅ Score de pertinence
- ✅ Tableau interactif
- ✅ Sélection rapide (1 clic)

### Cas d'Usage

**1. Trouver des ETF thématiques**
```
Requête: "ETF tech"
Résultats: QQQ, XLK, VGT, ARKK
Action: Sélection en 1 clic → Analyse graphique
```

**2. Explorer les énergies renouvelables**
```
Requête: "energie renouvelable"
Résultats: NEE, ICLN, TAN
Voir descriptions: Solaire, éolien, hydrogène
```

**3. Exposition au Bitcoin**
```
Requête: "bitcoin"
Résultats: BTC-USD (spot), BITO (futures), IBIT (ETF spot)
Comparer: ETF régulé vs crypto directe
```

**4. Diversification internationale**
```
Requête: "japon"
Résultats: EWJ (iShares MSCI Japan ETF)
```

## 📈 Prochaines Améliorations

### Phase 2 : Base de Données
- [ ] Ajouter 200+ actions supplémentaires
- [ ] Actions européennes (.PA, .L, .DE)
- [ ] Plus d'ETFs thématiques (IA, robotique, cybersécurité)
- [ ] Cryptos additionnelles (ADA, SOL, AVAX)

### Phase 3 : Fonctionnalités
- [ ] Filtres avancés (secteur, type, volatilité)
- [ ] Tri personnalisable (alpha, pertinence, secteur)
- [ ] Watchlist (sauvegarder les favoris)
- [ ] Comparaison côte à côte

### Phase 4 : Données Temps Réel
- [ ] Prix actuel dans le tableau
- [ ] Variation % journalière
- [ ] Capitalisation boursière
- [ ] Ratio P/E, dividendes

### Phase 5 : Intégration IA Avancée
- [ ] Clustering automatique (actions similaires)
- [ ] Recommandations basées sur le portfolio
- [ ] Analyse de corrélation
- [ ] Détection de tendances

## 🧪 Tests

### Test Manuel
```bash
cd trading_online
uv run python src/agents/stock_search_agent.py
```

**Résultats attendus** :
```
Test 1: Recherche 'tech ETF'
Résultats: 4-5 ETFs technologiques

Test 2: Recherche 'energie renouvelable'
Résultats: 2-3 actions/ETFs

Test 3: Recherche 'bitcoin'
Résultats: 3 instruments (BTC-USD, BITO, IBIT)
```

### Test dans le Dashboard
1. Lancer : `uv run streamlit run dashboard_app.py`
2. Recherche : "ETF tech"
3. Vérifier : Tableau avec QQQ, XLK, VGT, ARKK
4. Cliquer : Bouton "QQQ"
5. Confirmer : Symbole chargé automatiquement

## 📚 Ressources

### Code Source
- `src/data/stocks_database.py` - Base de données
- `src/agents/stock_search_agent.py` - Agent de recherche
- `dashboard_app.py` - Interface Streamlit

### Documentation
- README.md - Guide général
- DASHBOARD_GUIDE.md - Guide du dashboard
- QUICK_START_DASHBOARD.md - Démarrage rapide

---

**Version** : 1.0.0
**Date** : 2026-02-20
**Auteur** : Quantum Trader Team
