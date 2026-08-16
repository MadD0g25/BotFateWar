import socket
import sys

from fatewar_protocol import do_ls_login

# ============================================================================
# A ADAPTER : IP locale de ton Raspberry Pi (verifiable avec "hostname -I"
# sur le Pi) et port sur lequel gs_bot.py ecoute (5555 par defaut).
# ============================================================================
PI_HOST = "192.168.1.112"
PI_PORT = 5555

# Adresses possibles du Login Server. La premiere ("pss-login...") est celle
# utilisee depuis le debut ; la seconde ("192-243-44-11...") vient du
# fichier de config officiel de l'app (webconf.json) et sert peut-etre de
# serveur par defaut/secours - utile si la premiere est rate-limitee.
LS_SERVERS = {
    "1": ("pss-login.pss.igotgames.net", 9310),
    "2": ("192-243-44-11.ip.igotgames.net", 9310),
}


def send_to_pi(nonce, gs_host, gs_port):
    message = nonce + "," + str(gs_host) + "," + str(gs_port)
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.settimeout(5)
    try:
        sock.connect((PI_HOST, PI_PORT))
        sock.sendall(message.encode("utf-8"))
        reply = sock.recv(16)
        print("Reponse du Pi : " + reply.decode("utf-8", errors="replace"))
        return True
    except Exception as e:
        print("Erreur d'envoi au Pi : " + type(e).__name__ + ": " + str(e))
        return False
    finally:
        sock.close()


def main():
    choice = sys.argv[1] if len(sys.argv) > 1 else "1"
    if choice not in LS_SERVERS:
        print("Usage : python3 ls_login.py [1|2]")
        print("  1 = pss-login.pss.igotgames.net (par defaut)")
        print("  2 = 192-243-44-11.ip.igotgames.net (alternatif)")
        return

    ls_host, ls_port = LS_SERVERS[choice]
    print("Utilisation du serveur LS #" + choice + " : " + ls_host + ":" + str(ls_port))

    login_session, gs_host, gs_port = do_ls_login(ls_host, ls_port)

    if login_session is None:
        print("\nECHEC. Pas de login_session recupere.")
        return

    print("\nNonce obtenu : " + login_session)
    print("Envoi immediat au Pi (" + PI_HOST + ":" + str(PI_PORT) + ")...")

    ok = send_to_pi(login_session, gs_host, gs_port)

    if ok:
        print("\nEnvoye ! Le Pi devrait demarrer le bot maintenant.")
    else:
        print("\nEchec de l'envoi automatique. Valeurs a copier manuellement :")
        print("NONCE   : " + login_session)
        print("GS_HOST : " + str(gs_host))
        print("GS_PORT : " + str(gs_port))


main()
