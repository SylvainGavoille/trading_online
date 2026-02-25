# Migration LITE → Version Unique (Ollama)

**Date** : 2026-02-20

## 🔄 Changement Important

La version **LITE** a été supprimée car **Ollama + DeepSeek-R1** offre désormais :
- ✅ **0$ de coût API** (comme LITE)
- ✅ **Toutes les fonctionnalités** (technique + sentiment)
- ✅ **Meilleures performances** (DSPy optimisé)

## 📦 Migration en 3 Étapes

### Étape 1 : Installer Ollama

```bash
# Windows / macOS
# Télécharger depuis https://ollama.ai

# Linux
curl -fsSL https://ollama.ai/install.sh | sh
```

### Étape 2 : Télécharger DeepSeek-R1

```bash
ollama pull deepseek-r1:14b
```

**Taille** : ~8.6 GB
**Temps** : 5-15 minutes selon votre connexion

### Étape 3 : Lancer avec la Nouvelle Commande

**Avant (LITE)** :
```bash
uv run python run_trader_lite.py --symbols AAPL MSFT --mode paper
```

**Maintenant** :
```bash
# Utilise automatiquement Ollama + DeepSeek-R1 par défaut
uv run python run_trader.py --symbols AAPL MSFT --mode paper
```

**C'est tout !** ✅

## 🆚 Comparaison

| Caractéristique | Ancienne LITE | Nouvelle Version (Ollama) |
|----------------|---------------|---------------------------|
| **Coût API** | 0$ | 0$ |
| **Analyse technique** | ✅ Python pur | ✅ DSPy optimisé |
| **Analyse sentiment** | ❌ Non | ✅ Oui |
| **Optimisation prompts** | ❌ Non | ✅ Oui (DSPy) |
| **Clé API requise** | ❌ Non | ❌ Non (local) |
| **Performance** | 95% | 100%+ |
| **Installation** | Aucune | Ollama (une fois) |

## 💰 Coûts

### Avant (LITE)

```
- API : 0$
- Infrastructure : 0$
Total : 0$
```

### Maintenant (Ollama)

```
- API : 0$ (local)
- Infrastructure : 0$
- Ollama : Gratuit
Total : 0$
```

**Coût identique, fonctionnalités supérieures !**

## 🎯 Alternatives si Vous Ne Voulez Pas Ollama

Si vous préférez ne pas installer Ollama, vous pouvez :

### Option A : OpenAI (Cloud)

```bash
export OPENAI_API_KEY=sk-...
uv run python run_trader.py --symbols AAPL --llm openai --model gpt-4o-mini --mode paper
```

**Coût** : ~$3-5/jour

### Option B : Anthropic Claude (Cloud)

```bash
export ANTHROPIC_API_KEY=sk-ant-...
uv run python run_trader.py --symbols AAPL --llm anthropic --model claude-3-5-sonnet-20241022 --mode paper
```

**Coût** : ~$24/jour

## ⚙️ Configuration Identique

Votre fichier `config.yaml` reste **100% compatible** :

```yaml
# Aucun changement nécessaire
api:
  tws_endpoint: "127.0.0.1"
  port: 4002

risk_management:
  position_limits:
    max_position_size: 100
    # ... (reste identique)
```

## 📊 Tests de Migration

### Test 1 : Vérifier Ollama

```bash
# Vérifier qu'Ollama est installé
ollama --version

# Vérifier que DeepSeek-R1 est disponible
ollama list | grep deepseek
```

### Test 2 : Test Rapide (1 cycle)

```bash
# Tester avec 1 cycle seulement
uv run python run_trader.py --symbols AAPL --mode paper --cycles 1
```

**Devrait afficher** :
```
✅ DSPy configuré avec ollama/deepseek-r1:14b
✅ Agent Technique activé
✅ Agent Sentiment activé
✅ Coût API: $0
```

### Test 3 : Test Complet

```bash
# Test normal (60s entre cycles)
uv run python run_trader.py --symbols AAPL MSFT --mode paper
```

## 🐛 Dépannage

### Problème : "Ollama not found"

**Solution** :
```bash
# Vérifier installation
which ollama  # Linux/macOS
where ollama  # Windows

# Si absent, réinstaller
# https://ollama.ai
```

### Problème : "Model deepseek-r1:14b not found"

**Solution** :
```bash
# Télécharger le modèle
ollama pull deepseek-r1:14b

# Vérifier
ollama list
```

### Problème : Performances lentes

**Solutions** :
1. **Avec GPU** : Devrait être rapide (~30-50 tokens/sec)
2. **Sans GPU** : Normal, utiliser un modèle plus petit
   ```bash
   ollama pull llama3:8b  # Plus petit, plus rapide
   uv run python run_trader.py --symbols AAPL --llm ollama --model llama3:8b --mode paper
   ```

### Problème : Manque de RAM/VRAM

**Solution** : Utiliser un modèle plus petit
```bash
# DeepSeek-R1:14b nécessite ~16GB RAM
# Alternative : Llama 3 8B (~8GB RAM)
ollama pull llama3:8b
uv run python run_trader.py --symbols AAPL --llm ollama --model llama3:8b --mode paper
```

## 📚 Documentation

- [Guide Multi-LLM complet](MULTI_LLM_GUIDE.md)
- [README actualisé](README.md)
- [Configuration](CONFIGURATION.md)

## ❓ FAQ

**Q : Puis-je continuer à utiliser la version LITE ?**
R : Non, elle a été supprimée. Mais Ollama offre 0$ API comme LITE avec toutes les fonctionnalités en plus.

**Q : Dois-je modifier mon code ou ma config ?**
R : Non ! Tout est compatible. Seule la commande de lancement change.

**Q : Ollama est-il aussi rapide que LITE ?**
R : Avec GPU : Oui, similaire ou plus rapide. Sans GPU : Peut être plus lent, utiliser llama3:8b.

**Q : Mes trades/stratégies seront-ils différents ?**
R : Les signaux techniques restent identiques. En plus, vous avez maintenant l'analyse de sentiment.

**Q : Et si je n'ai pas de GPU ?**
R : Ollama fonctionne sur CPU (plus lent) ou utilisez OpenAI/Claude (cloud).

**Q : Combien de VRAM/RAM nécessaire ?**
R :
- DeepSeek-R1:14b → ~16GB RAM ou 10GB VRAM
- Llama3:8b → ~8GB RAM ou 5GB VRAM

**Q : Puis-je revenir à l'ancienne version LITE ?**
R : Oui, via git :
```bash
git log --all --oneline | grep -i "lite"
git checkout <commit-avant-suppression>
```
Mais ce n'est pas recommandé.

## ✅ Checklist de Migration

- [ ] Ollama installé
- [ ] DeepSeek-R1:14b téléchargé
- [ ] Test avec `--cycles 1` réussi
- [ ] Configuration `config.yaml` vérifiée
- [ ] Ancienne commande `run_trader_lite.py` remplacée
- [ ] Test complet en paper trading réussi

## 🎉 Avantages de la Migration

✅ **0$ API** (identique à LITE)
✅ **Analyse sentiment** (nouveau)
✅ **DSPy optimisé** (meilleure performance)
✅ **Local** (aucune donnée au cloud)
✅ **Aucune limite** (utilisez autant que vous voulez)
✅ **Fine-tuning possible** (avec DSPy)

---

**Besoin d'aide ?** Consultez le [README](README.md) ou [MULTI_LLM_GUIDE.md](MULTI_LLM_GUIDE.md)

**Statut** : Migration recommandée ✅
