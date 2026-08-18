import time
from datetime import datetime

from fatewar_core import (
    encode_varint, encode_field_varint, build_frame,
    walk_protobuf, find_message_of_type, find_all_messages_of_type,
    recv_all, log_event,
)


def decode_train_status(response, barrack_id):
    """Retourne le statut complet d'une caserne :
    {"status": int, "end_time": int|None}. Important : le statut
    kTrainWorkStatusNone (0, aucun entrainement en cours) et
    kTrainWorkStatusWorking (1, entrainement en cours) declenchent tous
    les deux la meme erreur cote serveur (5809, kECArmyNotNoneDeal) lors
    d'une tentative de recuperation - il faut donc lire ce statut pour
    savoir s'il faut vraiment attendre (status=1) ou tenter de lancer un
    entrainement immediatement (status=0, rien n'est en cours)."""
    notices = find_all_messages_of_type(response, 10401)
    for notice_body in notices:
        fields = walk_protobuf(notice_body)
        for fn, wt, val in fields:
            if fn == 1 and wt == "bytes":  # champ "work" (TrainWorkInfo)
                work_fields = walk_protobuf(val)
                work_barrack_id = None
                work_end_time = None
                work_status = None
                for wfn, wwt, wval in work_fields:
                    if wfn == 7:  # barrack_id
                        work_barrack_id = wval
                    elif wfn == 4:  # end_time
                        work_end_time = wval
                    elif wfn == 5:  # work_status
                        work_status = wval
                if work_barrack_id == barrack_id:
                    # IMPORTANT : en Protobuf, un champ dont la valeur est 0
                    # (la valeur par defaut) n'est jamais transmis sur le
                    # reseau. Si le champ work_status est absent alors qu'on
                    # a bien trouve la notice pour cette caserne, ca signifie
                    # concretement que le statut EST 0 (kTrainWorkStatusNone,
                    # caserne vide) - pas "inconnu".
                    if work_status is None:
                        work_status = 0
                    return {"status": work_status, "end_time": work_end_time}
    return None


def decode_train_end_time(response, barrack_id):
    """Raccourci pratique qui ne retourne que le end_time."""
    status = decode_train_status(response, barrack_id)
    return status["end_time"] if status else None


def train_troops(sock, barrack_id, army_id, count):
    """Lance l'entrainement de troupes. Retourne un dict :
    {"end_time": ..., "status": "started"|"insufficient_resources"|"busy"|"error"}
    plutot qu'une simple valeur, pour permettre a l'appelant de reagir
    intelligemment selon la raison exacte de l'echec (pas les memes delais
    de reessai selon que la caserne est occupee ou que les ressources
    manquent)."""
    print("\n=== ACTION : Entrainement de troupes (armee=" + str(army_id) +
          ", quantite=" + str(count) + ", caserne=" + str(barrack_id) + ") ===")

    army_info_body = encode_field_varint(1, army_id) + encode_field_varint(2, count)
    body = b""
    tag = (1 << 3) | 2
    body += encode_varint(tag) + encode_varint(len(army_info_body)) + army_info_body
    body += encode_field_varint(2, barrack_id)

    packet = build_frame("a228", body)  # kMsgCL2GSTrainRequest = 10402
    sock.sendall(packet)
    response, total = recv_all(sock, drain_seconds=3)
    print("Reponse brute : " + response.hex())

    if total == 0:
        print("Aucune reponse.")
        return {"end_time": None, "status": "error"}

    end_time = decode_train_end_time(response, barrack_id)

    reply_body = find_message_of_type(response, 10403)  # kMsgGS2CLTrainReply
    if reply_body is None:
        print("Message TrainReply non trouve dans la reponse.")
        return {"end_time": end_time, "status": "error"}

    fields = walk_protobuf(reply_body)
    has_error = any(fn == 99 for fn, wt, val in fields)

    if has_error:
        error_code = next(val for fn, wt, val in fields if fn == 99)
        if error_code == 5801:  # kECArmyNotEnough
            print("Echec : pas assez de ressources pour lancer cet entrainement")
            print("(code 5801, kECArmyNotEnough).")
            return {"end_time": None, "status": "insufficient_resources"}
        elif error_code == 5816:  # kECArmyTraining
            print("Echec : une troupe est deja en cours d'entrainement dans cette")
            print("caserne (code 5816, kECArmyTraining). Normal, pas un bug -")
            print("attends la fin de l'entrainement en cours.")
            return {"end_time": None, "status": "busy"}
        else:
            print("Echec de l'entrainement, code erreur : " + str(error_code))
            return {"end_time": None, "status": "error"}
    else:
        log_event("Entrainement lance : " + str(count) + "x armee " + str(army_id) +
                   " (caserne " + str(barrack_id) + ")")
        if end_time:
            remaining = end_time - int(time.time())
            finish_clock = datetime.fromtimestamp(end_time).strftime("%H:%M:%S")
            print("Fin de l'entrainement dans " + str(remaining) + " secondes, " +
                  "vers " + finish_clock + ".")
        return {"end_time": end_time, "status": "started"}


