import time

from fatewar_core import (
    encode_varint, encode_field_varint, build_frame,
    walk_protobuf, find_message_of_type, recv_all, log_event,
)
from fatewar_actions_rewards import CURRENCY_NAMES


# ============================================================================
# Recherche (arbre technologique de la ville) - meme schema que les
# batiments : lancer puis reclamer separement. Aucune heure de fin
# recuperable dans les structures decodees (TechInfoData n'a pas de
# end_time) - geree par verification periodique plutot que minuteur
# precis, contrairement aux casernes/batiments.
# ============================================================================

def start_research(sock, tech_id, queue_index=0):
    """Lance une recherche. tech_id est la recherche ACTUELLEMENT
    disponible/selectionnee dans ton arbre technologique - change avec le
    temps, a mettre a jour manuellement (voir README.md)."""
    print("\n=== ACTION : Lancement recherche (tech=" + str(tech_id) + ") ===")
    body = encode_field_varint(1, tech_id) + encode_field_varint(2, queue_index)
    packet = build_frame("b828", body)  # kMsgCL2GSResearchRequest = 10424
    sock.sendall(packet)
    response, total = recv_all(sock, drain_seconds=3)
    print("Reponse brute : " + response.hex())

    if total == 0:
        print("Aucune reponse.")
        return False

    reply_body = find_message_of_type(response, 10425)  # MsgGS2CLResearchnReply
    if reply_body is None:
        print("Message de reponse non trouve.")
        return False

    fields = walk_protobuf(reply_body)
    has_error = any(fn == 99 for fn, wt, val in fields)
    if has_error:
        error_code = next(val for fn, wt, val in fields if fn == 99)
        print("Echec du lancement, code erreur : " + str(error_code))
        return False
    else:
        log_event("Recherche lancee : tech " + str(tech_id))
        return True


def claim_research(sock, tech_id):
    """Reclame une recherche terminee (kMsgCL2GSDealResearchRequest)."""
    print("\n=== ACTION : Reclamation recherche (tech=" + str(tech_id) + ") ===")
    body = encode_field_varint(1, tech_id)
    packet = build_frame("c228", body)  # kMsgCL2GSDealResearchRequest = 10434
    sock.sendall(packet)
    response, total = recv_all(sock, drain_seconds=3)
    print("Reponse brute : " + response.hex())

    if total == 0:
        print("Aucune reponse.")
        return False

    reply_body = find_message_of_type(response, 10435)  # MsgGS2CLDealResearchReply
    if reply_body is None:
        print("Message de reponse non trouve.")
        return False

    fields = walk_protobuf(reply_body)
    has_error = any(fn == 99 for fn, wt, val in fields)
    if has_error:
        error_code = next(val for fn, wt, val in fields if fn == 99)
        print("Pas encore prete ou echec, code erreur : " + str(error_code))
        return False
    else:
        log_event("Recherche terminee et reclamee : tech " + str(tech_id))
        return True


# ============================================================================
# Recompenses de chapitre et de taches quotidiennes - meme pattern que les
# quetes principales/de guilde deja geres ailleurs.
# ============================================================================

def claim_chapter_award(sock):
    """Reclame la recompense du chapitre d'histoire actuel (corps vide,
    kMsgCL2GSTaskChapterAwardRequest)."""
    print("\n=== ACTION : Reclamation recompense de chapitre ===")
    packet = build_frame("0e29", b"")  # kMsgCL2GSTaskChapterAwardRequest = 10510
    sock.sendall(packet)
    response, total = recv_all(sock, drain_seconds=3)
    print("Reponse brute : " + response.hex())

    if total == 0:
        print("Aucune reponse.")
        return

    reply_body = find_message_of_type(response, 10511)  # ...Reply
    if reply_body is None:
        print("Message de reponse non trouve.")
        return

    fields = walk_protobuf(reply_body)
    has_error = False
    collected_any = False
    for fn, wt, val in fields:
        if fn == 99:
            has_error = True
            print("Erreur, code : " + str(val))
        elif fn == 2 and wt == "bytes":
            res_fields = walk_protobuf(val)
            res = {f: v for f, wt2, v in res_fields if wt2 == "varint"}
            if res:
                res_name = CURRENCY_NAMES.get(res.get(1), "Type " + str(res.get(1)))
                value = res.get(3, res.get(2, 0))
                log_event("Recompense de chapitre : +" + str(value) + " " + res_name)
                collected_any = True

    if has_error:
        print("Echec (chapitre pas termine, ou deja reclame).")
    elif collected_any:
        print("Recompense de chapitre reclamee !")
    else:
        print("Rien a reclamer pour l'instant.")


