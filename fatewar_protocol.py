import socket
import struct
import time
import json
import os
from datetime import datetime

try:
    from config import (
        GAME_ID, KEY_UUID, DEVICE_ID, USER_ID,
        APP_VERSION, DEVICE_MODEL, GPU_MODEL, WEB_SESSION,
    )
except ImportError:
    print("ERREUR : fichier config.py introuvable.")
    print("Copie config.example.py vers config.py et renseigne tes propres")
    print("identifiants (voir README.md).")
    raise SystemExit(1)

LS_HOST = "pss-login.pss.igotgames.net"
LS_PORT = 9310

LOG_FILE = "fatewar_bot.log"
STATE_FILE = "fatewar_state.json"


def log_event(text):
    """Ecrit une ligne horodatee dans le fichier de log, en plus de
    l'afficher a l'ecran."""
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    line = "[" + timestamp + "] " + text
    print(line)
    try:
        with open(LOG_FILE, "a", encoding="utf-8") as f:
            f.write(line + "\n")
    except Exception:
        pass  # on ne bloque jamais le bot pour un souci d'ecriture de log


def load_state():
    """Charge l'etat persistant (timestamps de fin d'entrainement/amelioration
    connus lors de la derniere execution) depuis STATE_FILE. Permet au bot
    de reprendre intelligemment apres un plantage/redemarrage au lieu de
    repartir de zero sans savoir ou en etaient les casernes. Retourne un
    dict vide si le fichier n'existe pas encore ou est invalide."""
    if not os.path.exists(STATE_FILE):
        return {}
    try:
        with open(STATE_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {}


def save_state(state):
    """Sauvegarde l'etat persistant sur disque. Appelee a chaque fois
    qu'un nouveau timestamp de fin est connu, pour que le bot puisse
    reprendre correctement s'il redemarre avant l'echeance."""
    try:
        with open(STATE_FILE, "w", encoding="utf-8") as f:
            json.dump(state, f)
    except Exception:
        pass  # on ne bloque jamais le bot pour un souci d'ecriture d'etat


# ============================================================================
# Encodage / decodage Protobuf bas niveau
# ============================================================================

def encode_varint(n):
    out = bytearray()
    while True:
        b = n & 0x7F
        n >>= 7
        if n:
            out.append(b | 0x80)
        else:
            out.append(b)
            break
    return bytes(out)


def encode_field_varint(field_num, value):
    tag = (field_num << 3) | 0
    return encode_varint(tag) + encode_varint(value)


def encode_field_string(field_num, value):
    tag = (field_num << 3) | 2
    data = value.encode("utf-8")
    return encode_varint(tag) + encode_varint(len(data)) + data


def build_frame(msg_type_hex, body):
    msg_type = bytes.fromhex(msg_type_hex)
    total_len = 2 + len(msg_type) + len(body)
    length_prefix = struct.pack("<H", total_len)
    return length_prefix + msg_type + body


def decode_varint(data, pos):
    result = 0
    shift = 0
    while True:
        b = data[pos]
        result |= (b & 0x7F) << shift
        pos += 1
        if not (b & 0x80):
            break
        shift += 7
    return result, pos


def walk_protobuf(data):
    pos = 0
    fields = []
    while pos < len(data):
        tag, pos = decode_varint(data, pos)
        field_num = tag >> 3
        wire_type = tag & 0x7
        if wire_type == 0:
            val, pos = decode_varint(data, pos)
            fields.append((field_num, "varint", val))
        elif wire_type == 2:
            length, pos = decode_varint(data, pos)
            val = data[pos:pos + length]
            pos += length
            fields.append((field_num, "bytes", val))
        else:
            fields.append((field_num, "wiretype_" + str(wire_type), data[pos:]))
            break
    return fields


def split_messages(data):
    """Decoupe un buffer pouvant contenir plusieurs messages concatenes."""
    messages = []
    pos = 0
    while pos + 4 <= len(data):
        length = int.from_bytes(data[pos:pos + 2], "little")
        if length < 4 or pos + length > len(data):
            break
        msg_type = int.from_bytes(data[pos + 2:pos + 4], "little")
        body = data[pos + 4:pos + length]
        messages.append((msg_type, body))
        pos += length
    return messages


def find_message_of_type(data, expected_type):
    for msg_type, body in split_messages(data):
        if msg_type == expected_type:
            return body
    return None


def recv_all(sock, drain_seconds=3):
    sock.settimeout(drain_seconds)
    chunks = []
    total = 0
    try:
        while True:
            data = sock.recv(65536)
            if not data:
                break
            chunks.append(data)
            total += len(data)
    except socket.timeout:
        pass
    return b"".join(chunks), total


# ============================================================================
# Login Server (LS) - a executer depuis un appareil Apple reel uniquement
# ============================================================================

def build_ls_login_packet():
    body = b""
    body += encode_field_varint(3, USER_ID)
    body += encode_field_string(4, WEB_SESSION)
    body += encode_field_varint(6, 4)
    body += encode_field_string(8, GAME_ID)
    body += encode_field_string(10, KEY_UUID)
    body += encode_field_string(13, APP_VERSION)
    return build_frame("9d27", body)


def do_ls_login(ls_host=None, ls_port=None):
    ls_host = ls_host or LS_HOST
    ls_port = ls_port or LS_PORT
    print("=== LOGIN LS (" + ls_host + ":" + str(ls_port) + ") ===")
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.settimeout(10)
    gs_host = None
    gs_port = None
    login_session = None
    try:
        sock.connect((ls_host, ls_port))
        print("Connecte au LS.")
        time.sleep(0.2)

        packet = build_ls_login_packet()
        sock.sendall(packet)

        response, total = recv_all(sock, drain_seconds=5)
        print("Recu " + str(total) + " octets du LS.")
        if total == 0:
            return None, None, None

        body = response[4:]
        fields = walk_protobuf(body)

        for fn, wt, val in fields:
            if wt == "bytes":
                try:
                    s = val.decode("ascii")
                    if fn == 3:
                        login_session = s
                except Exception:
                    if fn == 2:
                        sub_fields = walk_protobuf(val)
                        for sfn, swt, sval in sub_fields:
                            if swt == "varint" and sfn == 1:
                                gs_port = sval
                            elif swt == "bytes" and sfn == 2:
                                gs_host = sval.decode("ascii")

        return login_session, gs_host, gs_port

    except ConnectionResetError:
        print("LS a reinitialise la connexion (rate limit probable, ou token deja utilise).")
        return None, None, None
    finally:
        sock.close()


# ============================================================================
# Game Server (GS) - peut tourner depuis n'importe quel appareil (Linux OK)
# ============================================================================

def build_gs_login_packet(login_session_nonce):
    body = b""
    body += encode_field_varint(1, USER_ID)
    body += encode_field_varint(2, USER_ID)
    body += encode_field_string(3, login_session_nonce)
    body += encode_field_varint(5, 1)
    body += encode_field_varint(6, 1)
    body += encode_field_varint(8, 0)
    body += encode_field_string(9, KEY_UUID)
    body += encode_field_string(10, APP_VERSION)
    body += encode_field_string(11, DEVICE_MODEL)
    body += encode_field_string(12, GPU_MODEL)
    body += encode_field_varint(13, 30)
    body += encode_field_varint(14, 1)
    body += encode_field_string(15, DEVICE_ID)
    return build_frame("9f27", body)


def do_gs_login(gs_host, gs_port, login_session):
    print("\n=== LOGIN GS ===")
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
    sock.settimeout(10)
    try:
        sock.connect((gs_host, gs_port))
        print("Connecte au GS.")
        time.sleep(0.2)

        packet = build_gs_login_packet(login_session)
        sock.sendall(packet)

        response, total = recv_all(sock, drain_seconds=3)
        print("Recu " + str(total) + " octets du GS.")
        print("Reponse : " + response.hex())

        if total == 0:
            sock.close()
            return None

        body = response[4:]
        fields = walk_protobuf(body)
        has_error = any(fn == 99 for fn, wt, val in fields)

        if has_error:
            print("Erreur presente, login GS echoue.")
            sock.close()
            return None

        print("LOGIN GS REUSSI ! Session ouverte.")

        print("\n=== SYNCHRONISATION (config, comme le vrai client) ===")
        activity_csv_req = bytes.fromhex("1800e2340a0c61637469766974792e63737610fece8b8c06")
        sock.sendall(activity_csv_req)
        r1, t1 = recv_all(sock, drain_seconds=3)
        print("activity.csv : recu " + str(t1) + " octets.")

        ping1 = bytes.fromhex("0400a127")
        sock.sendall(ping1)
        r2, t2 = recv_all(sock, drain_seconds=2)
        print("ping : recu " + str(t2) + " octets.")

        activity_cal_req = bytes.fromhex("2100e2340a1561637469766974795f63616c656e6461722e637376109adbab8402")
        sock.sendall(activity_cal_req)
        r3, t3 = recv_all(sock, drain_seconds=3)
        print("activity_calendar.csv : recu " + str(t3) + " octets.")

        return sock

    except ConnectionResetError:
        print("GS a reinitialise la connexion.")
        return None


# ============================================================================
# Decodage des ressources
# ============================================================================

CURRENCY_NAMES = {
    1: "Emoney", 2: "Oil", 3: "Nourriture (Food)", 4: "Bois (Wood)",
    5: "Acier/Pierre (Steel)", 16: "Gold", 17: "TechnologyPoint",
}


def decode_resource_set(data):
    fields = walk_protobuf(data)
    resources = []
    for fn, wt, val in fields:
        if fn == 1 and wt == "bytes":
            res_fields = walk_protobuf(val)
            res = {}
            for rfn, rwt, rval in res_fields:
                if rfn == 1:
                    res["res_type"] = rval
                elif rfn == 2:
                    res["sub_type"] = rval
                elif rfn == 3:
                    res["value"] = rval
                elif rfn == 4:
                    res["luck_val"] = rval
                elif rfn == 5:
                    res["tag"] = rval
            resources.append(res)
    return resources


# ============================================================================
# Actions de jeu
# ============================================================================

def collect_privilege_escrow_reward(sock):
    print("\n=== ACTION : Collecte des gains hors ligne (PrivilegeEscrow) ===")
    packet = build_frame("2434", b"")
    sock.sendall(packet)

    response, total = recv_all(sock, drain_seconds=3)
    print("Recu " + str(total) + " octets.")
    print("Reponse brute : " + response.hex())

    if total == 0:
        print("Aucune reponse.")
        return

    body = find_message_of_type(response, 13349)  # kMsgGS2CLReceivePrivilegeEscrowRewardReply
    if body is None:
        print("Message de reponse non trouve.")
        return

    fields = walk_protobuf(body)
    has_error = False
    collected_any = False
    for fn, wt, val in fields:
        if fn == 99:
            has_error = True
            print("Erreur, code : " + str(val))
        elif fn == 1 and wt == "bytes":
            resources = decode_resource_set(val)
            print("\nRessources recuperees :")
            for r in resources:
                print("  " + str(r))
                res_name = CURRENCY_NAMES.get(r.get("res_type"), "Type " + str(r.get("res_type")))
                log_event("Gains hors ligne : +" + str(r.get("value", 0)) + " " + res_name)
                collected_any = True

    if not has_error and not collected_any:
        log_event("Gains hors ligne : rien a collecter cette fois.")
    elif not has_error:
        print("\nCollecte reussie !")


def check_collectible_resources(sock):
    print("\n=== VERIFICATION : Ressources pretes a collecter ===")
    packet = build_frame("ef28", b"")
    sock.sendall(packet)
    response, total = recv_all(sock, drain_seconds=3)
    print("Recu " + str(total) + " octets.")
    print("Reponse brute : " + response.hex())

    if total == 0:
        print("Aucune reponse.")
        return []

    body = find_message_of_type(response, 10480)  # kMsgGS2CLCollectInfoReply
    if body is None:
        print("Message CollectInfoReply non trouve dans la reponse.")
        return []

    fields = walk_protobuf(body)
    collectibles = []
    for fn, wt, val in fields:
        if fn == 1 and wt == "bytes":
            info_fields = walk_protobuf(val)
            info = {}
            for ifn, iwt, ival in info_fields:
                if ifn == 1:
                    info["type"] = ival
                elif ifn == 4:
                    info["store"] = ival
                elif ifn == 5:
                    info["speed"] = ival
                elif ifn == 7:
                    info["max_collection"] = ival
                elif ifn == 8:
                    info["building_id"] = ival
            if info:
                name = CURRENCY_NAMES.get(info.get("type"), "Type " + str(info.get("type")))
                print("  " + name + " : " + str(info.get("store", 0)) + " en stock (batiment " + str(info.get("building_id")) + ")")
                collectibles.append(info)

    if not collectibles:
        print("  Rien de disponible actuellement.")
    return collectibles


def collect_resource(sock, currency_type):
    name = CURRENCY_NAMES.get(currency_type, "Type " + str(currency_type))
    print("\n=== ACTION : Collecte de " + name + " ===")
    body = encode_field_varint(1, currency_type)
    packet = build_frame("f128", body)
    sock.sendall(packet)
    response, total = recv_all(sock, drain_seconds=3)
    print("Reponse brute : " + response.hex())

    if total == 0:
        print("Aucune reponse.")
        return

    reply_body = find_message_of_type(response, 10482)  # kMsgGS2CLCollectResourceReply
    if reply_body is None:
        print("Message CollectResourceReply non trouve dans la reponse.")
        return

    fields = walk_protobuf(reply_body)
    has_error = False
    value = None
    for fn, wt, val in fields:
        if fn == 99:
            has_error = True
            print("Erreur, code : " + str(val))
        elif fn == 2 and wt == "varint":
            value = val

    if has_error:
        print("Echec de la collecte.")
    else:
        log_event("Collecte de ressource : +" + str(value) + " " + name)


def decode_train_end_time(response, barrack_id):
    """Cherche un ou plusieurs messages UpdateTrainNotice (10401) dans la
    reponse et retourne le end_time (timestamp Unix) de celui qui
    correspond a barrack_id, si trouve. Ce message est souvent inclus
    automatiquement dans la reponse d'un TrainRequest reussi, ou pousse
    plus tard par le serveur - plusieurs peuvent arriver ensemble si tu as
    plusieurs casernes actives."""
    notices = find_all_messages_of_type(response, 10401)
    for notice_body in notices:
        fields = walk_protobuf(notice_body)
        for fn, wt, val in fields:
            if fn == 1 and wt == "bytes":  # champ "work" (TrainWorkInfo)
                work_fields = walk_protobuf(val)
                work_barrack_id = None
                work_end_time = None
                for wfn, wwt, wval in work_fields:
                    if wfn == 7:  # barrack_id
                        work_barrack_id = wval
                    elif wfn == 4:  # end_time
                        work_end_time = wval
                if work_barrack_id == barrack_id and work_end_time:
                    return work_end_time
    return None


def train_troops(sock, barrack_id, army_id, count):
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
        return None

    end_time = decode_train_end_time(response, barrack_id)

    reply_body = find_message_of_type(response, 10403)  # kMsgGS2CLTrainReply
    if reply_body is None:
        print("Message TrainReply non trouve dans la reponse.")
        return end_time

    fields = walk_protobuf(reply_body)
    has_error = any(fn == 99 for fn, wt, val in fields)

    if has_error:
        error_code = next(val for fn, wt, val in fields if fn == 99)
        if error_code == 5816:
            print("Echec : une troupe est deja en cours d'entrainement dans cette")
            print("caserne (code 5816, kECArmyTraining). Normal, pas un bug -")
            print("attends la fin de l'entrainement en cours.")
        else:
            print("Echec de l'entrainement, code erreur : " + str(error_code))
    else:
        log_event("Entrainement lance : " + str(count) + "x armee " + str(army_id) +
                   " (caserne " + str(barrack_id) + ")")
        if end_time:
            remaining = end_time - int(time.time())
            print("Fin de l'entrainement dans " + str(remaining) + " secondes " +
                  "(timestamp " + str(end_time) + ").")

    return end_time


def claim_finished_training(sock, barrack_id):
    """Recupere les troupes d'un entrainement termine (equivalent au clic
    manuel sur le bouton de recuperation dans l'app). Confirme par capture
    reseau : kMsgCL2GSDealArmyRequest, ne prend que le barrack_id en
    parametre. Retourne True si la recuperation a reussi (caserne donc
    libre pour un nouvel entrainement), False sinon."""
    print("\n=== ACTION : Recuperation des troupes entrainees (caserne " +
          str(barrack_id) + ") ===")
    body = encode_field_varint(1, barrack_id)
    packet = build_frame("ac28", body)  # kMsgCL2GSDealArmyRequest = 10412
    sock.sendall(packet)
    response, total = recv_all(sock, drain_seconds=3)
    print("Reponse brute : " + response.hex())

    if total == 0:
        print("Aucune reponse.")
        return False

    reply_body = find_message_of_type(response, 10413)  # kMsgGS2CLDealArmyReply
    if reply_body is None:
        print("Message DealArmyReply non trouve dans la reponse.")
        return False

    fields = walk_protobuf(reply_body)
    has_error = any(fn == 99 for fn, wt, val in fields)

    if has_error:
        error_code = next(val for fn, wt, val in fields if fn == 99)
        print("Echec de la recuperation, code erreur : " + str(error_code))
        return False
    else:
        log_event("Troupes recuperees (caserne " + str(barrack_id) + ")")
        return True


def claim_daily_signin_reward(sock, day=1):
    """Reclame la recompense de connexion quotidienne (calendrier de sign-in).

    activity_id=43 correspond a "SignInAct" dans l'enum MallLabelType du jeu
    (confirme via dump.cs). Le parametre "day" (jour du calendrier a
    reclamer) est en revanche une estimation - a verifier/ajuster si le
    serveur renvoie une erreur de jour invalide (regarde le code d'erreur
    retourne, qui devrait indiquer le bon jour a utiliser)."""
    print("\n=== ACTION : Recompense de connexion quotidienne (jour " + str(day) + ") ===")
    body = encode_field_varint(1, 43) + encode_field_varint(2, day)
    packet = build_frame("1130", body)  # kMsgCL2GSNewMallFetchSignInRewardRequest = 12305
    sock.sendall(packet)
    response, total = recv_all(sock, drain_seconds=6)
    print("Reponse brute : " + response.hex())

    if total == 0:
        print("Aucune reponse.")
        return

    reply_body = find_message_of_type(response, 12306)  # ...Reply
    if reply_body is None:
        print("Message de reponse non trouve (probablement noye parmi des")
        print("notifications periodiques non liees). Types recus :")
        for mt, _ in split_messages(response):
            print("  type " + str(mt))
        return

    fields = walk_protobuf(reply_body)
    has_error = False
    for fn, wt, val in fields:
        if fn == 99:
            has_error = True
            print("Erreur, code : " + str(val) + " (le jour demande est peut-etre incorrect)")
        elif fn == 3 and wt == "bytes":
            resources = decode_resource_set(val)
            for r in resources:
                res_name = CURRENCY_NAMES.get(r.get("res_type"), "Type " + str(r.get("res_type")))
                log_event("Sign-in quotidien : +" + str(r.get("value", 0)) + " " + res_name)

    if not has_error:
        print("Recompense quotidienne recuperee !")


# ============================================================================
# Maintien de session
# ============================================================================

def find_all_messages_of_type(data, expected_type):
    """Comme find_message_of_type mais retourne TOUTES les occurrences
    (utile pour les notifications qui peuvent arriver en plusieurs
    exemplaires, comme les mises a jour de taches)."""
    return [body for msg_type, body in split_messages(data) if msg_type == expected_type]


def claim_task_reward(sock, task_id):
    """Reclame la recompense d'une tache terminee (statut kTaskStatusAward=2)."""
    print("\n=== ACTION : Reclamation de la tache #" + str(task_id) + " ===")
    body = encode_field_varint(1, task_id)
    packet = build_frame("e72d", body)  # kMsgCL2GSTaskPeriodGetTaskRewardRequest = 11751
    sock.sendall(packet)
    response, total = recv_all(sock, drain_seconds=3)

    if total == 0:
        print("Aucune reponse.")
        return

    reply_body = find_message_of_type(response, 11752)  # ...Reply
    if reply_body is None:
        print("Reponse non trouvee.")
        return

    fields = walk_protobuf(reply_body)
    has_error = False
    for fn, wt, val in fields:
        if fn == 99:
            has_error = True
            print("Erreur, code : " + str(val))
        elif fn == 2 and wt == "bytes":
            resources = decode_resource_set(val)
            for r in resources:
                res_name = CURRENCY_NAMES.get(r.get("res_type"), "Type " + str(r.get("res_type")))
                log_event("Tache #" + str(task_id) + " reclamee : +" + str(r.get("value", 0)) + " " + res_name)

    if not has_error:
        print("Tache reclamee avec succes !")


def scan_and_claim_tasks_in_data(sock, response):
    """Cherche des TaskPeriodUpdateNotice (11749) dans un buffer deja recu
    (par exemple la reponse d'un keepalive) et reclame automatiquement
    celles au statut 'Award' (terminee, recompense en attente). Reutilisable
    partout ou on recoit des donnees du serveur, pas seulement juste apres
    le login - une quete peut se terminer a tout moment pendant que le bot
    tourne."""
    task_notices = find_all_messages_of_type(response, 11749)  # TaskPeriodUpdateNotice
    if not task_notices:
        return 0

    claimed_count = 0
    for notice_body in task_notices:
        fields = walk_protobuf(notice_body)
        for fn, wt, val in fields:
            if fn == 1 and wt == "bytes":
                task_fields = walk_protobuf(val)
                task_id = None
                status = None
                for tfn, twt, tval in task_fields:
                    if tfn == 1:
                        task_id = tval
                    elif tfn == 2:
                        status = tval
                if task_id is not None and status == 2:  # kTaskStatusAward
                    print("\nTache #" + str(task_id) + " terminee, reclamation...")
                    claim_task_reward(sock, task_id)
                    claimed_count += 1
                    time.sleep(2)

    return claimed_count


def check_and_claim_completed_tasks(sock):
    """Version 'a la demande' : lit ce qui traine dans le buffer socket
    maintenant et reclame les taches trouvees. Utile juste apres le login,
    mais ne suffit pas seule pour capter les taches terminees plus tard -
    voir scan_and_claim_tasks_in_data() pour l'integrer a une boucle
    d'ecoute continue (deja fait dans gs_bot.py)."""
    print("\n=== VERIFICATION : Taches terminees en attente de recompense ===")

    response, total = recv_all(sock, drain_seconds=2)
    if total == 0:
        print("Rien recu pour l'instant.")
        return

    claimed_count = scan_and_claim_tasks_in_data(sock, response)
    if claimed_count == 0:
        print("Aucune tache prete a etre reclamee pour le moment.")


def check_and_claim_mail(sock):
    """Liste le courrier, repere les mails avec une piece jointe non
    reclamee (read_flag=2, kMailFlagNotExtract) et les reclame
    automatiquement (read_flag=6, kMailFlagCollect envoye dans
    MailOperatorRequest)."""
    print("\n=== VERIFICATION : Courrier avec pieces jointes ===")

    # Liste vide = on demande tout le courrier disponible
    packet = build_frame("8527", b"")  # kMsgCL2GSMailListRequest = 10117
    sock.sendall(packet)
    response, total = recv_all(sock, drain_seconds=3)

    if total == 0:
        print("Aucune reponse.")
        return

    reply_body = find_message_of_type(response, 10118)  # MailListReply
    if reply_body is None:
        print("Message MailListReply non trouve.")
        return

    fields = walk_protobuf(reply_body)
    unclaimed_ids = []
    total_mail = 0
    for fn, wt, val in fields:
        if fn == 1 and wt == "bytes":
            mail_fields = walk_protobuf(val)
            mail_id = None
            read_flag = None
            for mfn, mwt, mval in mail_fields:
                if mfn == 1:
                    mail_id = mval
                elif mfn == 10:
                    read_flag = mval
            if mail_id is not None:
                total_mail += 1
                if read_flag == 2:  # kMailFlagNotExtract
                    unclaimed_ids.append(mail_id)

    print(str(total_mail) + " mail(s) au total, " + str(len(unclaimed_ids)) +
          " avec piece jointe non reclamee.")

    if not unclaimed_ids:
        return

    body = b""
    for mail_id in unclaimed_ids:
        tag = (1 << 3) | 0
        body += encode_varint(tag) + encode_varint(mail_id)
    body += encode_field_varint(2, 6)  # read_flag = kMailFlagCollect

    packet = build_frame("8827", body)  # kMsgCL2GSMailOperatorRequest = 10120
    sock.sendall(packet)
    response, total = recv_all(sock, drain_seconds=3)

    if total == 0:
        print("Aucune reponse a la reclamation.")
        return

    reply_body = find_message_of_type(response, 10121)  # MailOperatorReply
    if reply_body is None:
        print("Message MailOperatorReply non trouve.")
        return

    fields = walk_protobuf(reply_body)
    has_error = False
    for fn, wt, val in fields:
        if fn == 99:
            has_error = True
            print("Erreur, code : " + str(val))
        elif fn == 4 and wt == "bytes":
            resources = decode_resource_set(val)
            for r in resources:
                res_name = CURRENCY_NAMES.get(r.get("res_type"), "Type " + str(r.get("res_type")))
                log_event("Courrier reclame : +" + str(r.get("value", 0)) + " " + res_name)

    if not has_error:
        print("Courrier reclame avec succes (" + str(len(unclaimed_ids)) + " mail(s)) !")


def decode_building_end_time(response, building_id):
    """Cherche un message CityBuildQueueNotice (10029) dans la reponse et
    retourne le end_time (timestamp Unix) du travail correspondant a
    building_id, si trouve. Meme principe que decode_train_end_time mais
    pour les batiments - contrairement aux troupes, aucune action de
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
    queue_index=0 par defaut (premiere file de construction disponible;
    certains comptes VIP ont plusieurs files simultanees).

    Retourne le end_time (timestamp) si trouve dans la reponse, sinon None -
    contrairement aux troupes, il n'y a pas d'action de 'recuperation'
    separee : relance simplement upgrade_building() une fois le end_time
    atteint pour le niveau suivant."""
    print("\n=== ACTION : Amelioration du batiment #" + str(building_id) + " ===")
    body = encode_field_varint(1, building_id) + encode_field_varint(2, queue_index)
    packet = build_frame("3027", body)  # kMsgCL2GSCityUpgradeBuidlingRequest = 10032
    sock.sendall(packet)
    response, total = recv_all(sock, drain_seconds=3)
    print("Reponse brute : " + response.hex())

    if total == 0:
        print("Aucune reponse.")
        return None

    end_time = decode_building_end_time(response, building_id)

    reply_body = find_message_of_type(response, 10033)  # ...Reply
    if reply_body is None:
        print("Message de reponse non trouve.")
        return end_time

    fields = walk_protobuf(reply_body)
    has_error = any(fn == 99 for fn, wt, val in fields)

    if has_error:
        error_code = next(val for fn, wt, val in fields if fn == 99)
        print("Echec de l'amelioration, code erreur : " + str(error_code))
    else:
        log_event("Amelioration lancee : batiment #" + str(building_id))
        if end_time:
            remaining = end_time - int(time.time())
            print("Fin de l'amelioration dans " + str(remaining) + " secondes " +
                  "(timestamp " + str(end_time) + ").")

    return end_time


def parse_player_attributes(response):
    """Cherche des messages PlayerAttribute (10009 - c'est le message qui
    apparait tres frequemment dans le flux, pousse en continu par le
    serveur) et retourne une liste de (type, value, action_type). Le
    'type' suit la meme numerotation que CurrencyType. Ce message sert au
    client a synchroniser en temps reel les totaux de ressources du
    joueur (parmi d'autres attributs)."""
    results = []
    for msg_type, body in split_messages(response):
        if msg_type != 10009:
            continue
        fields = walk_protobuf(body)
        for fn, wt, val in fields:
            if fn == 1 and wt == "bytes":
                attr_fields = walk_protobuf(val)
                atype = None
                avalue = None
                aaction = None
                for afn, awt, aval in attr_fields:
                    if afn == 1:
                        atype = aval
                    elif afn == 3:
                        avalue = aval
                    elif afn == 4:
                        aaction = aval
                if atype is not None and avalue is not None:
                    results.append((atype, avalue, aaction))
    return results


class ResourceTracker:
    """Garde en memoire les derniers totaux connus de chaque ressource, et
    estime un taux de production par heure en observant l'evolution dans
    le temps (le jeu ne semble pas transmettre de taux de production tout
    fait - CollectInfo, qui devrait le donner via son champ 'speed',
    revient vide sur ce compte, probablement a cause de la collecte
    automatique des villageois). L'estimation se base sur l'historique
    recent des valeurs observees, pas sur une donnee officielle du jeu -
    a prendre comme approximation."""

    def __init__(self, history_window_seconds=600):
        self.history_window = history_window_seconds
        self.history = {}  # type -> liste de (timestamp, value)
        self.latest = {}   # type -> valeur la plus recente connue

    def update(self, attributes):
        now = time.time()
        for atype, avalue, aaction in attributes:
            self.latest[atype] = avalue
            self.history.setdefault(atype, []).append((now, avalue))
            cutoff = now - self.history_window
            self.history[atype] = [(t, v) for t, v in self.history[atype] if t >= cutoff]

    def estimated_rate_per_hour(self, atype):
        points = self.history.get(atype, [])
        if len(points) < 2:
            return None
        t_first, v_first = points[0]
        t_last, v_last = points[-1]
        elapsed_hours = (t_last - t_first) / 3600
        if elapsed_hours <= 0:
            return None
        return (v_last - v_first) / elapsed_hours

    def print_summary(self):
        print("\n=== RESSOURCES ACTUELLES ===")
        if not self.latest:
            print("  Aucune donnee recue pour l'instant.")
            return
        for atype in sorted(self.latest):
            name = CURRENCY_NAMES.get(atype, "Type " + str(atype))
            value = self.latest[atype]
            rate = self.estimated_rate_per_hour(atype)
            line = "  " + name + " : " + str(value)
            if rate is not None and abs(rate) >= 1:
                sign = "+" if rate >= 0 else ""
                line += "  (" + sign + str(int(rate)) + "/h estime)"
            print(line)


def heartbeat_loop(sock, interval_seconds=5):
    """Envoie le vrai message de maintien de session (kMsgCL2GSKeepLiveRequest
    = 10006, corps vide) confirme par capture reseau reelle. Les anciennes
    valeurs utilisees ici (types 10145 EnterGameRequest et 13999
    GetTotalChargeRequest) etaient incorrectes - ce ne sont pas des
    keepalives mais de vraies actions ponctuelles, ce qui expliquait
    probablement les coupures de connexion apres 1-2 minutes."""
    print("\n=== MAINTIEN DE SESSION (heartbeat, intervalle=" + str(interval_seconds) + "s) ===")
    print("Ctrl+C pour arreter.")
    keepalive = bytes.fromhex("04001627")  # kMsgCL2GSKeepLiveRequest = 10006
    try:
        while True:
            time.sleep(interval_seconds)
            sock.sendall(keepalive)
            response, total = recv_all(sock, drain_seconds=2)
            reply = find_message_of_type(response, 10007)  # kMsgGS2CLKeepLiveReply
            status = "OK" if reply is not None else ("(" + str(total) + " octets, type inattendu)" if total else "(rien)")
            print("Keepalive envoye, reponse : " + status)
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
