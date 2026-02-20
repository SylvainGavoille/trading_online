"""
Quantum Trader - Script de lancement principal
"""
import sys
import argparse

if __name__ == "__main__":
    # Importer le CLI après avoir ajouté le path
    from src.cli.cli_interface import main

    # Lancer l'interface CLI
    sys.exit(main())
