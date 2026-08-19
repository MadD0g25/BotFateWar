import socket
import sys
import time

from bot_config import (
    LISTEN_PORT,
    TRAINING_SLOTS,
    AUTO_UPGRADE_ALL_BUILDINGS,
    MAX_CONCURRENT_BUILDING_UPGRADES,
    EXCLUDED_BUILDING_IDS,
    ENABLE_GUILD_FEATURES,
    GUILD_TECH_ID,
    GUILD_TECH_LEVEL,
    GUILD_TECH_DONATE_TIMES,
    AUTO_ATTACK_MONSTERS,
    MONSTER_ATTACK_LEVEL,
    BATTLE_HERO1,
    BATTLE_HERO2,
    BATTLE_TROOPS,
    PERSONAL_TECH_ID,
    CLAIM_CHAPTER_AWARD,
    HERO_TALENT_IDS,
    DAILY_TASK_IDS,
    CITIZEN_COLLECT_IDS,
    FARM_PEN_IDS,
    TD_CITY_AREA_ID,
    TD_CITY_STARTING_GRID,
    TD_CITY_MAX_GRID,
    RETRY_STILL_TRAINING,
    RETRY_INSUFFICIENT_RES,
    RETRY_GENERIC_ERROR,
)
from fatewar_core import log_event, load_state, save_state, recv_all, enable_full_debug_log
from fatewar_login import do_gs_login
from fatewar_actions_troops import (
    train_troops,
    train_max_troops,
    claim_finished_training,
    decode_train_end_time,
)
from fatewar_actions_building import upgrade_building
from fatewar_actions_rewards import (
    check_collectible_resources,
    collect_resource,
    claim_daily_signin_reward,
    check_and_claim_completed_tasks,
    scan_and_claim_tasks_in_data,
    check_and_claim_mail,
    check_and_collect_guild_resource,
    help_guild_members,
    donate_guild_tech,
    collect_citizen_settle,
    claim_all_guild_gifts,
    claim_all_daily_gifts,
    harvest_farm,
)
from fatewar_resources import (
    get_city_resources,
    get_city_buildings,
    get_city_buildings_and_queue,
    RESOURCE_TYPE_CODES,
    TYPE_CODE_TO_CURRENCY,
    parse_player_attributes,
    ResourceTracker,
)
from fatewar_actions_tdcity import explore_next_td_grid
from fatewar_actions_misc import (
    start_research,
    claim_research,
    claim_chapter_award,
    claim_daily_task_award,
    upgrade_hero_talent_recommended,
)
from fatewar_actions_battle import search_and_attack_corrupted

# Capture tout ce qui s'affiche a l'ecran (pas seulement les evenements
# notables) dans fatewar_debug.log, avec horodatage par ligne. Utile pour
# partager une trace complete de ce que fait le bot en cas de probleme.
enable_full_debug_log()

BUILDING_STATUS_UPGRADING = 1  # kBuildingStatus_Upgrading (deja en cours)
BUILDING_STATUS_NORMAL = 3  # kBuildingStatus_Normal (libre, ameliorable)

# Batiments temporairement mis de cote apres un echec "structurel" (pas
# juste manque de ressources) - evite qu'un batiment bloque en boucle ne
# monopolise indefiniment l'unique place disponible a chaque cycle.
# {building_id: timestamp jusqu'auquel on l'ignore}
_building_cooldowns = {}
BUILDING_COOLDOWN_SECONDS = 1800  # 30 minutes


def persist(end_times):
    """Sauvegarde sur disque les timestamps de fin connus, pour que le bot
    puisse reprendre intelligemment s'il plante ou redemarre avant
    l'echeance - plutot que de repartir de zero sans savoir ou en etaient
    les casernes."""
    state = load_state()
    for bid, et in end_times.items():
        if et:
            state["barrack:" + str(bid)] = et
    save_state(state)


