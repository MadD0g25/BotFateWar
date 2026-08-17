import socket
import sys
import time

from fatewar_core import log_event, load_state, save_state, recv_all, enable_full_debug_log
from fatewar_login import do_gs_login
from fatewar_actions_troops import (
    train_troops,
    claim_finished_training,
    decode_train_end_time,
)
from fatewar_actions_building import upgrade_building, decode_building_end_time
from fatewar_actions_rewards import (
    collect_privilege_escrow_reward,
    check_collectible_resources,
    collect_resource,
    claim_daily_signin_reward,
    check_and_claim_completed_tasks,
    scan_and_claim_tasks_in_data,
    check_and_claim_mail,
)
from fatewar_resources import (
    get_city_resources,
    RESOURCE_TYPE_CODES,
    parse_player_attributes,
    ResourceTracker,
)

# Capture tout ce qui s'affiche a l'ecran (pas seulement les evenements
# notables) dans fatewar_debug.log, avec horodatage par ligne. Utile pour
# partager une trace complete de ce que fait le bot en cas de probleme.
enable_full_debug_log()

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

# Delais de reessai selon la raison de l'echec (secondes)
RETRY_STILL_TRAINING = 60       # heure de fin inconnue, on retente prudemment
RETRY_INSUFFICIENT_RES = 300    # pas assez de ressources, ca prend du temps a s'accumuler
RETRY_GENERIC_ERROR = 60


def persist(end_times, building_end_time):
    """Sauvegarde sur disque les timestamps de fin connus, pour que le bot
    puisse reprendre intelligemment s'il plante ou redemarre avant
    l'echeance - plutot que de repartir de zero sans savoir ou en etaient
    les casernes."""
    state = {}
    for bid, et in end_times.items():
        if et:
            state["barrack:" + str(bid)] = et
    if AUTO_UPGRADE_BUILDING_ID and building_end_time:
        state["building:" + str(AUTO_UPGRADE_BUILDING_ID)] = building_end_time
    save_state(state)


def process_barrack(sock, slot, end_times, next_check, building_end_time):
    """Logique complete pour une caserne :
    1. Regarde d'abord si un entrainement est deja en cours (tentative de
       recuperation - si ca echoue avec 'still_training', on sait qu'il
       faut juste attendre).
    2. Si la caserne est libre (recuperation reussie, ou rien a recuperer),
       tente de lancer un nouvel entrainement.
    3. Si le lancement echoue par manque de ressources, note-le et attend
       plus longtemps avant de retenter (les ressources prennent du temps
       a s'accumuler, contrairement a une simple attente de fin de
       formation).
    4. Si le lancement reussit, note l'heure de fin exacte."""
    bid = slot["barrack_id"]
    print("\n--- Caserne " + str(bid) + " ---")

    claim_result = claim_finished_training(sock, bid)

    if claim_result["still_training"]:
        if claim_result["end_time"]:
            # On connait le vrai temps restant (inclus dans la reponse du
            # serveur) - pas besoin de retenter a l'aveugle toutes les 60s,
            # on programme directement la prochaine tentative au bon moment.
            end_times[bid] = claim_result["end_time"]
            next_check.pop(bid, None)
        else:
            end_times[bid] = None
            next_check[bid] = int(time.time()) + RETRY_STILL_TRAINING
        persist(end_times, building_end_time)
        return

    time.sleep(1)
    train_result = train_troops(sock, bid, slot["army_id"], slot["count"])

    if train_result["status"] == "started":
        end_times[bid] = train_result["end_time"]
        next_check.pop(bid, None)
    elif train_result["status"] == "insufficient_resources":
        end_times[bid] = None
        next_check[bid] = int(time.time()) + RETRY_INSUFFICIENT_RES
        print("Nouvelle tentative dans " + str(RETRY_INSUFFICIENT_RES) +
              "s (le temps d'accumuler des ressources).")
    else:
        end_times[bid] = None
        next_check[bid] = int(time.time()) + RETRY_GENERIC_ERROR

    persist(end_times, building_end_time)


