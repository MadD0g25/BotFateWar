import time

from fatewar_core import (
    encode_varint, encode_field_varint, build_frame,
    walk_protobuf, split_messages, find_message_of_type, recv_all, log_event,
)

# Statuts observes dans RadarInfoNotice (deduit par observation reelle,
# pas de nom officiel confirme dans dump.cs pour ce champ precis) :
#   1 = cible disponible (target_id present)
#   2 = cible traitee/expiree (target_id absent)
RADAR_STATUS_AVAILABLE = 1

# search_type=0 (kMapSearchType_Barbarians) - confirme par capture reelle
# comme le type utilise pour chercher les "Corrompus" (le champ etait
# absent du message, donc egal a sa valeur par defaut 0).
MAP_SEARCH_TYPE_CORRUPTED = 0


def search_corrupted_monster(sock, level):
    """Cherche un monstre 'Corrompu' au niveau demande (equivalent au
    bouton 'Rechercher' avec le curseur de niveau dans l'app). Bien plus
    simple et fiable que d'attendre une notification radar passive :
    une seule requete/reponse donne directement target_id et position.

    Retourne {"target_id":..., "x":..., "y":...} ou None si rien trouve
    a ce niveau (essaie un niveau different si echec)."""
    print("\n=== RECHERCHE : Monstre Corrompu (niveau " + str(level) + ") ===")
    body = encode_field_varint(2, level) + encode_field_varint(5, level)
    packet = build_frame("fe28", body)  # kMsgCL2GSMapSearchRequest = 10494
    sock.sendall(packet)
    response, total = recv_all(sock, drain_seconds=3)
    print("Reponse brute : " + response.hex())

    if total == 0:
        print("Aucune reponse.")
        return None

    reply_body = find_message_of_type(response, 10495)  # kMsgGS2CLMapSearchReply
    if reply_body is None:
        print("Message de reponse non trouve.")
        return None

    fields = walk_protobuf(reply_body)
    has_error = any(fn == 99 for fn, wt, val in fields)
    if has_error:
        error_code = next(val for fn, wt, val in fields if fn == 99)
        print("Aucun monstre trouve a ce niveau, code : " + str(error_code))
        return None

    result = {}
    for fn, wt, val in fields:
        if fn == 3:
            result["target_id"] = val
        elif fn == 4 and wt == "bytes":
            pos_fields = walk_protobuf(val)
            pos = {f: v for f, wt2, v in pos_fields if wt2 == "varint"}
            result["x"] = pos.get(1)
            result["y"] = pos.get(2)

    if "target_id" in result:
        print("Trouve : cible " + str(result["target_id"]) + " en " +
              str(result.get("x")) + "," + str(result.get("y")) + ".")
        return result
    else:
        print("Reponse recue mais sans cible exploitable.")
        return None


def encode_position(x, y):
    """Encode une position Vector2d (x,y) en sous-message protobuf."""
    return encode_field_varint(1, x) + encode_field_varint(2, y)


def scan_radar_notices(response):
    """Cherche des RadarInfoNotice (11259, notification passive poussee
    par le serveur) dans un buffer deja recu, et retourne la liste des
    cibles disponibles trouvees : [{"target_id":..., "x":..., "y":...,
    "radar_id":...}, ...]. A utiliser dans la boucle principale, comme
    scan_and_claim_tasks_in_data pour les taches."""
    targets = []
    for body in split_messages(response):
        msg_type, msg_body = body
        if msg_type != 11259:
            continue
        for fn, wt, val in walk_protobuf(msg_body):
            if fn != 1 or wt != "bytes":
                continue
            sub_fields = walk_protobuf(val)
            entry = {}
            for sfn, swt, sval in sub_fields:
                if sfn == 1:
                    entry["radar_id"] = sval
                elif sfn == 3:
                    entry["status"] = sval
                elif sfn == 4:
                    entry["target_id"] = sval
                elif sfn == 6 and swt == "bytes":
                    pos_fields = walk_protobuf(sval)
                    pos = {f: v for f, wt2, v in pos_fields if wt2 == "varint"}
                    entry["x"] = pos.get(1)
                    entry["y"] = pos.get(2)
            if entry.get("status") == RADAR_STATUS_AVAILABLE and entry.get("target_id"):
                targets.append(entry)
    return targets


