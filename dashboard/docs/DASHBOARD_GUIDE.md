# 📈 Dashboard Streamlit - Guide d'Utilisation

## 🚀 Démarrage Rapide

### 1. Installer les dépendances

```bash
# Synchroniser les dépendances avec uv
uv sync
```

### 2. Lancer le dashboard

```bash
# Lancer l'application Streamlit
uv run streamlit run dashboard_app.py

# Ou avec options
uv run streamlit run dashboard_app.py --server.port 8501
```

Le dashboard s'ouvrira automatiquement dans votre navigateur à l'adresse : `http://localhost:8501`

## 🎯 Fonctionnalités

### 🔍 Onglet Exploration

L'onglet principal pour analyser les actions en temps réel.

#### **1. Recherche Assistée par IA** 💡

- Décrivez ce que vous recherchez en langage naturel
- L'IA (DSPy + Ollama) suggère des actions pertinentes
- Exemples de requêtes :
  - "actions technologiques prometteuses"
  - "secteur énergie renouvelable"
  - "dividendes stables"
  - "small caps américaines"

#### **2. Sélection d'Action**

Deux façons de choisir une action :

**A. Par catégorie**
- Tech : AAPL, MSFT, GOOGL, META, NVDA, TSLA, AMZN, NFLX
- Finance : JPM, BAC, WFC, GS, MS, C, USB
- Energie : XOM, CVX, COP, SLB, OXY, EOG
- Santé : JNJ, UNH, PFE, ABBV, TMO, LLY
- Consommation : WMT, PG, KO, PEP, MCD, NKE
- Industrie : BA, CAT, GE, MMM, HON, UPS

**B. Symbole personnalisé**
- Entrez n'importe quel symbole Yahoo Finance
- Exemples : TSLA, BTC-USD, EUR=X, ^GSPC

#### **3. Périodes d'Analyse**

| Période | Données | Intervalle | Axe X |
|---------|---------|------------|-------|
| **1 Jour** | 1 jour | 1 minute | Heures (HH:MM) |
| **5 Jours** | 5 jours | 5 minutes | Dates |
| **1 Mois** | 1 mois | 1 heure | Dates |
| **6 Mois** | 6 mois | 1 jour | Dates |
| **1 An** | 1 an | 1 jour | Dates |
| **5 Ans** | 5 ans | 1 semaine | Dates |
| **10 Ans** | 10 ans | 1 semaine | Dates |

#### **4. Statistiques Affichées** 📊

- **Prix Actuel** : Dernier prix de clôture avec variation %
- **Minimum** : Prix le plus bas sur la période
- **Maximum** : Prix le plus haut sur la période
- **Moyenne** : Prix moyen sur la période
- **Volatilité** : Écart-type des prix

#### **5. Graphique Interactif** 📈

**Graphique en chandelier (Candlestick)**
- **Vert** : Clôture > Ouverture (hausse)
- **Rouge** : Clôture < Ouverture (baisse)
- Affiche : Open, High, Low, Close (OHLC)
- Graphique de volume en dessous

**Fonctionnalités interactives**
- ✅ Zoom avec la souris
- ✅ Pan (déplacer la vue)
- ✅ Hover pour voir les détails
- ✅ Reset zoom (double-clic)
- ✅ Export en image (bouton caméra)

#### **6. Curseur d'Exploration** 🔍

- Déplacez le curseur pour naviguer dans le temps
- Affiche les valeurs exactes pour chaque point :
  - Date/Heure
  - Prix d'ouverture
  - Prix de clôture
  - Prix haut/bas
  - Volume échangé

#### **7. Analyse IA** 🤖

- Génère une analyse détaillée de l'action
- Points clés automatiques
- Utilise DSPy + Ollama (local, gratuit)

## 📊 Autres Onglets (À venir)

### Portfolio
- Vue d'ensemble du portefeuille
- Positions actuelles
- Performance globale

### Configuration
- Paramètres du dashboard
- Configuration LLM
- Préférences d'affichage

### Documentation
- Guide interactif
- Exemples d'utilisation
- FAQ

## 🛠️ Configuration

### Configuration DSPy / LLM

Le dashboard utilise par défaut **Ollama + DeepSeek-R1** (gratuit, local).

**Prérequis** :
```bash
# Installer Ollama
# https://ollama.ai

# Télécharger DeepSeek-R1
ollama pull deepseek-r1:14b

# Vérifier qu'Ollama est lancé
ollama list
```

**Alternative : Utiliser OpenAI ou Anthropic**

Modifiez `src/config/config.yaml` :

```yaml
multi_agent:
  # Option 1 : OpenAI
  llm_provider: openai
  model_name: gpt-4o-mini

  # Option 2 : Anthropic
  llm_provider: anthropic
  model_name: claude-3-5-sonnet-20241022
```

