# Guide Multi-LLM pour Quantum Trader

## 🚀 Quantum Trader avec DSPy Framework

Quantum Trader utilise **DSPy**, un framework puissant qui permet d'utiliser **n'importe quel LLM** (OpenAI, Anthropic, Ollama, etc.) avec optimisation automatique des prompts.

### ✅ Avantages du système DSPy

- ✅ Support **OpenAI, Anthropic, local models** (Ollama, etc.)
- ✅ **Optimisation automatique** des prompts
- ✅ **Compilation** pour réduire les coûts
- ✅ **Fine-tuning** pour améliorer les performances
- ✅ **Structuration** meilleure du code avec Signatures et Modules
- ✅ **Debugging** plus facile avec traçage intégré
- ✅ **Type checking** avec Pydantic

## 📊 Fonctionnalités DSPy

| Fonctionnalité | Description | Avantage |
|----------------|-------------|----------|
| **Multi-LLM** | OpenAI, Anthropic, Ollama, etc. | Flexibilité totale |
| **Optimisation auto** | Bootstrap few-shot learning | Meilleure performance |
| **Compilation** | Distillation de modèles | Réduction des coûts |
| **Fine-tuning** | Training sur vos données | Performance maximale |
| **Signatures** | Input/Output typés | Code plus robuste |
| **Modules** | Composants réutilisables | Architecture propre |

## 🏗️ Architecture DSPy

Le système utilise l'architecture DSPy avec **Signatures** et **Modules** :

```python
# DSPy - Structuré et optimisable
import dspy

# 1. Définir la signature (input/output)
class TechnicalAnalysis(dspy.Signature):
    """Analyse technique des données de marché"""
    market_data: str = dspy.InputField()
    indicators: str = dspy.InputField()

    signal: str = dspy.OutputField()
    confidence: float = dspy.OutputField()

# 2. Créer le module
class TechnicalAgent(dspy.Module):
    def __init__(self):
        super().__init__()
        self.analyze = dspy.ChainOfThought(TechnicalAnalysis)

    def forward(self, market_data, indicators):
        return self.analyze(market_data=market_data, indicators=indicators)

# 3. Utiliser
agent = TechnicalAgent()
result = agent(market_data="...", indicators="...")
```

## 🚀 Utilisation

### 1. Avec OpenAI (comme Swarm)

```bash
# Configure clé API
export OPENAI_API_KEY=sk-...

# Lancer avec OpenAI
uv run python run_trader.py \
  --symbols AAPL MSFT \
  --llm openai \
  --model gpt-4o-mini \
  --mode paper
```

**Coût** : ~$3-5/jour (identique à Swarm)

### 2. Avec Anthropic Claude (Nouveau !)

```bash
# Configure clé API Claude
export ANTHROPIC_API_KEY=sk-ant-...

# Lancer avec Claude
uv run python run_trader.py \
  --symbols AAPL MSFT \
  --llm anthropic \
  --model claude-3-5-sonnet-20241022 \
  --mode paper
```

**Coût** : ~$2-4/jour (peut être moins cher selon le modèle)

### 3. Avec Ollama (Modèles Locaux - 0$ API !)

```bash
# Installer Ollama d'abord
# https://ollama.ai

# Télécharger un modèle
ollama pull llama3

# Lancer avec modèle local
uv run python run_trader.py \
  --symbols AAPL MSFT \
  --llm ollama \
  --model llama3 \
  --mode paper
```

**Coût** : **$0 en API** (seulement électricité pour votre PC)

## 🎯 Modèles Recommandés

### OpenAI

| Modèle | Coût (Input/Output) | Usage |
|--------|---------------------|-------|
| **gpt-4o-mini** | $0.15 / $0.60 par 1M tokens | ✅ **Recommandé (développement)** |
| gpt-3.5-turbo | $0.50 / $1.50 par 1M tokens | Budget |
| gpt-4o | $2.50 / $10 par 1M tokens | Production uniquement |

### Anthropic

| Modèle | Coût (Input/Output) | Usage |
|--------|---------------------|-------|
| **claude-3-5-sonnet** | $3.00 / $15 par 1M tokens | ✅ **Meilleure qualité** |
| claude-3-haiku | $0.25 / $1.25 par 1M tokens | Économique |

### Ollama (Local - Gratuit)

| Modèle | Taille | Performance |
|--------|--------|-------------|
| **llama3:8b** | 4.7GB | ✅ **Bon équilibre** |
| mistral | 4.1GB | Rapide |
| llama3:70b | 40GB | Meilleure qualité (nécessite GPU) |

## 💰 Comparaison des Coûts

### Par Jour (8h trading, 3 symboles)

| Provider | Modèle | Coût/jour | Qualité |
|----------|--------|-----------|---------|
| **Ollama** | llama3:8b | **$0** | 80% |
| OpenAI | gpt-4o-mini | ~$3.60 | 95% |
| Anthropic | claude-3-haiku | ~$2.00 | 90% |
| Anthropic | claude-3-5-sonnet | ~$24 | 100% |
| OpenAI | gpt-4o | ~$72 | 100% |

**Recommandation** :
- **Développement** : Ollama (gratuit) ou gpt-4o-mini ($3.60/jour)
- **Production** : claude-3-5-sonnet ($24/jour)

## 🔧 Configuration DSPy

### Setup OpenAI

```python
import dspy

# Configure OpenAI
lm = dspy.LM(model='openai/gpt-4o-mini')
dspy.configure(lm=lm)
```

### Setup Anthropic

```python
import dspy
import os

# Configure Anthropic
os.environ['ANTHROPIC_API_KEY'] = 'sk-ant-...'
lm = dspy.LM(model='anthropic/claude-3-5-sonnet-20241022')
dspy.configure(lm=lm)
```

