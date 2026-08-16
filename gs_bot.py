import socket
import sys
import time

from fatewar_protocol import (
    do_gs_login,
    collect_privilege_escrow_reward,
    check_collectible_resources,
    collect_resource,
    train_troops,
    claim_daily_signin_reward,
    check_and_claim_completed_tasks,
    heartbeat_loop,
)

LISTEN_PORT = 5555


def run_bot(gs_host, gs_port, nonce):
    sock = do_gs_login(gs_host, gs_port, nonce)

    if sock is None:
        print("\nImpossible d'ouvrir la session GS.")
        return

    collect_privilege_escrow_reward(sock)

    time.sleep(5)
    collectibles = check_collectible_resources(sock)
    for info in collectibles:
        if info.get("store", 0) > 0:
            time.sleep(5)
            collect_resource(sock, info["type"])

    # Entrainement de troupes (army_id/barrack_id trouves par capture
    # reseau lors d'un entrainement manuel - a adapter si tu changes de
    # caserne ou de type de troupe).
    time.sleep(5)
    train_troops(sock, barrack_id=1007, army_id=1201, count=50)

    # Recompense de connexion quotidienne : desactivee pour l'instant, pas
    # encore confirmee fonctionnelle (l'activite semble ne pas etre active
    # en ce moment, ou le "day" est incorrect - voir fatewar_protocol.py).
    # L'attente supplementaire semblait aussi contribuer a des coupures de
    # connexion prematurees. A reactiver une fois debuggee avec une vraie
    # capture reseau d'un sign-in reussi.
    # time.sleep(5)
    # claim_daily_signin_reward(sock, day=1)

    time.sleep(3)
    check_and_claim_completed_tasks(sock)

    heartbeat_loop(sock, interval_seconds=5)


def main():
    server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    server.bind(("0.0.0.0", LISTEN_PORT))
    server.listen(1)
    print("En attente du nonce sur le port " + str(LISTEN_PORT) + "...")
    print("(lance ls_login.py sur ton iPhone maintenant)")

    conn, addr = server.accept()
    print("Connexion recue de " + str(addr))
    data = conn.recv(4096).decode("utf-8").strip()
    conn.sendall(b"OK")
    conn.close()
    server.close()

    parts = data.split(",")
    if len(parts) != 3:
        print("Donnees recues invalides : " + data)
        return

    nonce, gs_host, gs_port = parts
    gs_port = int(gs_port)

    print("\nNonce recu : " + nonce)
    print("GS : " + gs_host + ":" + str(gs_port))
    print("Lancement immediat du bot...\n")

    run_bot(gs_host, gs_port, nonce)


main()
