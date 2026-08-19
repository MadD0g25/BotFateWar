import time

from fatewar_core import (
    encode_field_varint, build_frame,
    walk_protobuf, find_message_of_type, recv_all, log_event,
)


def decode_building_end_time(response, building_id):
    """Cherche un message CityBuildQueueNotice (10029) dans la reponse et
    retourne le end_time (timestamp Unix) du travail correspondant a
    building_id, si trouve. Contrairement aux troupes, aucune action de
    'confirmation' n'existe pour les batiments : l'amelioration s'applique
    automatiquement des que le minuteur arrive a zero, cote serveur."""
    notice_body = find_message_of_type(response, 10029)
    if notice_body is None:
        return None

    fields = walk_protobuf(notice_body)
    for fn, wt, val in fields:
        if fn == 1 and wt == "bytes":  # champ "queue" (BuildQueueInfo)
            queue_fields = walk_protobuf(val)
            for qfn, qwt, qval in queue_fields:
                if qfn == 1 and qwt == "bytes":  # champ "works" (repeated BuildWorkInfo)
                    work_fields = walk_protobuf(qval)
                    work_building_id = None
                    work_end_time = None
                    for wfn, wwt, wval in work_fields:
                        if wfn == 2:  # building_id
                            work_building_id = wval
                        elif wfn == 4:  # end_time
                            work_end_time = wval
                    if work_building_id == building_id and work_end_time:
                        return work_end_time
    return None


def upgrade_building(sock, building_id, queue_index=0):
    """Lance l'amelioration d'un batiment. Confirme par capture reseau
    (kMsgCL2GSCityUpgradeBuidlingRequest). building_id est propre a ta
    ville (meme ID que le batiment vu dans l'app - ex: la caserne
    utilisee pour l'entrainement a le meme building_id que barrack_id).

    Retourne un dict {"end_time": ..., "status": "started"|"queue_busy"|
    "not_eligible"|"error"} - contrairement aux troupes, il n'y a pas
    d'action de 'recuperation' separee : relance simplement
    upgrade_building() une fois le end_time atteint pour le niveau
    suivant."""
    print("\n=== ACTION : Amelioration du batiment #" + str(building_id) + " ===")
    body = encode_field_varint(1, building_id) + encode_field_varint(2, queue_index)
    packet = build_frame("3027", body)  # kMsgCL2GSCityUpgradeBuidlingRequest = 10032
    sock.sendall(packet)
    response, total = recv_all(sock, drain_seconds=3)
    print("Reponse brute : " + response.hex())

    if total == 0:
        print("Aucune reponse.")
        return {"end_time": None, "status": "error"}

    end_time = decode_building_end_time(response, building_id)

    reply_body = find_message_of_type(response, 10033)  # ...Reply
    if reply_body is None:
        print("Message de reponse non trouve.")
        return {"end_time": end_time, "status": "error"}

    fields = walk_protobuf(reply_body)
    has_error = any(fn == 99 for fn, wt, val in fields)

    if has_error:
        error_code = next(val for fn, wt, val in fields if fn == 99)
        if error_code == 5212:  # kECCityWorkQueueBusy
            print("Toutes les files de construction sont occupees (batiment #" +
                  str(building_id) + " en attente, retentera au prochain cycle).")
            return {"end_time": None, "status": "queue_busy"}
        elif error_code in (5202, 5204, 5205, 203):
            # kECCityNotMeetRequirement / kECCityWorkNotAvailable /
            # kECCityCanNotUpgrade / kECGeneralNotEnoughResource : ce
            # batiment precis ne peut pas etre ameliore maintenant (condition
            # non remplie, deja au max, ou pas assez de ressources). Sans
            # pause, ce batiment monopoliserait la seule place disponible a
            # chaque cycle et empecherait les autres d'etre tentes.
            print("Ce batiment ne peut pas etre ameliore pour l'instant " +
                  "(code " + str(error_code) + ") - mis de cote temporairement.")
            return {"end_time": None, "status": "not_eligible"}
        else:
            print("Echec de l'amelioration, code erreur : " + str(error_code))
            return {"end_time": None, "status": "error"}
    else:
        log_event("Amelioration lancee : batiment #" + str(building_id))
        if end_time:
            remaining = end_time - int(time.time())
            print("Fin de l'amelioration dans " + str(remaining) + " secondes " +
                  "(timestamp " + str(end_time) + ").")
        return {"end_time": end_time, "status": "started"}
