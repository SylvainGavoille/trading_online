# 🤖 Configuration LLM pour le Dashboard

## 📊 État Actuel

**Par défaut, le dashboard fonctionne SANS IA si Ollama n'est pas installé.**

Le dashboard a 2 modes :
1. **Mode Simple** (actuel) - Recherche algorithmique sans LLM
2. **Mode IA** - Avec analyse intelligente par LLM

---

## 🎯 Options de Configuration

### Option 1 : Ollama + DeepSeek-R1 (GRATUIT ⭐)

**Avantages** :
- ✅ 0$ de coût
- ✅ Fonctionne en local (données privées)
- ✅ Pas de limite d'utilisation
- ✅ Bon modèle de raisonnement

**Installation** :

#### Étape 1 : Installer Ollama

```powershell
# Windows
# Télécharger sur https://ollama.ai et installer

# Linux
curl -fsSL https://ollama.ai/install.sh | sh
```

#### Étape 2 : Télécharger DeepSeek-R1

```powershell
ollama pull deepseek-r1:14b
# Taille : 8.6 GB
# Temps : ~10 minutes
```

#### Étape 3 : Vérifier

```powershell
ollama list
# Devrait afficher : deepseek-r1:14b
```

#### Étape 4 : Configuration (Déjà Faite)

Le dashboard est déjà configuré pour Ollama par défaut. Aucune modification nécessaire.

#### Étape 5 : Lancer

```powershell
run_dashboard.bat
```

**Configuration automatique** :
```yaml
# src/config/config.yaml
multi_agent:
  llm_provider: ollama  # Par défaut
  model_name: deepseek-r1:14b
```

---

### Option 2 : OpenAI (Cloud - ~$3-5/jour)

**Avantages** :
- ✅ Rapide
- ✅ Pas d'installation locale
- ✅ API officielle

**Coût** : ~$3-5 par jour d'utilisation intensive

#### Étape 1 : Obtenir une Clé API

1. Aller sur https://platform.openai.com
2. Créer un compte
3. Générer une clé API

#### Étape 2 : Configurer la Clé

```powershell
# Windows (PowerShell)
$env:OPENAI_API_KEY="sk-..."

# Linux/macOS
export OPENAI_API_KEY="sk-..."
```

#### Étape 3 : Modifier la Configuration

```yaml
# src/config/config.yaml
multi_agent:
  llm_provider: openai
  model_name: gpt-4o-mini  # ou gpt-4o
```

#### Étape 4 : Lancer

```powershell
run_dashboard.bat
```

---

### Option 3 : Anthropic Claude (Cloud - ~$24/jour)

**Avantages** :
- ✅ Meilleure qualité d'analyse
- ✅ Très bon pour le raisonnement
- ✅ API officielle

**Coût** : ~$24 par jour d'utilisation intensive

#### Étape 1 : Obtenir une Clé API

1. Aller sur https://console.anthropic.com
2. Créer un compte
3. Générer une clé API

#### Étape 2 : Configurer la Clé

```powershell
# Windows (PowerShell)
$env:ANTHROPIC_API_KEY="sk-ant-..."

# Linux/macOS
export ANTHROPIC_API_KEY="sk-ant-..."
```

#### Étape 3 : Modifier la Configuration

```yaml
# src/config/config.yaml
multi_agent:
  llm_provider: anthropic
  model_name: claude-3-5-sonnet-20241022
```

#### Étape 4 : Lancer

```powershell
run_dashboard.bat
```

---

## 🔍 Vérifier le Mode Actif

### Dans le Dashboard

1. Lancer : `run_dashboard.bat`
2. Onglet **🔍 Exploration**
3. Section **💡 Recherche Intelligente d'Actions**

**Si IA configurée** :
```
✅ Bouton "🔍 Rechercher" activé
✅ Section "Générer une analyse IA" visible
```

**Si IA non configurée** :
```
🔵 Recherche simple fonctionne (sans IA)
⚠️  Analyse IA désactivée
```

### Dans les Logs

Lancer le test :
```powershell
cd dashboard
uv run python test_dashboard.py
```

**Résultat** :
```
>> Vérification d'Ollama...
[OK] Ollama est installé et fonctionne
[OK] Modèle deepseek-r1:14b trouvé
```

OU

```
[AVERTISSEMENT] Ollama n'est pas installé
   (Le dashboard fonctionnera sans l'IA)
```

---

## 📊 Comparaison des Options

| Option | Coût | Installation | Performance | Données |
|--------|------|--------------|-------------|---------|
| **Ollama + DeepSeek** | **0$** | Locale (8.6GB) | Rapide avec GPU | Privées |
| OpenAI gpt-4o-mini | ~$3-5/jour | Aucune | Très rapide | Cloud |
| Anthropic Claude | ~$24/jour | Aucune | Excellente | Cloud |
| **Sans IA** (actuel) | **0$** | Aucune | Instant | Locales |

---

## 🎯 Recommandation

### Pour Débutants
**Utilisez le mode actuel (sans IA)** - Fonctionne déjà bien pour :
- ✅ Recherche d'actions
- ✅ Graphiques interactifs
- ✅ Statistiques

### Pour Utilisateurs Avancés
**Installez Ollama + DeepSeek** (gratuit) pour :
- ✅ Suggestions d'actions intelligentes
- ✅ Analyse IA des graphiques
- ✅ Insights automatiques

### Pour Production
**OpenAI gpt-4o-mini** si vous préférez le cloud (rapide, stable)

---

## 🔧 Configuration Avancée

### Modèles Alternatifs

#### Ollama - Autres Modèles

```yaml
# Plus petit, plus rapide
model_name: llama3:8b

# Plus grand, meilleur
model_name: llama3:70b

# Spécialisé code
model_name: codellama:13b
```

#### OpenAI - Autres Modèles

```yaml
# Plus économique
model_name: gpt-3.5-turbo

# Plus performant
model_name: gpt-4o
```

#### Anthropic - Autres Modèles

```yaml
# Plus rapide
model_name: claude-3-haiku-20240307

# Meilleur raisonnement
model_name: claude-opus-4-20250514
```

---

## 🧪 Tester la Configuration

### Test 1 : Vérifier Ollama

```powershell
ollama list
```

**Attendu** :
```
NAME                ID              SIZE
deepseek-r1:14b     abc123...       8.6 GB
```

### Test 2 : Tester le Dashboard

```powershell
cd dashboard
uv run python test_dashboard.py
```

### Test 3 : Utiliser l'IA

1. Lancer le dashboard
2. Rechercher : "ETF tech"
3. Vérifier que les résultats apparaissent
4. Cliquer **"Générer une analyse IA"** (si disponible)

---

## 🐛 Dépannage

### Ollama ne démarre pas

```powershell
# Vérifier le service
ollama serve

# Tester la connexion
curl http://localhost:11434
```

### Clé API invalide

```powershell
# Vérifier que la clé est définie
echo $env:OPENAI_API_KEY      # Windows
echo $OPENAI_API_KEY          # Linux
```

### Dashboard n'utilise pas l'IA

1. Vérifier `src/config/config.yaml`
2. Vérifier que le provider est bien configuré
3. Relancer le dashboard (Ctrl+C puis relancer)

---

## 📚 Ressources

- [Ollama](https://ollama.ai) - Installation et modèles
- [OpenAI API](https://platform.openai.com) - Documentation
- [Anthropic API](https://console.anthropic.com) - Documentation
- [DSPy Framework](https://dspy-docs.vercel.app/) - Framework LLM

---

**Version** : 2.0.2
**Date** : 2026-02-20
**Status** : Configuration multi-provider ajoutée