def smart_loop(sock, end_times, next_check, building_end_time):
    """Boucle principale : garde la session vivante (keepalive toutes les
    5s), surveille les notifications de fin d'entrainement (une par
    caserne active) ET de fin d'amelioration de batiment poussees
    spontanement par le serveur, et relance automatiquement chaque cycle
    des que possible. Sauvegarde l'etat sur disque a chaque changement."""
    print("\n=== BOUCLE PRINCIPALE ===")
    print("Ctrl+C pour arreter.")
    keepalive = bytes.fromhex("04001627")  # kMsgCL2GSKeepLiveRequest = 10006
    resources = ResourceTracker()
    next_resource_print = int(time.time()) + 120

    for slot in TRAINING_SLOTS:
        bid = slot["barrack_id"]
        et = end_times.get(bid)
        if et:
            remaining = et - int(time.time())
            print("Caserne " + str(bid) + " : pret dans ~" + str(max(0, remaining)) + "s.")
        else:
            nc = next_check.get(bid)
            if nc:
                remaining = nc - int(time.time())
                print("Caserne " + str(bid) + " : prochaine verification dans ~" +
                      str(max(0, remaining)) + "s.")

    if AUTO_UPGRADE_BUILDING_ID and building_end_time:
        remaining = building_end_time - int(time.time())
        print("Batiment " + str(AUTO_UPGRADE_BUILDING_ID) + " : pret dans ~" +
              str(max(0, remaining)) + "s.")

    try:
        keepalive_count = 0
        while True:
            time.sleep(5)
            sock.sendall(keepalive)
            response, total = recv_all(sock, drain_seconds=2)
            keepalive_count += 1
            # On n'affiche/logue qu'un keepalive sur 12 (~1 fois par minute)
            # pour confirmer que la boucle tourne toujours, sans noyer le
            # fichier de log avec une ligne toutes les 5 secondes.
            if keepalive_count % 12 == 0:
                print("Keepalive OK (" + str(keepalive_count) + " envoyes depuis le debut).")

            if total > 0:
                state_changed = False

                for slot in TRAINING_SLOTS:
                    bid = slot["barrack_id"]
                    new_end = decode_train_end_time(response, bid)
                    if new_end and new_end != end_times.get(bid):
                        end_times[bid] = new_end
                        next_check.pop(bid, None)
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
                city_resources = get_city_resources(sock)
                for type_code, value in city_resources.items():
                    name = RESOURCE_TYPE_CODES.get(type_code, "Type " + str(type_code))
                    log_event("Stock actuel - " + name + " : " + str(value))
                next_resource_print = now + 120

            for slot in TRAINING_SLOTS:
                bid = slot["barrack_id"]
                et = end_times.get(bid)
                nc = next_check.get(bid)
                should_try = (et and now >= et) or (nc and now >= nc)
                if should_try:
                    process_barrack(sock, slot, end_times, next_check, building_end_time)
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

    saved_state = load_state()
    if saved_state:
        print("\nEtat precedent trouve (" + str(len(saved_state)) + " entree(s)),")
        print("reprise a partir des timestamps connus.")

    keepalive = bytes.fromhex("04001627")  # kMsgCL2GSKeepLiveRequest = 10006

    def ping():
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

    end_times = {}
    next_check = {}
    now = int(time.time())
    building_end_time = saved_state.get(
        "building:" + str(AUTO_UPGRADE_BUILDING_ID)) if AUTO_UPGRADE_BUILDING_ID else None

    for slot in TRAINING_SLOTS:
        bid = slot["barrack_id"]
        saved_et = saved_state.get("barrack:" + str(bid))
        if saved_et and saved_et > now:
            print("\n--- Caserne " + str(bid) + " : timestamp sauvegarde encore valide ---")
            end_times[bid] = saved_et
            continue
        time.sleep(1)
        process_barrack(sock, slot, end_times, next_check, building_end_time)
        ping()

    persist(end_times, building_end_time)

    time.sleep(1)
    check_and_claim_completed_tasks(sock)
    ping()

    time.sleep(1)
    check_and_claim_mail(sock)
    ping()

    # Recuperation des totaux de ressources actuels (bois/nourriture/
    # connaissances confirmes ; voir fatewar_resources.py).
    time.sleep(1)
    get_city_resources(sock)
    ping()

    if AUTO_UPGRADE_BUILDING_ID and not building_end_time:
        time.sleep(1)
        building_end_time = upgrade_building(sock, AUTO_UPGRADE_BUILDING_ID)
        persist(end_times, building_end_time)

    smart_loop(sock, end_times, next_check, building_end_time)


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
