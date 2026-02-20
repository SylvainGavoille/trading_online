import socket
from ib_insync import *

def check_port(host, port, name):
    """Vérifie si un port est ouvert"""
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.settimeout(2)
    try:
        result = sock.connect_ex((host, port))
        if result == 0:
            print(f"[OK] {name} (port {port}) est OUVERT")
            return True
        else:
            print(f"[X] {name} (port {port}) est FERMÉ")
            return False
    except Exception as e:
        print(f"[X] Erreur lors du test {name} (port {port}): {e}")
        return False
    finally:
        sock.close()

print("=" * 60)
print("DIAGNOSTIC DE CONNEXION INTERACTIVE BROKERS")
print("=" * 60)

# Test des ports communs
print("\n[1] Test des ports:")
print("-" * 60)
paper_open = check_port('127.0.0.1', 7497, 'Paper Trading (TWS)')
live_open = check_port('127.0.0.1', 7496, 'Live Trading (TWS)')
gateway_paper = check_port('127.0.0.1', 4002, 'Paper Trading (Gateway)')
gateway_live = check_port('127.0.0.1', 4001, 'Live Trading (Gateway)')

# Tentatives de connexion
print("\n[2] Tentatives de connexion:")
print("-" * 60)

ports_to_try = []
if paper_open:
    ports_to_try.append((7497, "TWS Paper Trading"))
if live_open:
    ports_to_try.append((7496, "TWS Live Trading"))
if gateway_paper:
    ports_to_try.append((4002, "Gateway Paper Trading"))
if gateway_live:
    ports_to_try.append((4001, "Gateway Live Trading"))

if not ports_to_try:
    print("[X] Aucun port IB n'est ouvert!")
    print("\n ACTIONS REQUISES:")
    print("   1. Lancez TWS ou IB Gateway")
    print("   2. Activez l'API dans les paramètres")
    print("   3. Redémarrez ce script")
else:
    for port, name in ports_to_try:
        print(f"\nTest connexion sur {name} (port {port})...")
        ib = IB()
        try:
            ib.connect('127.0.0.1', port, clientId=1, readonly=True)
            print(f"[OK] CONNEXION RÉUSSIE sur {name}!")

            # Informations
            accounts = ib.managedAccounts()
            print(f"   Compte(s): {accounts}")

            server_time = ib.reqCurrentTime()
            print(f"   Heure serveur: {server_time}")

            ib.disconnect()
            print(f"\nSUCCESS: Utilisez le port {port} pour vos scripts!")
            break

        except Exception as e:
            print(f"[X] Échec: {e}")
            ib.disconnect()

print("\n" + "=" * 60)
print(" GUIDE DE CONFIGURATION TWS/GATEWAY")
print("=" * 60)
print("""
Si aucune connexion ne fonctionne, suivez ces étapes :

1. Dans TWS ou IB Gateway :
   File → Global Configuration → API → Settings

2. Cochez ces options :
   [X] Enable ActiveX and Socket Clients
   [X] Allow connections from localhost only (ou ajoutez 127.0.0.1)

3. Vérifiez le port :
   - TWS Paper Trading : 7497
   - TWS Live Trading : 7496
   - Gateway Paper : 4002
   - Gateway Live : 4001

4. Désactivez "Read-Only API" si vous voulez passer des ordres

5. Redémarrez TWS/Gateway après les changements

6. Relancez ce script pour vérifier
""")
