# Configuration de la Clé API OpenAI

## ⚠️ Requis pour le Fonctionnement

Le système Quantum Trader utilise **OpenAI Swarm** pour coordonner les agents. Une **clé API OpenAI** est **obligatoire**.

## 📝 Étapes de Configuration

### 1. Obtenir une Clé API OpenAI

1. Créer un compte sur https://platform.openai.com
2. Aller dans **API Keys** : https://platform.openai.com/api-keys
3. Cliquer sur **"Create new secret key"**
4. Copier la clé (format : `sk-...`)
5. **⚠️ IMPORTANT** : Sauvegardez-la immédiatement, elle ne sera plus visible !

### 2. Configurer la Clé Localement

**Option 1 : Fichier .env (Recommandé)**

```bash
# Copier le template
cp .env.example .env

# Éditer le fichier .env
nano .env
# ou
code .env
```

Dans `.env`, remplacer :
```bash
OPENAI_API_KEY=sk-your-api-key-here
```

Par votre vraie clé :
```bash
OPENAI_API_KEY=sk-proj-abc123xyz...
```

**Option 2 : Variable d'Environnement Windows**

```powershell
# PowerShell (temporaire, session actuelle)
$env:OPENAI_API_KEY = "sk-proj-abc123xyz..."

# PowerShell (permanent, utilisateur)
[System.Environment]::SetEnvironmentVariable('OPENAI_API_KEY', 'sk-proj-abc123xyz...', 'User')
```

**Option 3 : Variable d'Environnement Bash (Git Bash)**

```bash
# Temporaire (session actuelle)
export OPENAI_API_KEY="sk-proj-abc123xyz..."

# Permanent (ajouter à ~/.bashrc)
echo 'export OPENAI_API_KEY="sk-proj-abc123xyz..."' >> ~/.bashrc
source ~/.bashrc
```

### 3. Vérifier la Configuration

```bash
# PowerShell
echo $env:OPENAI_API_KEY

# Bash
echo $OPENAI_API_KEY
```

Devrait afficher votre clé (commençant par `sk-...`).

### 4. Installer python-dotenv (Si vous utilisez .env)

```bash
# Avec uv
uv add python-dotenv
```

### 5. Modifier le Code pour Charger .env

Créer un fichier `src/config/env_loader.py` :

```python
import os
from pathlib import Path
from dotenv import load_dotenv

# Charger .env depuis la racine du projet
env_path = Path(__file__).parent.parent.parent / '.env'
load_dotenv(dotenv_path=env_path)

def get_openai_key():
    """Récupère la clé API OpenAI"""
    key = os.getenv('OPENAI_API_KEY')
    if not key:
        raise ValueError(
            "OPENAI_API_KEY non trouvée ! "
            "Configurez-la dans .env ou en variable d'environnement."
        )
    return key
```

Puis modifier `src/trading/trading_agents.py` :

```python
from swarm import Swarm, Agent
from src.config.env_loader import get_openai_key
import os

class TradingSwarm:
    def __init__(self, config: dict):
        self.config = config
        self.logger = logging.getLogger(__name__)

        # S'assurer que la clé API est configurée
        os.environ['OPENAI_API_KEY'] = get_openai_key()

        self.client = Swarm()
        # ... reste du code
```

## 💰 Coûts Estimés

### Modèles Recommandés

| Modèle | Coût Input | Coût Output | Recommandation |
|--------|------------|-------------|----------------|
| **gpt-4o** | $2.50 / 1M tokens | $10 / 1M tokens | Production |
| **gpt-4o-mini** | $0.15 / 1M tokens | $0.60 / 1M tokens | **Recommandé (développement)** |
| **gpt-3.5-turbo** | $0.50 / 1M tokens | $1.50 / 1M tokens | Budget |

### Estimation par Trade

Un cycle de trading complet (analyse + décision) utilise environ :
- **2,000-5,000 tokens** par symbole
- Avec 3 symboles : ~10,000 tokens par cycle (60s)

