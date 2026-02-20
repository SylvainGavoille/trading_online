"""
Test de la configuration de la clé API OpenAI
"""
import os
from pathlib import Path

def test_api_key():
    """Teste si la clé API OpenAI est configurée"""
    print("=" * 60)
    print("TEST CONFIGURATION CLE API OPENAI")
    print("=" * 60)

    # Vérifier la clé
    api_key = os.getenv('OPENAI_API_KEY')

    if not api_key:
        print("\n[X] OPENAI_API_KEY non trouvee !")
        print("\nSOLUTIONS:")
        print("1. Creer un fichier .env a la racine du projet")
        print("2. Ajouter: OPENAI_API_KEY=sk-votre-cle-ici")
        print("3. Ou definir en variable d'environnement:")
        print("   export OPENAI_API_KEY='sk-votre-cle-ici'  # Bash")
        print("   $env:OPENAI_API_KEY = 'sk-votre-cle-ici'  # PowerShell")
        print("\nVoir SETUP_API_KEY.md pour plus de details")
        return False

    # Masquer une partie de la clé pour la sécurité
    masked_key = f"{api_key[:10]}...{api_key[-4:]}"
    print(f"\n[OK] Cle trouvee : {masked_key}")
    print(f"[OK] Longueur : {len(api_key)} caracteres")

    # Vérifier le format
    if not api_key.startswith('sk-'):
        print("\n[!] AVERTISSEMENT: La cle ne commence pas par 'sk-'")
        print("    Format attendu: sk-proj-... ou sk-...")

    # Test de connexion à l'API
    print("\n[*] Test de connexion a l'API OpenAI...")

    try:
        from openai import OpenAI

        client = OpenAI(api_key=api_key)

        # Test simple avec gpt-4o-mini (le moins cher)
        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[{"role": "user", "content": "Respond with just: OK"}],
            max_tokens=5
        )

        result = response.choices[0].message.content.strip()
        print(f"[OK] Reponse API : {result}")
        print(f"[OK] Modele utilise : {response.model}")
        print(f"[OK] Tokens utilises : {response.usage.total_tokens}")

        # Coût estimé
        cost = response.usage.total_tokens * 0.00000015  # gpt-4o-mini rate
        print(f"[OK] Cout du test : ~${cost:.6f}")

        print("\n" + "=" * 60)
        print("SUCCES ! La cle API fonctionne correctement")
        print("=" * 60)
        print("\nVous pouvez maintenant lancer le systeme:")
        print("  uv run python quick_start.py")
        print("  uv run python run_trader.py --symbols AAPL --mode paper")

        return True

    except ImportError:
        print("[X] Module 'openai' non installe")
        print("    Installez avec: uv add openai")
        return False

    except Exception as e:
        print(f"[X] Erreur lors du test API : {e}")
        print("\nVerifiez:")
        print("1. Que la cle est valide")
        print("2. Que vous avez des credits sur votre compte OpenAI")
        print("3. Dashboard: https://platform.openai.com/usage")
        return False

if __name__ == "__main__":
    # Essayer de charger .env si disponible
    try:
        from dotenv import load_dotenv
        env_path = Path(__file__).parent / '.env'
        if env_path.exists():
            load_dotenv(dotenv_path=env_path)
            print(f"[*] Fichier .env charge depuis : {env_path}")
    except ImportError:
        print("[*] python-dotenv non installe, utilisation variables environnement")
    except Exception as e:
        print(f"[!] Erreur chargement .env : {e}")

    test_api_key()
