# 🚀 Démarrage Rapide - Dashboard

## En 3 Étapes

### 1️⃣ Installer les Dépendances

```bash
cd trading_online
uv sync
```

**Temps** : ~2-3 minutes

---

### 2️⃣ (Optionnel) Configurer l'IA Locale

Pour utiliser l'analyse IA gratuite (0$), installez Ollama :

```bash
# Installation Ollama
# Windows/macOS: https://ollama.ai
# Linux:
curl -fsSL https://ollama.ai/install.sh | sh

# Télécharger le modèle
ollama pull deepseek-r1:14b
```

**Temps** : ~10 minutes (téléchargement 8.6 GB)

⚠️ **Optionnel** : Le dashboard fonctionne sans IA, mais vous n'aurez pas :
- Suggestions d'actions automatiques
- Analyse IA des graphiques

---

### 3️⃣ Lancer le Dashboard

```bash
# Méthode 1 : Commande directe
uv run streamlit run dashboard_app.py

# Méthode 2 : Script de lancement
./launch_dashboard.sh      # Linux/macOS
launch_dashboard.bat       # Windows
```

**Résultat** : Le navigateur s'ouvre automatiquement sur `http://localhost:8501`

**Temps** : ~10 secondes

---

## ✅ Test Rapide

Vérifiez que tout fonctionne :

```bash
uv run python test_dashboard.py
```

**Devrait afficher** :
```
✅ Streamlit
✅ Yahoo Finance
✅ Plotly
✅ Pandas
✅ DSPy
✅ PyYAML
✅ Configuration trouvée
✅ Ollama est installé et fonctionne
✅ Modèle deepseek-r1:14b trouvé

✅ Tout est prêt !
```

---

## 🎯 Premier Usage

1. **Ouvrir le dashboard** (déjà fait !)

2. **Aller dans l'onglet "🔍 Exploration"** (par défaut)

3. **Sélectionner une action** :
   - Catégorie : **Tech**
   - Symbole : **AAPL**

4. **Choisir une période** :
   - Période : **1 Mois**

5. **Charger les données** :
   - Cliquer sur **📥 Charger les données**

6. **Explorer** :
   - Regarder le graphique interactif
   - Vérifier les statistiques
   - Déplacer le curseur pour explorer les points

7. **(Optionnel) Générer une analyse IA** :
   - Cliquer sur **Générer une analyse IA**

**Temps total** : ~1 minute

---

## 📖 Documentation Complète

- **Guide complet** : [DASHBOARD_GUIDE.md](DASHBOARD_GUIDE.md)
- **Fonctionnalités** : [DASHBOARD_FEATURES.md](DASHBOARD_FEATURES.md)
- **README général** : [README.md](README.md)

---

## 🐛 Problèmes Courants

### Erreur : "ModuleNotFoundError: streamlit"

**Solution** :
```bash
uv sync
```

### Erreur : "Ollama not found"

**Solution** :
- Installez Ollama : https://ollama.ai
- Ou désactivez l'IA (le dashboard fonctionne quand même)

### Le graphique ne s'affiche pas

**Solution** :
- Vérifiez que les données sont chargées
- Rechargez la page (F5)
- Essayez un autre symbole

### Port 8501 déjà utilisé

**Solution** :
```bash
# Utiliser un autre port
uv run streamlit run dashboard_app.py --server.port 8502
```

---

## 🎉 C'est Tout !

Vous êtes prêt à analyser les marchés avec l'IA ! 🚀

**Prochaines étapes** :
- Explorez différentes actions
- Testez les différentes périodes
- Essayez la recherche IA
- Comparez plusieurs secteurs

---

**Besoin d'aide ?** → Consultez [DASHBOARD_GUIDE.md](DASHBOARD_GUIDE.md)