**Coût horaire (gpt-4o-mini)** :
- 60 cycles/heure × 10k tokens = 600k tokens/heure
- Input : ~$0.09/heure
- Output : ~$0.36/heure
- **Total : ~$0.45/heure** ⚡ Très abordable !

**Coût journalier (8h de trading)** :
- ~$3.60/jour avec gpt-4o-mini
- ~$72/jour avec gpt-4o (non recommandé pour débuter)

### Réduire les Coûts

1. **Utiliser gpt-4o-mini** (15x moins cher que gpt-4o)
2. **Augmenter update_interval** dans config.yaml :
   ```yaml
   agent_system:
     update_interval: 120  # Au lieu de 60s
   ```
3. **Limiter les symboles** : Trader 1-2 symboles au lieu de 5
4. **Mode paper trading** : Pas de frais IB, juste API OpenAI

## 🔒 Sécurité

### ✅ FAIRE

- ✅ Utiliser un fichier `.env` (ignoré par git)
- ✅ Limiter les permissions de la clé (lecture seule si possible)
- ✅ Monitorer l'utilisation sur https://platform.openai.com/usage
- ✅ Définir des limites de dépenses mensuelles sur OpenAI

### ❌ NE JAMAIS FAIRE

- ❌ Commit `.env` dans git
- ❌ Partager votre clé API
- ❌ Hard-coder la clé dans le code
- ❌ Pusher la clé sur GitHub

## 🧪 Tester la Configuration

Créer un fichier `test_openai_key.py` :

```python
import os
from openai import OpenAI

# Tester la clé
def test_api_key():
    api_key = os.getenv('OPENAI_API_KEY')

    if not api_key:
        print("❌ OPENAI_API_KEY non trouvée !")
        print("Configurez-la dans .env ou en variable d'environnement")
        return False

    print(f"✅ Clé trouvée : {api_key[:10]}...{api_key[-4:]}")

    try:
        client = OpenAI(api_key=api_key)
        # Test simple
        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[{"role": "user", "content": "Say 'API works!'"}],
            max_tokens=10
        )
        print(f"✅ API fonctionne : {response.choices[0].message.content}")
        return True
    except Exception as e:
        print(f"❌ Erreur API : {e}")
        return False

if __name__ == "__main__":
    test_api_key()
```

Exécuter :
```bash
uv run python test_openai_key.py
```

## 📊 Monitoring des Coûts

1. **Dashboard OpenAI** : https://platform.openai.com/usage
2. **Limites de dépenses** : https://platform.openai.com/settings/organization/billing/limits
3. **Alertes email** : Configurer dans les settings

### Définir une Limite Mensuelle

1. Aller sur https://platform.openai.com/settings/organization/billing/limits
2. Définir "Hard limit" (ex: $50/mois)
3. Définir "Soft limit" pour alertes (ex: $30/mois)

## 🚀 Modèle Recommandé pour Débuter

Ajouter dans `.env` :

```bash
OPENAI_API_KEY=sk-your-key-here
OPENAI_MODEL=gpt-4o-mini  # Moins cher, parfait pour débuter
```

Puis modifier `src/trading/agents/agent_manager.py` pour utiliser cette variable.

## ❓ FAQ

**Q : Puis-je utiliser une autre API (Claude, Llama, etc.) ?**
R : Non, Swarm est spécifique à OpenAI. Il faudrait réécrire le système d'agents.

**Q : Combien coûte le paper trading ?**
R : Seulement l'API OpenAI (~$3-5/jour avec gpt-4o-mini). IB paper trading est gratuit.

**Q : Puis-je tester sans clé API ?**
R : Non, les agents nécessitent l'API pour fonctionner. Mais vous pouvez tester les indicateurs techniques sans agents.

**Q : La clé est-elle partagée avec d'autres ?**
R : Non, votre clé est personnelle et privée. Jamais partagée.

---

**Configuration terminée ?** Testez avec :
```bash
uv run python test_openai_key.py
uv run python quick_start.py
```
