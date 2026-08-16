# ============================================================================
# Configuration du bot Fate War
# ============================================================================
# Copie ce fichier vers "config.py" et renseigne tes propres valeurs.
#
# Comment recuperer chaque valeur (voir README.md pour le detail complet
# de la procedure) :
#
#  1. Utilise un outil de capture reseau HTTPS sur ton telephone
#     (ex: un sniffer avec certificat MITM installe) pendant que tu ouvres
#     l'app Fate War normalement.
#
#  2. Cherche un appel vers :
#     https://apis-dsa.iggapis.com/ums/member/binding?access_token=...
#     -> le parametre "access_token" est ta valeur WEB_SESSION
#
#  3. Decode ce token JWT (format standard, 3 parties separees par des
#     points, partie centrale encodee en base64) pour trouver :
#       - "sub"  -> USER_ID (nombre)
#       - "key"  -> KEY_UUID (format UUID)
#
#  4. Cherche dans les logs de l'app (appels vers un domaine se terminant
#     par "/Log") le parametre "device_id" -> DEVICE_ID
#
#  5. GAME_ID, APP_VERSION, DEVICE_MODEL et GPU_MODEL sont visibles en
#     clair dans le tout premier message envoye par l'app au serveur de
#     jeu (port 12042 ou 12040), capturable avec tcpdump/Wireshark.
# ============================================================================

GAME_ID = "11570603034"

KEY_UUID = "00000000-0000-0000-0000-000000000000"
DEVICE_ID = "00000000-0000-0000-0000-000000000000"
USER_ID = 0

APP_VERSION = "1.2.20"
DEVICE_MODEL = "iPhone16,2"
GPU_MODEL = "Apple A17 Pro GPU"

WEB_SESSION = "COLLE_TON_ACCESS_TOKEN_ICI"
