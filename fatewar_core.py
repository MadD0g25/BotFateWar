import socket
import struct
import time
import json
import os
import sys
import zlib
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
DEBUG_LOG_FILE = "fatewar_debug.log"

COMPRESSED_MESSAGE_TYPE = 14028  # kMsgGS2CLCompressedMessage


# ============================================================================
# Logging complet (debug) et journal des evenements notables
# ============================================================================

class _TeeWithTimestamp:
    """Duplique tout ce qui est affiche (print) vers un fichier, avec un
    horodatage ajoute au debut de chaque ligne. Permet d'avoir une trace
    complete et partageable de tout ce que fait le bot, pas seulement les
    evenements de collecte (contrairement a log_event qui ne capture que
    les succes notables)."""

    def __init__(self, filename):
        self.terminal = sys.stdout
        self.file = open(filename, "a", encoding="utf-8", buffering=1)
        self._line_start = True

    def write(self, message):
        self.terminal.write(message)
        for i, part in enumerate(message.split("\n")):
            if i > 0:
                self.file.write("\n")
                self._line_start = True
            if part == "":
                continue
            if self._line_start:
                timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                self.file.write("[" + timestamp + "] ")
                self._line_start = False
            self.file.write(part)

    def flush(self):
        self.terminal.flush()
        self.file.flush()


def enable_full_debug_log(filename=DEBUG_LOG_FILE):
    """Active la capture complete de tout ce qui s'affiche a l'ecran vers
    un fichier (avec horodatage par ligne). A appeler une seule fois, au
    tout debut du script principal."""
    if not isinstance(sys.stdout, _TeeWithTimestamp):
        sys.stdout = _TeeWithTimestamp(filename)


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


# ============================================================================
# Etat persistant (reprise apres plantage)
# ============================================================================

def load_state():
    """Charge l'etat persistant depuis STATE_FILE. Permet au bot de
    reprendre intelligemment apres un plantage/redemarrage. Retourne un
    dict vide si le fichier n'existe pas encore ou est invalide."""
    if not os.path.exists(STATE_FILE):
        return {}
    try:
        with open(STATE_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {}


def save_state(state):
    """Sauvegarde l'etat persistant sur disque."""
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
    """Cherche un message du type attendu dans le buffer. Si non trouve
    directement, verifie aussi s'il n'a pas ete emballe dans un
    CompressedMessage generique (type 14028) - le serveur compresse en
    zlib les reponses volumineuses (CityInfoReply notamment), et le
    contenu decompresse correspond directement au corps du message
    attendu (pas un nouveau message complet avec son propre entete)."""
    for msg_type, body in split_messages(data):
        if msg_type == expected_type:
            return body

    compressed_body = None
    for msg_type, body in split_messages(data):
        if msg_type == COMPRESSED_MESSAGE_TYPE:
            compressed_body = body
            break

    if compressed_body is not None:
        idx = compressed_body.find(b"\x78\x9c")
        if idx != -1:
            try:
                return zlib.decompress(compressed_body[idx:])
            except Exception:
                return None
    return None


def find_all_messages_of_type(data, expected_type):
    """Comme find_message_of_type mais retourne TOUTES les occurrences
    (utile pour les notifications qui peuvent arriver en plusieurs
    exemplaires, comme les mises a jour de taches)."""
    return [body for msg_type, body in split_messages(data) if msg_type == expected_type]


def recv_all(sock, drain_seconds=3, max_total_seconds=None):
    """Lit tout ce qui arrive sur le socket jusqu'a un silence de
    drain_seconds. IMPORTANT : sans limite absolue, une reponse envoyee en
    petits paquets espaces de MOINS que drain_seconds pourrait faire
    trainer cette fonction bien plus longtemps que prevu (chaque nouveau
    paquet relance le compte a rebours) - au risque de depasser la
    patience du serveur lui-meme et de provoquer une coupure de connexion
    (observe en pratique sur une grosse reponse CityInfoReply : 57
    secondes d'attente au lieu des ~9s habituelles, suivi d'un reset).
    max_total_seconds plafonne le temps total, peu importe les paquets
    recus entre-temps - par defaut, 3x drain_seconds (large marge sans
    etre illimite)."""
    if max_total_seconds is None:
        max_total_seconds = drain_seconds * 3
    sock.settimeout(drain_seconds)
    chunks = []
    total = 0
    start = time.time()
    try:
        while True:
            if time.time() - start > max_total_seconds:
                break
            data = sock.recv(65536)
            if not data:
                break
            chunks.append(data)
            total += len(data)
    except socket.timeout:
        pass
    return b"".join(chunks), total
