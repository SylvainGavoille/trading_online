from ib_insync import *

# Connexion à IB Gateway
ib = IB()

try:
    # readonly=True pour éviter les erreurs si l'API est en lecture seule
    ib.connect('127.0.0.1', 4002, clientId=1, readonly=True)
    print("[OK] Connexion reussie !")

    # Récupérer infos compte
    account = ib.managedAccounts()
    print("Compte(s) detecte(s):", account)

    # Vérifier heure serveur
    server_time = ib.reqCurrentTime()
    print("Heure serveur:", server_time)

    print("\nINFO: API en mode lecture seule")
    print("Pour activer le trading, allez dans Gateway:")
    print("  Configure > Settings > API > Settings")
    print("  Decochez 'Read-Only API'")

except Exception as e:
    print("[X] Erreur de connexion :", e)

finally:
    ib.disconnect()
    print("\nConnexion fermee.")
