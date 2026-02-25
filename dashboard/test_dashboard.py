"""
Script de test pour vérifier que le dashboard peut démarrer
"""

import sys
import io

# Configuration de l'encodage pour Windows
if sys.platform == "win32":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")


def test_imports():
    """Teste que toutes les dépendances sont installées"""
    print(">> Vérification des dépendances...")

    dependencies = {
        "streamlit": "Streamlit",
        "plotly": "Plotly",
        "pandas": "Pandas",
        "dspy": "DSPy",
        "yaml": "PyYAML",
        "cachetools": "CacheTools",
        "pydantic": "Pydantic",
    }

    missing = []
    for module, name in dependencies.items():
        try:
            __import__(module)
            print(f"[OK] {name}")
        except ImportError:
            print(f"[ERREUR] {name} - MANQUANT")
            missing.append(name)

    if missing:
        print(f"\n[ERREUR] Dépendances manquantes: {', '.join(missing)}")
        print("\nInstallez-les avec:")
        print("  uv sync")
        return False
    else:
        print("\n[OK] Toutes les dépendances sont installées !")
        return True


def test_config():
    """Teste que la configuration existe"""
    print("\n>> Vérification de la configuration...")

    import os

    # Chemin depuis dashboard/
    config_path = os.path.join("..", "src", "config", "config.yaml")

    if os.path.exists(config_path):
        print(f"[OK] Configuration trouvée: {config_path}")
        return True
    else:
        print(f"[AVERTISSEMENT] Configuration non trouvée: {config_path}")
        print("   Le dashboard fonctionnera avec les paramètres par défaut")
        return True


def test_ollama():
    """Teste si Ollama est disponible"""
    print("\n>> Vérification d'Ollama...")

    import subprocess

    try:
        result = subprocess.run(
            ["ollama", "list"], capture_output=True, text=True, timeout=5
        )

        if result.returncode == 0:
            print("[OK] Ollama est installé et fonctionne")

            if "deepseek-r1:14b" in result.stdout:
                print("[OK] Modèle deepseek-r1:14b trouvé")
            else:
                print("[AVERTISSEMENT] Modèle deepseek-r1:14b non trouvé")
                print("   Installez-le avec: ollama pull deepseek-r1:14b")

            return True
        else:
            print("[AVERTISSEMENT] Ollama n'est pas lancé")
            print("   Démarrez-le avec: ollama serve")
            return False

    except FileNotFoundError:
        print("[AVERTISSEMENT] Ollama n'est pas installé")
        print("   Téléchargez-le sur: https://ollama.ai")
        print("   (Le dashboard fonctionnera sans l'IA)")
        return False
    except Exception as e:
        print(f"[AVERTISSEMENT] Erreur lors de la vérification d'Ollama: {e}")
        return False


def main():
    """Fonction principale de test"""
    print("=" * 60)
    print("  Test du Dashboard Streamlit - Quantum Trader")
    print("=" * 60)

    all_ok = True

    # Test des imports
    if not test_imports():
        all_ok = False

    # Test de la config
    test_config()

    # Test d'Ollama
    test_ollama()

    print("\n" + "=" * 60)

    if all_ok:
        print("[OK] Tout est prêt !")
        print("\nLancez le dashboard avec:")
        print("  uv run streamlit run dashboard_app.py")
        print("\nOu utilisez le script de lancement:")
        print("  ./launch_dashboard.sh    (Linux/macOS)")
        print("  launch_dashboard.bat     (Windows)")
    else:
        print("[ERREUR] Certaines dépendances manquent")
        print("\nInstallez-les avec:")
        print("  uv sync")

    print("=" * 60)


if __name__ == "__main__":
    main()