Et définissez la clé API :
```bash
export OPENAI_API_KEY=sk-...
# ou
export ANTHROPIC_API_KEY=sk-ant-...
```

## 💡 Exemples d'Utilisation

### Exemple 1 : Analyser AAPL sur 1 mois

1. Aller dans **🔍 Exploration**
2. Catégorie : **Tech**
3. Symbole : **AAPL**
4. Période : **1 Mois**
5. Cliquer **📥 Charger les données**
6. Explorer avec le curseur
7. Cliquer **Générer une analyse IA**

### Exemple 2 : Recherche avec IA

1. Aller dans **🔍 Exploration**
2. Ouvrir **💡 Recherche assistée par IA**
3. Entrer : "actions tech avec forte croissance"
4. Cliquer **🔍 Suggérer des actions**
5. Sélectionner une action suggérée
6. Analyser

### Exemple 3 : Crypto-monnaies

1. Symbole personnalisé : **BTC-USD**
2. Période : **1 An**
3. Charger les données
4. Comparer avec **ETH-USD**

### Exemple 4 : Indices

1. Symbole personnalisé : **^GSPC** (S&P 500)
2. Période : **10 Ans**
3. Analyser la tendance long terme

## 🔥 Raccourcis Clavier

| Touche | Action |
|--------|--------|
| `R` | Recharger l'application |
| `C` | Effacer le cache |
| `?` | Aide Streamlit |

## ⚡ Optimisations

### Cache
- Les données sont mises en cache 5 minutes
- La configuration DSPy est mise en cache
- Rechargez si besoin avec `C`

### Performance
- Utilisez des périodes adaptées :
  - Intraday (1j) : intervalle 1m
  - Court terme (5j-1m) : intervalle 5m-1h
  - Long terme (1an+) : intervalle 1d-1wk

## 🐛 Dépannage

### Erreur : "Ollama not found"
```bash
# Vérifier qu'Ollama est installé
ollama --version

# Démarrer Ollama
ollama serve
```

### Erreur : "No data available"
- Vérifiez que le symbole est correct
- Certains symboles n'ont pas d'historique long
- Essayez une période plus courte

### Erreur : "DSPy configuration failed"
- Vérifiez qu'Ollama est lancé
- Ou configurez OpenAI/Anthropic avec une clé API

### Le graphique ne s'affiche pas
- Rechargez la page (F5)
- Vérifiez que les données sont chargées
- Essayez un autre navigateur (Chrome recommandé)

## 📚 Ressources

### Symboles Yahoo Finance
- **Actions US** : AAPL, MSFT, TSLA...
- **Crypto** : BTC-USD, ETH-USD, DOGE-USD...
- **Forex** : EUR=X, GBP=X, JPY=X...
- **Indices** : ^GSPC (S&P 500), ^DJI (Dow Jones), ^IXIC (Nasdaq)
- **Matières premières** : GC=F (Or), CL=F (Pétrole)

### Documentation
- [Yahoo Finance](https://finance.yahoo.com)
- [Streamlit Docs](https://docs.streamlit.io)
- [Plotly Charts](https://plotly.com/python/)
- [DSPy Framework](https://dspy-docs.vercel.app/)

## 🚀 Prochaines Fonctionnalités

- [ ] Comparaison de plusieurs actions
- [ ] Indicateurs techniques (RSI, MACD, Bollinger)
- [ ] Alertes de prix
- [ ] Export des analyses en PDF
- [ ] Backtesting de stratégies
- [ ] Portfolio tracking en temps réel
- [ ] Intégration avec Interactive Brokers

## ❓ Questions Fréquentes

**Q: Le dashboard fonctionne-t-il sans Internet ?**
R: Non, il nécessite Internet pour télécharger les données via Yahoo Finance. Mais l'IA (Ollama) fonctionne en local.

**Q: Puis-je analyser des actions étrangères ?**
R: Oui ! Utilisez les suffixes :
- `.PA` : Paris (ex: MC.PA pour LVMH)
- `.L` : Londres
- `.TO` : Toronto
- `.HK` : Hong Kong

**Q: Les données sont-elles en temps réel ?**
R: Les données ont un délai de ~15 minutes (gratuit). Pour le temps réel, utilisez Interactive Brokers.

**Q: Combien coûte le dashboard ?**
R: **0$** avec Ollama (local). Avec OpenAI/Anthropic, voir [MULTI_LLM_GUIDE.md](MULTI_LLM_GUIDE.md).

---

**Développé avec** ❤️ **pour Quantum Trader**

**Version** : 1.0.0
**Date** : 2026-02-20
