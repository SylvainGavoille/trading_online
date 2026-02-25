#!/usr/bin/env python3
"""Quick translation helper for remaining French strings"""

translations = {
    # Headers
    "Résumé Global": "Global Summary",
    "Répartition du Capital": "Capital Allocation",
    "Détail des Positions": "Position Details",
    "Ajouter une Position": "Add Position",
    "Supprimer une Position": "Remove Position",
    "Configuration du Profil de Risque": "Risk Profile Configuration",
    "Changer de Profil": "Change Profile",
    "Comparer les profils disponibles": "Compare available profiles",
    # Messages
    "Positions chargées depuis votre compte IBKR en temps réel": "Positions loaded from your IBKR account in real-time",
    "Positions chargées depuis la configuration locale": "Positions loaded from local configuration",
    "Position ajoutée avec succès!": "Position added successfully!",
    "Position supprimée!": "Position deleted!",
    "Veuillez entrer un symbole": "Please enter a symbol",
    "Aucune position dans votre portfolio": "No positions in your portfolio",
    "Ajoutez votre première position ci-dessous": "Add your first position below",
    "Taux d'investissement élevé pour profil Conservateur": "High investment rate for Conservative profile",
    "Profil Très Agressif : Vous pourriez investir plus de cash": "Very Aggressive Profile: You could invest more cash",
    "Allocation d'actifs recommandée": "Recommended asset allocation",
    "Instruments financiers recommandés pour ce profil": "Recommended financial instruments for this profile",
    "Instruments à éviter avec ce profil": "Instruments to avoid with this profile",
    "Ces paramètres sont modifiables ci-dessous": "These parameters can be modified below",
    "Profil changé avec succès": "Profile changed successfully",
    "Capital mis à jour": "Capital updated",
    "Mettre à jour le capital disponible": "Update available capital",
}

# Print find/replace commands
for fr, en in translations.items():
    print(f"# {fr} → {en}")
    print(f"sed -i 's/{fr}/{en}/g' dashboard_app.py")
    print()

print("\n# Or use Python to replace:")
print(
    """
import re

with open('dashboard_app.py', 'r', encoding='utf-8') as f:
    content = f.read()

for fr, en in translations.items():
    content = content.replace(fr, en)

with open('dashboard_app.py', 'w', encoding='utf-8') as f:
    f.write(content)
"""
)