### Setup Ollama (Local)

```bash
# 1. Installer Ollama
# Windows/Mac: https://ollama.ai
# Linux: curl https://ollama.ai/install.sh | sh

# 2. Télécharger modèle
ollama pull llama3

# 3. Vérifier
ollama list
```

```python
import dspy

# Configure Ollama
lm = dspy.LM(model='ollama/llama3')
dspy.configure(lm=lm)
```

## 🎓 Fonctionnalités Avancées DSPy

### 1. Optimisation Automatique

DSPy peut **optimiser automatiquement** les prompts pour améliorer les performances :

```python
from dspy.teleprompt import BootstrapFewShot

# Créer un optimiseur
optimizer = BootstrapFewShot(metric=accuracy)

# Optimiser le module
optimized_agent = optimizer.compile(
    student=technical_agent,
    trainset=training_data
)

# L'agent optimisé est maintenant plus performant !
```

### 2. Compilation pour Réduire les Coûts

DSPy peut **compiler** un gros modèle vers un petit :

```python
# Entraîner avec GPT-4o (cher mais précis)
dspy.configure(lm=dspy.LM('openai/gpt-4o'))
agent = train_agent(training_data)

# Compiler vers gpt-4o-mini (moins cher)
compiled_agent = compiler.compile(
    agent,
    target_model='openai/gpt-4o-mini'
)

# Utiliser le modèle compilé
# Même qualité que GPT-4o, coût de gpt-4o-mini !
```

### 3. Fine-Tuning

DSPy facilite le fine-tuning :

```python
# Générer des exemples de training
examples = agent.generate_training_data(historical_trades)

# Fine-tuner le modèle
finetuned_agent = dspy.finetune(
    agent,
    trainset=examples,
    model='gpt-4o-mini'
)
```

## 🔍 Debugging

DSPy offre de meilleurs outils de debugging :

```python
import dspy

# Activer le mode debug
dspy.settings.configure(trace=True)

# Inspecter les prompts générés
result = agent(market_data="...", indicators="...")

# Voir le prompt exact envoyé au LLM
print(dspy.inspect_history())

# Voir les coûts
print(dspy.get_cost())
```

## 📈 Migration de Swarm vers DSPy

### Étape 1 : Installer DSPy

```bash
uv add dspy-ai
```

### Étape 2 : Convertir les Agents

**Avant (Swarm)** :
```python
from swarm import Agent

agent = Agent(
    name="Technical Agent",
    instructions="Analyze market data..."
)
```

**Après (DSPy)** :
```python
import dspy

class TechnicalAnalysis(dspy.Signature):
    market_data: str = dspy.InputField()
    signal: str = dspy.OutputField()

class TechnicalAgent(dspy.Module):
    def __init__(self):
        super().__init__()
        self.analyze = dspy.ChainOfThought(TechnicalAnalysis)

    def forward(self, market_data):
        return self.analyze(market_data=market_data)
```

### Étape 3 : Tester

```bash
# Ancien (Swarm)
uv run python run_trader.py --symbols AAPL --mode paper

# Nouveau (DSPy)
uv run python run_trader.py --symbols AAPL --mode paper --llm openai --model gpt-4o-mini
```

## 🎯 Use Cases

### Use Case 1 : Développement Économique

```bash
# Utiliser Ollama (gratuit) pendant le développement
uv run python run_trader.py \
  --symbols AAPL \
  --llm ollama \
  --model llama3 \
  --skip-sentiment \
  --cycles 10

# Coût : $0
```

### Use Case 2 : Production avec Claude

```bash
# Meilleure qualité avec Claude en production
export ANTHROPIC_API_KEY=sk-ant-...

uv run python run_trader.py \
  --symbols AAPL MSFT GOOGL \
  --llm anthropic \
  --model claude-3-5-sonnet-20241022 \
  --mode paper

# Coût : ~$24/jour mais meilleure précision
```

### Use Case 3 : Hybride (Économique + Qualité)

```bash
# Analyse technique avec modèle local (gratuit)
# Sentiment avec Claude (payant mais précis)

# À implémenter : utiliser différents modèles par agent
```

## 📚 Ressources

- **DSPy Documentation** : https://dspy-docs.vercel.app/
- **DSPy GitHub** : https://github.com/stanfordnlp/dspy
- **Ollama** : https://ollama.ai
- **Anthropic API** : https://console.anthropic.com/

## ❓ FAQ

**Q : DSPy est-il compatible avec tous les modèles ?**
R : Oui ! OpenAI, Anthropic, Ollama, HuggingFace, et plus.

**Q : Puis-je utiliser plusieurs modèles en même temps ?**
R : Oui ! Vous pouvez configurer différents modèles par agent.

**Q : Les performances sont-elles identiques à Swarm ?**
R : Oui, voire meilleures grâce à l'optimisation automatique.

**Q : Quel est le meilleur modèle gratuit ?**
R : Llama 3 (8B) via Ollama - 0$ et performances correctes.

**Q : Dois-je réécrire tout le code ?**
R : Non, les deux versions coexistent. `run_trader.py` est la nouvelle version.

---

## 🚀 Commande Recommandée

```bash
# Développement (gratuit)
uv run python run_trader.py --symbols AAPL --llm ollama --model llama3 --mode paper

# Production (meilleure qualité)
uv run python run_trader.py --symbols AAPL MSFT --llm anthropic --model claude-3-5-sonnet-20241022 --mode paper
```

**DSPy = Plus flexible, moins cher, meilleures performances !** 🎉
