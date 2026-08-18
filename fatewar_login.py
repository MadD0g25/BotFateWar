import socket
import time

from fatewar_core import (
    LS_HOST, LS_PORT,
    GAME_ID, KEY_UUID, DEVICE_ID, USER_ID,
    APP_VERSION, DEVICE_MODEL, GPU_MODEL, WEB_SESSION,
    encode_field_varint, encode_field_string, build_frame,
    walk_protobuf, find_message_of_type, recv_all,
)


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

        # Toujours afficher la reponse brute et le type de message recu -
        # sans ca, impossible de diagnostiquer un echec silencieux (par
        # exemple si le serveur renvoie une erreur au lieu du succes
        # attendu, avec une structure de champs completement differente).
        print("Reponse brute : " + response.hex())
        if len(response) >= 4:
            msg_type = int.from_bytes(response[2:4], "little")
            print("Type de message recu : " + str(msg_type) +
                  " (attendu : 10142, kMsgLS2CLLoginReply)")

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
# Maintien de session
# ============================================================================

def heartbeat_loop(sock, interval_seconds=5):
    """Envoie le vrai message de maintien de session (kMsgCL2GSKeepLiveRequest
    = 10006, corps vide) confirme par capture reseau reelle."""
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