def attack_monster(sock, target_id, x, y, hero1, hero2, troops):
    """Lance une marche d'attaque vers une cible reperee par radar.

    hero1/hero2 : IDs de tes deux heros a envoyer (propres a ton compte).
    troops : liste de dicts {"army_id":..., "count":...} - composition de
    l'armee envoyee.

    Confirme par capture reseau reelle (kMsgCL2GSCreateMarchRequest,
    target_type=2=kMarchCommandTarget_Battle)."""
    from fatewar_names import HERO_NAMES
    h1_name = HERO_NAMES.get(hero1, "Heros " + str(hero1))
    h2_name = HERO_NAMES.get(hero2, "Heros " + str(hero2))
    print("\n=== ACTION : Attaque de monstre avec " + h1_name + " et " + h2_name +
          " (cible=" + str(target_id) +
          ", position=" + str(x) + "," + str(y) + ") ===")

    # --- Construction du champ 1 (MarchCommand) ---
    position = encode_position(x, y)
    tag_pos = (2 << 3) | 2
    command = encode_varint(tag_pos) + encode_varint(len(position)) + position
    command += encode_field_varint(3, 2)  # target_type = Battle
    command += encode_field_varint(4, target_id)

    # --- Construction du champ 2 (ArmyData) ---
    army = encode_field_varint(1, hero1) + encode_field_varint(2, hero2)
    for t in troops:
        troop_entry = encode_field_varint(1, t["army_id"]) + encode_field_varint(2, t["count"])
        tag_troop = (8 << 3) | 2
        army += encode_varint(tag_troop) + encode_varint(len(troop_entry)) + troop_entry

    body = b""
    tag_cmd = (1 << 3) | 2
    body += encode_varint(tag_cmd) + encode_varint(len(command)) + command
    tag_army = (2 << 3) | 2
    body += encode_varint(tag_army) + encode_varint(len(army)) + army

    packet = build_frame("8e27", body)  # kMsgCL2GSCreateMarchRequest = 10126
    sock.sendall(packet)
    response, total = recv_all(sock, drain_seconds=3)
    print("Reponse brute : " + response.hex())

    if total == 0:
        print("Aucune reponse.")
        return None

    reply_body = find_message_of_type(response, 10127)  # kMsgGS2CLCreateMarchReply
    if reply_body is None:
        print("Message de reponse non trouve.")
        return None

    fields = walk_protobuf(reply_body)
    has_error = any(fn == 99 for fn, wt, val in fields)
    if has_error:
        error_code = next(val for fn, wt, val in fields if fn == 99)
        print("Echec du lancement de la marche, code erreur : " + str(error_code))
        return None
    else:
        log_event("Marche d'attaque lancee vers cible " + str(target_id) + ".")
        print("Marche lancee avec succes !")
        return True


def search_and_attack_corrupted(sock, level, hero1, hero2, troops=None,
                                 auto_troop_army_id=None):
    """Combine la recherche et l'attaque en un seul appel : cherche un
    Corrompu au niveau demande, et attaque immediatement s'il y en a un.

    Deux modes de composition d'armee :
    - troops fourni (liste de dicts {"army_id":..., "count":...}) :
      composition fixe, utilisee telle quelle.
    - auto_troop_army_id fourni (et troops absent) : calcule
      automatiquement la quantite recommandee pour ce niveau precis
      (voir get_recommended_troop_count dans fatewar_troop_data.py,
      extrait de la vraie config du jeu - correspond au texte "Troupe
      recommandee" affiche dans l'app), avec ce seul type de troupe.

    Retourne True si l'attaque a ete lancee, False sinon (rien trouve a
    ce niveau, niveau non couvert par la table de recommandation, ou
    echec de la marche)."""
    target = search_corrupted_monster(sock, level)
    if target is None:
        return False

    if troops is None and auto_troop_army_id is not None:
        from fatewar_troop_data import get_recommended_troop_count
        recommended = get_recommended_troop_count(level)
        if recommended is None:
            print("Pas de quantite recommandee connue pour le niveau " +
                  str(level) + " (au-dela des donnees extraites) - abandon.")
            return False
        print("Quantite recommandee pour ce niveau : " + str(recommended))
        troops = [{"army_id": auto_troop_army_id, "count": recommended}]

    if not troops:
        print("Aucune composition de troupes fournie - abandon.")
        return False

    time.sleep(1)
    return bool(attack_monster(sock, target["target_id"], target["x"], target["y"],
                                hero1, hero2, troops))