def persist_td_city_grid(grid):
    """Sauvegarde la case TDCity en cours, independamment du reste de
    l'etat (evolue a un rythme different des casernes/batiments)."""
    state = load_state()
    state["td_city_grid:" + str(TD_CITY_AREA_ID)] = grid
    save_state(state)


def process_barrack(sock, slot, end_times, next_check):
    """Logique complete pour une caserne :
    1. Regarde d'abord si un entrainement est deja en cours (tentative de
       recuperation - si ca echoue avec 'still_training', on sait qu'il
       faut juste attendre).
    2. Si la caserne est libre (recuperation reussie, ou rien a recuperer),
       tente de lancer un nouvel entrainement.
    3. Si le lancement echoue par manque de ressources, note-le et attend
       plus longtemps avant de retenter.
    4. Si le lancement reussit, note l'heure de fin exacte."""
    bid = slot["barrack_id"]
    print("\n--- Caserne " + str(bid) + " ---")

    claim_result = claim_finished_training(sock, bid)

    if claim_result["still_training"]:
        if claim_result["end_time"]:
            end_times[bid] = claim_result["end_time"]
            next_check.pop(bid, None)
        else:
            end_times[bid] = None
            next_check[bid] = int(time.time()) + RETRY_STILL_TRAINING
        persist(end_times)
        return

    time.sleep(1)
    if slot["count"] == "max":
        # Recupere le niveau de la caserne et les ressources actuelles
        # pour calculer directement la quantite max (voir
        # fatewar_troop_data.py) au lieu de tatonner par essais reseau -
        # si l'un des deux echoue, train_max_troops retombe automatiquement
        # sur le tatonnement classique.
        barrack_level = None
        available_resources = None
        try:
            buildings = get_city_buildings(sock)
            for b in buildings:
                if b.get("id") == bid:
                    barrack_level = b.get("level")
                    break
            time.sleep(1)
            city_resources = get_city_resources(sock)
            available_resources = {
                TYPE_CODE_TO_CURRENCY[tc]: val
                for tc, val in city_resources.items()
                if tc in TYPE_CODE_TO_CURRENCY
            }
        except Exception:
            pass  # en cas de souci, train_max_troops utilisera le tatonnement
        train_result = train_max_troops(sock, bid, slot["army_id"],
                                         barrack_level=barrack_level,
                                         available_resources=available_resources)
    else:
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

    persist(end_times)