def claim_daily_task_award(sock, task_id):
    """Reclame la recompense d'une tache quotidienne terminee. task_id est
    propre a ta progression - trouve par capture reseau
    (kMsgCL2GSTaskDailyTaskAwardRequest)."""
    print("\n=== ACTION : Reclamation tache quotidienne #" + str(task_id) + " ===")
    body = encode_field_varint(1, task_id)
    packet = build_frame("3c29", body)  # kMsgCL2GSTaskDailyTaskAwardRequest = 10556
    sock.sendall(packet)
    response, total = recv_all(sock, drain_seconds=3)
    print("Reponse brute : " + response.hex())

    if total == 0:
        print("Aucune reponse.")
        return

    reply_body = find_message_of_type(response, 10557)  # ...Reply
    if reply_body is None:
        print("Message de reponse non trouve.")
        return

    fields = walk_protobuf(reply_body)
    has_error = False
    collected_any = False
    for fn, wt, val in fields:
        if fn == 99:
            has_error = True
            print("Erreur, code : " + str(val))
        elif fn == 2 and wt == "bytes":
            res_fields = walk_protobuf(val)
            res = {f: v for f, wt2, v in res_fields if wt2 == "varint"}
            if res:
                res_name = CURRENCY_NAMES.get(res.get(1), "Type " + str(res.get(1)))
                value = res.get(3, res.get(2, 0))
                log_event("Tache quotidienne #" + str(task_id) + " : +" +
                           str(value) + " " + res_name)
                collected_any = True

    if has_error:
        print("Echec de la reclamation.")
    elif collected_any:
        print("Tache quotidienne reclamee !")
    else:
        print("Rien recu (deja reclamee ?).")


# ============================================================================
# Amelioration de talent de heros recommandee (bouton "1 clic" de l'app -
# choisit et applique automatiquement le meilleur talent selon le jeu).
# ============================================================================

def upgrade_hero_talent_recommended(sock, hero_id, page=1):
    """Ameliore le talent d'un heros en suivant la recommandation
    automatique du jeu (equivalent au bouton correspondant dans l'app).
    hero_id est propre a ton compte - trouve par capture reseau
    (kMsgCL2GSHeroUpTalentAsRecommendedRequest)."""
    print("\n=== ACTION : Amelioration talent recommandee (heros=" +
          str(hero_id) + ") ===")
    body = encode_field_varint(1, hero_id) + encode_field_varint(2, page)
    packet = build_frame("c934", body)  # ...Request = 13513
    sock.sendall(packet)
    response, total = recv_all(sock, drain_seconds=3)
    print("Reponse brute : " + response.hex())

    if total == 0:
        print("Aucune reponse.")
        return False

    reply_body = find_message_of_type(response, 13514)  # ...Reply
    if reply_body is None:
        print("Message de reponse non trouve.")
        return False

    fields = walk_protobuf(reply_body)
    has_error = any(fn == 99 for fn, wt, val in fields)
    if has_error:
        error_code = next(val for fn, wt, val in fields if fn == 99)
        print("Echec (plus de points de talent disponibles ?), code : " + str(error_code))
        return False
    else:
        log_event("Talent ameliore (recommande) : heros " + str(hero_id))
        return True


# ============================================================================
# Soin a l'hopital - fonction disponible mais PAS branchee automatiquement
# dans la boucle du bot : necessite de connaitre le nombre de blesses par
# type de troupe (map_wounded), qu'on ne sait pas encore decouvrir
# automatiquement (pas de requete "liste des blesses" identifiee pour
# l'instant). A utiliser manuellement en attendant, ou capture
# complementaire bienvenue pour l'automatiser completement.
# ============================================================================

def cure_hospital(sock, wounded_map, use_cure_potion=False):
    """Soigne les troupes blessees a l'hopital. wounded_map est un dict
    {army_id: nombre_a_soigner}. use_cure_potion active l'utilisation de
    potions de soin (probablement premium/consommable - a verifier avant
    d'automatiser)."""
    print("\n=== ACTION : Soin hopital (" + str(len(wounded_map)) + " type(s) de troupe) ===")
    body = encode_field_varint(1, 1 if use_cure_potion else 0)
    for army_id, count in wounded_map.items():
        entry = encode_field_varint(1, army_id) + encode_field_varint(2, count)
        tag = (2 << 3) | 2
        body += encode_varint(tag) + encode_varint(len(entry)) + entry
    packet = build_frame("7929", body)  # kMsgCL2GSHospitalCureRequest = 10617
    sock.sendall(packet)
    response, total = recv_all(sock, drain_seconds=3)
    print("Reponse brute : " + response.hex())

    if total == 0:
        print("Aucune reponse.")
        return

    reply_body = find_message_of_type(response, 10618)  # ...Reply
    if reply_body is None:
        print("Message de reponse non trouve.")
        return

    fields = walk_protobuf(reply_body)
    has_error = any(fn == 99 for fn, wt, val in fields)
    if has_error:
        error_code = next(val for fn, wt, val in fields if fn == 99)
        print("Echec du soin, code erreur : " + str(error_code))
    else:
        log_event("Soin hopital effectue (" + str(len(wounded_map)) + " type(s)).")
