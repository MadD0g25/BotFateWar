import socket
import sys
import time

from fatewar_protocol import (
    do_gs_login,
    collect_privilege_escrow_reward,
    check_collectible_resources,
    collect_resource,
    train_troops,
    claim_finished_training,
    claim_daily_signin_reward,
    check_and_claim_completed_tasks,
    scan_and_claim_tasks_in_data,
    check_and_claim_mail,
    decode_train_end_time,
    decode_building_end_time,
    upgrade_building,
    parse_player_attributes,
    ResourceTracker,
    load_state,
    save_state,
    recv_all,
)

LISTEN_PORT = 5555

# Liste des casernes a faire tourner en parallele, chacune avec son propre
# type de troupe et sa propre quantite. Trouvees par capture reseau
# (kMsgCL2GSTrainRequest, type 10402) pendant un entrainement manuel de
# chaque type dans l'app - voir README.md pour la procedure complete.
# Ajoute/retire des entrees selon tes propres casernes.
TRAINING_SLOTS = [
    {"barrack_id": 1005, "army_id": 1001, "count": 100},  # ex: lanceurs de haches
    {"barrack_id": 8,    "army_id": 1101, "count": 50},   # ex: berserkers
    {"barrack_id": 1007, "army_id": 1201, "count": 100},  # ex: cavalerie
]

# Amelioration automatique de batiment : optionnel, desactive par defaut
# (mettre a None pour desactiver). building_id est propre a CHAQUE COMPTE
# (voir README.md, section "Capturer ton building_id").
AUTO_UPGRADE_BUILDING_ID = None
# AUTO_UPGRADE_BUILDING_ID = 1009


def persist(end_times, building_end_time):
    """Sauvegarde sur disque les timestamps de fin connus, pour que le bot
    puisse reprendre intelligemment s'il plante ou redemarre avant
    l'echeance - plutot que de repartir de zero sans savoir ou en etaient
    les casernes (etat 'heure inconnue')."""
    state = {}
    for bid, et in end_times.items():
        if et:
            state["barrack:" + str(bid)] = et
    if AUTO_UPGRADE_BUILDING_ID and building_end_time:
        state["building:" + str(AUTO_UPGRADE_BUILDING_ID)] = building_end_time
    save_state(state)


def try_claim_and_retrain(sock, slot, end_times, building_end_time):
    """Tente de recuperer les troupes d'une caserne et relance un
    entrainement si elle est libre. Met a jour end_times[barrack_id] et
    persiste immediatement sur disque."""
    barrack_id = slot["barrack_id"]
    print("\nTentative de recuperation - caserne " + str(barrack_id) + "...")
    if claim_finished_training(sock, barrack_id):
        time.sleep(2)
        end_times[barrack_id] = train_troops(
            sock, barrack_id, slot["army_id"], slot["count"])
    else:
        end_times[barrack_id] = int(time.time()) + 30
    persist(end_times, building_end_time)


def smart_loop(sock, end_times, building_end_time):
    """Boucle principale : garde la session vivante (keepalive toutes les
    5s), surveille les notifications de fin d'entrainement (une par
    caserne active) ET de fin d'amelioration de batiment poussees
    spontanement par le serveur, et relance automatiquement chaque cycle
    des que possible. Sauvegarde l'etat sur disque a chaque changement."""
    print("\n=== BOUCLE PRINCIPALE ===")
    print("Ctrl+C pour arreter.")
    keepalive = bytes.fromhex("04001627")  # kMsgCL2GSKeepLiveRequest = 10006
    blind_retry_interval = 60
    next_blind_retry = {slot["barrack_id"]: int(time.time()) + blind_retry_interval
                         for slot in TRAINING_SLOTS}
    resources = ResourceTracker()
    next_resource_print = int(time.time()) + 120

    for slot in TRAINING_SLOTS:
        bid = slot["barrack_id"]
        et = end_times.get(bid)
        if et:
            remaining = et - int(time.time())
            print("Caserne " + str(bid) + " : pret dans ~" + str(max(0, remaining)) + "s.")
        else:
            print("Caserne " + str(bid) + " : heure inconnue, nouvelle tentative " +
                  "toutes les " + str(blind_retry_interval) + "s.")

    if AUTO_UPGRADE_BUILDING_ID and building_end_time:
        remaining = building_end_time - int(time.time())
        print("Batiment " + str(AUTO_UPGRADE_BUILDING_ID) + " : pret dans ~" +
              str(max(0, remaining)) + "s.")

    try:
        while True:
            time.sleep(5)
            sock.sendall(keepalive)
            response, total = recv_all(sock, drain_seconds=2)
            print("Keepalive envoye (" + str(total) + " octets recus).")

            if total > 0:
                state_changed = False

                for slot in TRAINING_SLOTS:
                    bid = slot["barrack_id"]
                    new_end = decode_train_end_time(response, bid)
                    if new_end and new_end != end_times.get(bid):
                        end_times[bid] = new_end
                        state_changed = True
                        remaining = new_end - int(time.time())
                        print("Notification recue (caserne " + str(bid) +
                              ") : pret dans ~" + str(max(0, remaining)) + "s.")

                if AUTO_UPGRADE_BUILDING_ID:
                    new_building_end = decode_building_end_time(
                        response, AUTO_UPGRADE_BUILDING_ID)
                    if new_building_end and new_building_end != building_end_time:
                        building_end_time = new_building_end
                        state_changed = True
                        remaining = building_end_time - int(time.time())
                        print("Notification recue : batiment pret dans ~" +
                              str(max(0, remaining)) + "s.")

                if state_changed:
                    persist(end_times, building_end_time)

                scan_and_claim_tasks_in_data(sock, response)

                attrs = parse_player_attributes(response)
                if attrs:
                    resources.update(attrs)

            now = int(time.time())

            if now >= next_resource_print:
                resources.print_summary()
                next_resource_print = now + 120

            for slot in TRAINING_SLOTS:
                bid = slot["barrack_id"]
                et = end_times.get(bid)
                should_try = (et and now >= et) or \
                             (et is None and now >= next_blind_retry[bid])
                if should_try:
                    try_claim_and_retrain(sock, slot, end_times, building_end_time)
                    if end_times.get(bid) is None:
                        next_blind_retry[bid] = int(time.time()) + blind_retry_interval
                    time.sleep(1)

            if AUTO_UPGRADE_BUILDING_ID and building_end_time and now >= building_end_time:
                print("\nAmelioration de batiment terminee, lancement du niveau suivant...")
                time.sleep(1)
                building_end_time = upgrade_building(sock, AUTO_UPGRADE_BUILDING_ID)
                if not building_end_time:
                    building_end_time = int(time.time()) + 60
                persist(end_times, building_end_time)

    except KeyboardInterrupt:
        print("\nArret demande.")
    except ConnectionResetError:
        print("\nConnexion perdue (reset).")
    except BrokenPipeError:
        print("\nConnexion perdue (broken pipe).")
    except Exception as e:
        print("\nErreur : " + type(e).__name__ + ": " + str(e))
    finally:
        sock.close()