def upgrade_all_available_buildings(sock):
    """Liste tous les batiments de la ville ET les vraies heures de fin
    des constructions en cours (en un seul appel reseau). Compte combien
    de files sont deja occupees, et ne lance de nouvelles ameliorations
    que sur les places encore libres, dans la limite de
    MAX_CONCURRENT_BUILDING_UPGRADES.

    Retourne le timestamp du prochain moment ou il faut revérifier - soit
    la fin la plus proche parmi les constructions en cours, soit un delai
    court par defaut si on ne sait rien (aucune construction en cours et
    aucun batiment eligible pour l'instant, ex: toutes en cooldown)."""
    if not AUTO_UPGRADE_ALL_BUILDINGS:
        return None

    print("\n=== AMELIORATION AUTOMATIQUE : verification de tous les batiments ===")
    buildings, queue_end_times = get_city_buildings_and_queue(sock)

    upgrading_count = sum(1 for b in buildings if b.get("status") == BUILDING_STATUS_UPGRADING)
    available_slots = MAX_CONCURRENT_BUILDING_UPGRADES - upgrading_count

    print(str(upgrading_count) + "/" + str(MAX_CONCURRENT_BUILDING_UPGRADES) +
          " file(s) de construction deja occupee(s).")

    now = int(time.time())
    next_check_time = None

    if available_slots <= 0:
        # Toutes les files sont pleines - le prochain moment utile est
        # exactement la fin la plus proche parmi celles en cours.
        if queue_end_times:
            next_check_time = min(queue_end_times.values())
            print("Aucune place libre - prochaine verification programmee " +
                  "a la fin d'une construction (dans " +
                  str(max(0, next_check_time - now)) + "s).")
        else:
            next_check_time = now + 60
            print("Aucune place libre, mais heure de fin inconnue - " +
                  "nouvelle verification dans 60s par securite.")
        return next_check_time

    eligible = [b for b in buildings
                if b.get("status") == BUILDING_STATUS_NORMAL
                and b.get("id") not in EXCLUDED_BUILDING_IDS
                and _building_cooldowns.get(b.get("id"), 0) <= now]

    if not eligible:
        print("Aucun batiment libre a ameliorer pour l'instant.")
        # Rien d'eligible maintenant (tout en cooldown ?) - retente dans
        # un moment raisonnable, ou a la fin d'une construction en cours
        # si il y en a une (une place se liberera peut-etre plus vite).
        if queue_end_times:
            next_check_time = min(queue_end_times.values())
        else:
            candidates = [t for t in _building_cooldowns.values() if t > now]
            next_check_time = min(candidates) if candidates else now + 300
        return next_check_time

    to_attempt = eligible[:available_slots]
    print(str(len(to_attempt)) + " batiment(s) vont etre tentes (" +
          str(available_slots) + " place(s) disponible(s), " +
          str(len(eligible)) + " batiment(s) eligible(s) au total).")

    keepalive = bytes.fromhex("04001627")  # kMsgCL2GSKeepLiveRequest = 10006
    for b in to_attempt:
        time.sleep(1)
        result = upgrade_building(sock, b["id"])
        if result["status"] == "not_eligible":
            _building_cooldowns[b["id"]] = now + BUILDING_COOLDOWN_SECONDS
            print("Batiment #" + str(b["id"]) + " mis de cote pour " +
                  str(BUILDING_COOLDOWN_SECONDS // 60) + " minutes.")
        elif result["status"] == "started" and result.get("end_time"):
            queue_end_times[b["id"]] = result["end_time"]
        # Signal de vie apres chaque batiment - avec beaucoup de batiments,
        # cette boucle peut prendre assez de temps pour declencher une
        # coupure de session si on n'envoie rien entre-temps.
        sock.sendall(keepalive)
        recv_all(sock, drain_seconds=1)

    if queue_end_times:
        next_check_time = min(queue_end_times.values())
    else:
        next_check_time = now + 120

    return next_check_time


def smart_loop(sock, end_times, next_check, td_city_grid=None, next_building_check=None):
    """Boucle principale : garde la session vivante (keepalive toutes les
    5s), surveille les notifications de fin d'entrainement (une par
    caserne active) poussees spontanement par le serveur, et relance
    automatiquement chaque cycle des que possible."""
    print("\n=== BOUCLE PRINCIPALE ===")
    print("Ctrl+C pour arreter.")
    keepalive = bytes.fromhex("04001627")  # kMsgCL2GSKeepLiveRequest = 10006
    resources = ResourceTracker()
    next_resource_print = int(time.time()) + 120
    if next_building_check is None:
        next_building_check = int(time.time()) + 30  # premiere verification rapide

    if TD_CITY_AREA_ID and td_city_grid:
        print("TDCity : prochaine case a explorer = " + str(td_city_grid) +
              (" (limite = " + str(TD_CITY_MAX_GRID) + ")" if TD_CITY_MAX_GRID else "") + ".")

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

    try:
        keepalive_count = 0
        while True:
            time.sleep(5)
            sock.sendall(keepalive)
            response, total = recv_all(sock, drain_seconds=2)
            keepalive_count += 1
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

                if state_changed:
                    persist(end_times)

                scan_and_claim_tasks_in_data(sock, response)

                attrs = parse_player_attributes(response)
                if attrs:
                    resources.update(attrs)

            now = int(time.time())

            # Batiments : verifie a l'heure de fin exacte connue (comme les
            # casernes), pas a intervalle fixe.
            if AUTO_UPGRADE_ALL_BUILDINGS and now >= next_building_check:
                new_next = upgrade_all_available_buildings(sock)
                next_building_check = new_next if new_next else now + 120

            if now >= next_resource_print:
                resources.print_summary()
                city_resources = get_city_resources(sock)
                for type_code, value in city_resources.items():
                    name = RESOURCE_TYPE_CODES.get(type_code, "Type " + str(type_code))
                    log_event("Stock actuel - " + name + " : " + str(value))
                if ENABLE_GUILD_FEATURES:
                    check_and_collect_guild_resource(sock)
                    help_guild_members(sock)

                if ENABLE_GUILD_FEATURES and GUILD_TECH_ID:
                    donate_guild_tech(sock, GUILD_TECH_ID, GUILD_TECH_LEVEL,
                                       times=GUILD_TECH_DONATE_TIMES)

                if PERSONAL_TECH_ID:
                    if not claim_research(sock, PERSONAL_TECH_ID):
                        start_research(sock, PERSONAL_TECH_ID)

                if CLAIM_CHAPTER_AWARD:
                    claim_chapter_award(sock)

                for task_id in DAILY_TASK_IDS:
                    time.sleep(1)
                    claim_daily_task_award(sock, task_id)

                for hero_id in HERO_TALENT_IDS:
                    time.sleep(1)
                    upgrade_hero_talent_recommended(sock, hero_id)

                for cid in CITIZEN_COLLECT_IDS:
                    time.sleep(1)
                    collect_citizen_settle(sock, cid)

                for pen_id in FARM_PEN_IDS:
                    time.sleep(1)
                    harvest_farm(sock, pen_id)

                if ENABLE_GUILD_FEATURES:
                    claim_all_guild_gifts(sock)
                claim_all_daily_gifts(sock)

                if TD_CITY_AREA_ID and td_city_grid:
                    if TD_CITY_MAX_GRID and td_city_grid > TD_CITY_MAX_GRID:
                        print("\nTDCity : limite atteinte (case " + str(TD_CITY_MAX_GRID) +
                              "), plus de nouvelle tentative.")
                    else:
                        print("\nTDCity : tentative sur la case " + str(td_city_grid) + "...")
                        won = explore_next_td_grid(sock, TD_CITY_AREA_ID, td_city_grid)
                        if won:
                            td_city_grid += 1
                            print("Case gagnee, prochaine case : " + str(td_city_grid) + ".")
                            persist_td_city_grid(td_city_grid)
                        else:
                            print("Case non gagnee (perdue, ou pas encore accessible) -")
                            print("on retentera la meme case au prochain cycle.")

                if AUTO_ATTACK_MONSTERS and BATTLE_HERO1 and BATTLE_HERO2 and BATTLE_TROOPS:
                    # Signal de vie avant l'attaque : ce point du cycle
                    # arrive apres deja plusieurs actions (ressources,
                    # guilde, taches...), et la reponse de CreateMarchRequest
                    # peut etre tres volumineuse - une coupure a ete
                    # observee juste apres une attaque reussie, au moment
                    # du keepalive suivant.
                    sock.sendall(keepalive)
                    recv_all(sock, drain_seconds=1)
                    search_and_attack_corrupted(sock, MONSTER_ATTACK_LEVEL,
                                                 BATTLE_HERO1, BATTLE_HERO2, BATTLE_TROOPS)
                    sock.sendall(keepalive)
                    recv_all(sock, drain_seconds=1)

                next_resource_print = now + 120

            for slot in TRAINING_SLOTS:
                bid = slot["barrack_id"]
                et = end_times.get(bid)
                nc = next_check.get(bid)
                should_try = (et and now >= et) or (nc and now >= nc)
                if should_try:
                    process_barrack(sock, slot, end_times, next_check)
                    time.sleep(1)

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

    try:
        _run_startup_sequence(sock)
    except (ConnectionResetError, BrokenPipeError) as e:
        print("\nConnexion perdue pendant le demarrage (" + type(e).__name__ + ").")
        print("Relance le bot (gs_bot.py sur le Pi, puis ls_login.py sur l'iPhone) -")
        print("l'etat deja sauvegarde sera repris automatiquement.")
        sock.close()
        return
    except Exception as e:
        print("\nErreur inattendue pendant le demarrage : " +
              type(e).__name__ + ": " + str(e))
        print("Relance le bot pour reessayer.")
        sock.close()
        return


def _run_startup_sequence(sock):
    saved_state = load_state()
    if saved_state:
        print("\nEtat precedent trouve (" + str(len(saved_state)) + " entree(s)),")
        print("reprise a partir des timestamps connus.")

    td_city_grid = None
    if TD_CITY_AREA_ID:
        td_city_grid = saved_state.get(
            "td_city_grid:" + str(TD_CITY_AREA_ID), TD_CITY_STARTING_GRID)
        print("TDCity : reprise a la case " + str(td_city_grid) + ".")

    keepalive = bytes.fromhex("04001627")  # kMsgCL2GSKeepLiveRequest = 10006

    def ping():
        sock.sendall(keepalive)
        recv_all(sock, drain_seconds=1)

    # Gains hors ligne (PrivilegeEscrow) : desactive par defaut. Renvoie
    # systematiquement vide malgre plusieurs captures reseau dediees -
    # semble calcule cote client, sans reelle utilite pour un bot qui
    # tourne en continu (jamais de vraie "periode hors ligne" a compenser).
    # La fonction reste disponible dans fatewar_actions_rewards.py si tu
    # veux la reactiver/investiguer davantage.
    # collect_privilege_escrow_reward(sock)
    # ping()

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

    for slot in TRAINING_SLOTS:
        bid = slot["barrack_id"]
        saved_et = saved_state.get("barrack:" + str(bid))
        if saved_et and saved_et > now:
            print("\n--- Caserne " + str(bid) + " : timestamp sauvegarde encore valide ---")
            end_times[bid] = saved_et
            continue
        time.sleep(1)
        process_barrack(sock, slot, end_times, next_check)
        ping()

    persist(end_times)

    time.sleep(1)
    check_and_claim_completed_tasks(sock)
    ping()

    time.sleep(1)
    check_and_claim_mail(sock)
    ping()

    if ENABLE_GUILD_FEATURES:
        time.sleep(1)
        check_and_collect_guild_resource(sock)
        ping()

        time.sleep(1)
        help_guild_members(sock)
        ping()

    if ENABLE_GUILD_FEATURES and GUILD_TECH_ID:
        time.sleep(1)
        donate_guild_tech(sock, GUILD_TECH_ID, GUILD_TECH_LEVEL, times=GUILD_TECH_DONATE_TIMES)
        ping()

    if PERSONAL_TECH_ID:
        time.sleep(1)
        if not claim_research(sock, PERSONAL_TECH_ID):
            start_research(sock, PERSONAL_TECH_ID)
        ping()

    if CLAIM_CHAPTER_AWARD:
        time.sleep(1)
        claim_chapter_award(sock)
        ping()

    for task_id in DAILY_TASK_IDS:
        time.sleep(1)
        claim_daily_task_award(sock, task_id)
    ping()

    for hero_id in HERO_TALENT_IDS:
        time.sleep(1)
        upgrade_hero_talent_recommended(sock, hero_id)
    ping()

    for cid in CITIZEN_COLLECT_IDS:
        time.sleep(1)
        collect_citizen_settle(sock, cid)
    ping()

    for pen_id in FARM_PEN_IDS:
        time.sleep(1)
        harvest_farm(sock, pen_id)
    ping()

    if ENABLE_GUILD_FEATURES:
        time.sleep(1)
        claim_all_guild_gifts(sock)
        ping()

    time.sleep(1)
    claim_all_daily_gifts(sock)
    ping()

    time.sleep(1)
    get_city_resources(sock)
    ping()

    time.sleep(1)
    next_building_check = upgrade_all_available_buildings(sock)
    ping()

    smart_loop(sock, end_times, next_check, td_city_grid, next_building_check)


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
