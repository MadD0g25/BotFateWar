from fatewar_core import (
    encode_field_varint, build_frame,
    walk_protobuf, find_message_of_type, recv_all, log_event,
)
from fatewar_actions_rewards import CURRENCY_NAMES, decode_resource_set


# ============================================================================
# TDCity (mode "Tower Defense" - combats de zone automatiques sur des
# cases/parcelles). Confirme par capture reseau reelle :
# - state=4 puis state=5 observes sur une case gagnee
# - state=2 seul observe sur une case perdue (pas de suite)
# La signification exacte des valeurs de "state" reste partiellement
# incertaine (pas de documentation officielle, deduit par observation) -
# a affiner si le comportement ne correspond pas a ce qui est attendu.
# ============================================================================

def explore_next_td_grid(sock, area_id, grid):
    """Attaque une case, et si gagnee, reclame immediatement la
    recompense (le combat semble se resoudre instantanement cote serveur,
    pas besoin d'attendre). Concu pour etre appele en boucle avec un
    numero de case incremente a chaque fois (grid, grid+1, grid+2...),
    puisque les cases semblent s'explorer dans l'ordre croissant.

    Retourne True si la case a ete gagnee (et la recompense reclamee),
    False sinon - permet a l'appelant de decider s'il faut avancer a la
    case suivante ou non."""
    won = start_td_battle(sock, area_id, grid, state=4)
    if not won:
        return False
    claim_td_battle_reward(sock, area_id, grid)
    return True


def start_td_battle(sock, area_id, grid, state=4):
    """Lance un combat automatique sur une case donnee (equivalent au clic
    pour attaquer une parcelle). state=4 est la valeur observee au debut
    d'un combat gagnant dans notre capture de reference - a verifier si
    le resultat ne correspond pas a ce qui est attendu."""
    print("\n=== ACTION : Lancement combat TDCity (zone=" + str(area_id) +
          ", case=" + str(grid) + ", etat=" + str(state) + ") ===")
    body = encode_field_varint(1, area_id) + encode_field_varint(2, grid) + encode_field_varint(3, state)
    packet = build_frame("da37", body)  # kMsgCL2GSTDCitySetStateRequest = 14298
    sock.sendall(packet)
    response, total = recv_all(sock, drain_seconds=3)
    print("Reponse brute : " + response.hex())

    if total == 0:
        print("Aucune reponse.")
        return False

    reply_body = find_message_of_type(response, 14299)  # ...Reply
    if reply_body is None:
        print("Message de reponse non trouve.")
        return False

    fields = walk_protobuf(reply_body)
    has_error = any(fn == 1 and wt == "varint" and val != 0 for fn, wt, val in fields)
    # NB : ici error_code est le champ 1 (pas 99 comme d'habitude) - a
    # verifier, structure un peu differente des autres messages du jeu.

    if has_error:
        print("Echec du lancement du combat.")
        return False
    else:
        print("Combat lance.")
        return True


def claim_td_battle_reward(sock, area_id, grid):
    """Reclame la recompense d'un combat TDCity termine sur une case
    donnee. Confirme par capture reseau reelle avec de vraies recompenses
    obtenues (kMsgCL2GSTDCityAreaBattleAwardRequest)."""
    print("\n=== ACTION : Reclamation combat TDCity (zone=" + str(area_id) +
          ", case=" + str(grid) + ") ===")
    body = encode_field_varint(1, area_id) + encode_field_varint(2, grid)
    packet = build_frame("dc37", body)  # kMsgCL2GSTDCityAreaBattleAwardRequest = 14300
    sock.sendall(packet)
    response, total = recv_all(sock, drain_seconds=3)
    print("Reponse brute : " + response.hex())

    if total == 0:
        print("Aucune reponse.")
        return

    reply_body = find_message_of_type(response, 14301)  # ...Reply
    if reply_body is None:
        print("Message de reponse non trouve.")
        return

    fields = walk_protobuf(reply_body)
    collected_any = False
    for fn, wt, val in fields:
        if fn == 4 and wt == "bytes":
            # Chaque occurrence du champ 4 est un Resource individuel
            # (pas une liste imbriquee comme d'habitude - structure plate
            # ici, confirmee par capture reelle).
            res_fields = walk_protobuf(val)
            res = {f: v for f, wt2, v in res_fields if wt2 == "varint"}
            if res:
                res_name = CURRENCY_NAMES.get(res.get(1), "Type " + str(res.get(1)))
                value = res.get(3, res.get(2, 0))
                log_event("Combat TDCity (case " + str(grid) + ") : +" +
                           str(value) + " " + res_name)
                collected_any = True

    if collected_any:
        print("Recompense de combat reclamee !")
    else:
        print("Rien a reclamer (combat pas termine, ou deja reclame).")


# ============================================================================
# Quetes principales (main tasks) - distinct des taches de guilde/periode
# deja geres dans fatewar_actions_rewards.py
# ============================================================================

def claim_main_task_reward(sock, task_id):
    """Reclame la recompense d'une quete principale terminee. Confirme
    par capture reseau reelle (kMsgCL2GSTaskMainTaskAwardRequest)."""
    print("\n=== ACTION : Reclamation quete principale #" + str(task_id) + " ===")
    body = encode_field_varint(1, task_id)
    packet = build_frame("fd27", body)  # kMsgCL2GSTaskMainTaskAwardRequest = 10237
    sock.sendall(packet)
    response, total = recv_all(sock, drain_seconds=3)
    print("Reponse brute : " + response.hex())

    if total == 0:
        print("Aucune reponse.")
        return

    reply_body = find_message_of_type(response, 10238)  # ...Reply
    if reply_body is None:
        print("Message de reponse non trouve.")
        return

    fields = walk_protobuf(reply_body)
    has_error = any(fn == 99 for fn, wt, val in fields)
    collected_any = False
    for fn, wt, val in fields:
        if fn == 99:
            print("Erreur, code : " + str(val))
        elif fn == 2 and wt == "bytes":
            res_fields = walk_protobuf(val)
            res = {f: v for f, wt2, v in res_fields if wt2 == "varint"}
            if res:
                res_name = CURRENCY_NAMES.get(res.get(1), "Type " + str(res.get(1)))
                value = res.get(3, res.get(2, 0))
                log_event("Quete principale #" + str(task_id) + " reclamee : +" +
                           str(value) + " " + res_name)
                collected_any = True

    if has_error:
        print("Echec de la reclamation.")
    elif collected_any:
        print("Quete principale reclamee !")
    else:
        print("Rien recu (deja reclamee ?).")