def claim_finished_training(sock, barrack_id):
    """Recupere les troupes d'un entrainement termine (equivalent au clic
    manuel sur le bouton de recuperation dans l'app). Confirme par capture
    reseau : kMsgCL2GSDealArmyRequest, ne prend que le barrack_id en
    parametre. Retourne un dict {"claimed": bool, "still_training": bool,
    "queue_empty": bool, "end_time": int|None}.

    IMPORTANT : le code d'erreur 5809 (kECArmyNotNoneDeal) est renvoye a
    la fois quand un entrainement est vraiment en cours (work_status=1,
    kTrainWorkStatusWorking) ET quand la caserne n'a tout simplement AUCUN
    entrainement en file (work_status=0, kTrainWorkStatusNone) - ces deux
    situations necessitent une reaction totalement differente."""
    print("\n=== ACTION : Recuperation des troupes entrainees (caserne " +
          str(barrack_id) + ") ===")
    body = encode_field_varint(1, barrack_id)
    packet = build_frame("ac28", body)  # kMsgCL2GSDealArmyRequest = 10412
    sock.sendall(packet)
    response, total = recv_all(sock, drain_seconds=3)
    print("Reponse brute : " + response.hex())

    if total == 0:
        print("Aucune reponse.")
        return {"claimed": False, "still_training": False, "queue_empty": False, "end_time": None}

    train_status = decode_train_status(response, barrack_id)
    end_time = train_status["end_time"] if train_status else None
    work_status = train_status["status"] if train_status else None

    reply_body = find_message_of_type(response, 10413)  # kMsgGS2CLDealArmyReply
    if reply_body is None:
        print("Message DealArmyReply non trouve dans la reponse.")
        return {"claimed": False, "still_training": False, "queue_empty": False, "end_time": end_time}

    fields = walk_protobuf(reply_body)
    has_error = any(fn == 99 for fn, wt, val in fields)

    if has_error:
        error_code = next(val for fn, wt, val in fields if fn == 99)
        if error_code == 5809:  # kECArmyNotNoneDeal
            if work_status == 0:  # kTrainWorkStatusNone : rien en file
                print("Caserne libre, aucun entrainement en file actuellement.")
                return {"claimed": False, "still_training": False, "queue_empty": True, "end_time": None}
            elif end_time:
                remaining = end_time - int(time.time())
                finish_clock = datetime.fromtimestamp(end_time).strftime("%H:%M:%S")
                print("Encore en cours, pret dans " + str(remaining) +
                      "s (vers " + finish_clock + ").")
            else:
                print("Rien a recuperer pour l'instant, entrainement encore en cours")
                print("(heure de fin non trouvee dans cette reponse).")
            return {"claimed": False, "still_training": True, "queue_empty": False, "end_time": end_time}
        print("Echec de la recuperation, code erreur : " + str(error_code))
        return {"claimed": False, "still_training": False, "queue_empty": False, "end_time": end_time}
    else:
        log_event("Troupes recuperees (caserne " + str(barrack_id) + ")")
        return {"claimed": True, "still_training": False, "queue_empty": False, "end_time": end_time}


def train_max_troops(sock, barrack_id, army_id, candidates=None):
    """Lance l'entrainement avec la plus grande quantite possible, sans
    avoir a la deviner/regler manuellement a chaque fois.

    IMPORTANT sur la methode : le serveur ne renvoie jamais le "maximum
    autorise" directement (verifie dans dump.cs - TrainReply n'a qu'un
    error_code). Le bouton "max" de l'app le calcule cote client a partir
    du cout par unite (donnee qu'on n'a pas). Ici, on teste une serie de
    quantites decroissantes et on s'arrete a la premiere qui reussit -
    une tentative refusee pour ressources insuffisantes ne consomme rien
    (verifie empiriquement), donc cette methode ne risque jamais de
    lancer deux entrainements ou de gaspiller des ressources. Une fois
    qu'une quantite reussit, on s'arrete immediatement (pas de nouvel
    essai apres un succes)."""
    if candidates is None:
        # Grille resserree pour ne pas "sauter" par-dessus la vraie limite
        # (ex: si le max reel est 250, une liste trop grossiere comme
        # [500, 200] passerait directement de 500 en echec a 200 en succes,
        # ratant les 250 vraiment disponibles).
        candidates = [
            100000, 50000, 20000, 10000, 5000, 3000, 2000, 1500, 1000,
            800, 600, 500, 450, 400, 350, 300, 280, 260, 250, 240, 220,
            200, 180, 160, 140, 120, 100, 90, 80, 70, 60, 50, 40, 30,
            25, 20, 15, 10, 5, 3, 1,
        ]

    print("\n=== Recherche de la quantite maximale entrainable ===")
    for count in candidates:
        result = train_troops(sock, barrack_id, army_id, count)
        if result["status"] == "started":
            return result
        if result["status"] == "busy":
            # Caserne occupee - pas la peine de continuer a essayer
            # d'autres quantites, le probleme n'est pas la quantite.
            return result
        # "insufficient_resources" ou "error" -> on essaie plus petit
        time.sleep(1)

    print("Aucune quantite testee n'a fonctionne (meme 1 unite).")
    return {"end_time": None, "status": "insufficient_resources"}