def run_bot(gs_host, gs_port, nonce):
    sock = do_gs_login(gs_host, gs_port, nonce)

    if sock is None:
        print("\nImpossible d'ouvrir la session GS.")
        return

    # Chargement de l'etat sauvegarde lors d'une precedente execution -
    # permet de reprendre sans repartir de zero si le bot a plante ou a
    # ete redemarre avant qu'un entrainement/amelioration ne se termine.
    saved_state = load_state()
    if saved_state:
        print("\nEtat precedent trouve (" + str(len(saved_state)) + " entree(s)),")
        print("reprise a partir des timestamps connus.")

    keepalive = bytes.fromhex("04001627")  # kMsgCL2GSKeepLiveRequest = 10006

    def ping():
        """Envoie un keepalive rapide pour eviter que la session n'expire
        pendant la longue sequence d'actions de demarrage."""
        sock.sendall(keepalive)
        recv_all(sock, drain_seconds=1)

    collect_privilege_escrow_reward(sock)
    ping()

    time.sleep(1)
    collectibles = check_collectible_resources(sock)
    for info in collectibles:
        if info.get("store", 0) > 0:
            time.sleep(1)
            collect_resource(sock, info["type"])
    ping()

    # Recuperation + relance pour chaque caserne suivie. Si la recuperation
    # echoue (caserne encore occupee) et qu'on a un timestamp sauvegarde
    # d'une session precedente pour cette caserne, on le reutilise au lieu
    # de marquer l'heure comme inconnue.
    end_times = {}
    building_end_time = saved_state.get(
        "building:" + str(AUTO_UPGRADE_BUILDING_ID)) if AUTO_UPGRADE_BUILDING_ID else None

    for slot in TRAINING_SLOTS:
        time.sleep(1)
        bid = slot["barrack_id"]
        print("\n--- Caserne " + str(bid) + " ---")
        ready = claim_finished_training(sock, bid)
        time.sleep(1)
        if ready:
            end_times[bid] = train_troops(sock, bid, slot["army_id"], slot["count"])
        else:
            saved_et = saved_state.get("barrack:" + str(bid))
            if saved_et:
                print("Caserne occupee - reprise du timestamp sauvegarde (" +
                      str(saved_et) + ").")
                end_times[bid] = saved_et
            else:
                print("Caserne occupee - la boucle principale reessaiera plus tard.")
                end_times[bid] = None
        ping()

    persist(end_times, building_end_time)

    # Recompense de connexion quotidienne : desactivee pour l'instant, pas
    # encore confirmee fonctionnelle - voir fatewar_protocol.py.
    # time.sleep(1)
    # claim_daily_signin_reward(sock, day=1)

    time.sleep(1)
    check_and_claim_completed_tasks(sock)
    ping()

    time.sleep(1)
    check_and_claim_mail(sock)
    ping()

    if AUTO_UPGRADE_BUILDING_ID and not building_end_time:
        time.sleep(1)
        building_end_time = upgrade_building(sock, AUTO_UPGRADE_BUILDING_ID)
        persist(end_times, building_end_time)

    smart_loop(sock, end_times, building_end_time)


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
