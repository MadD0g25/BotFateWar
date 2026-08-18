# ============================================================================
# CONFIGURATION DU BOT - c'est ici que tu modifies tout, jamais besoin de
# toucher a gs_bot.py lui-meme.
#
# Copie ce fichier vers bot_config.py et remplis-le avec tes propres
# valeurs (voir README.md pour savoir comment les trouver).
# ============================================================================

# Port sur lequel le Pi ecoute le nonce envoye par ls_login.py (iPhone).
LISTEN_PORT = 5555


# ----------------------------------------------------------------------------
# CASERNES (entrainement de troupes)
# ----------------------------------------------------------------------------
# Liste des casernes a faire tourner en parallele, chacune avec son propre
# type de troupe et sa propre quantite. Trouvees par capture reseau
# (kMsgCL2GSTrainRequest, type 10402) pendant un entrainement manuel de
# chaque type dans l'app - voir README.md pour la procedure complete.
# Ajoute/retire des entrees selon tes propres casernes. Mets "count": "max"
# pour laisser le bot trouver automatiquement la plus grande quantite
# possible a chaque cycle (teste plusieurs quantites decroissantes sans
# risque, voir train_max_troops dans fatewar_actions_troops.py) - evite
# d'avoir a ajuster ce fichier a chaque fois que tes ressources augmentent.
TRAINING_SLOTS = [
    # {"barrack_id": TON_ID, "army_id": TON_ARMY_ID, "count": "max"},
]


# ----------------------------------------------------------------------------
# BATIMENTS
# ----------------------------------------------------------------------------
# Amelioration automatique de TOUS les batiments disponibles. A chaque
# cycle, le bot liste tous tes batiments (get_city_buildings), et lance
# l'amelioration de chacun de ceux au statut "Normal" (libre, pas deja en
# cours). Comme plusieurs batiments partagent les memes ressources,
# certains echoueront naturellement par manque de ressources tant que les
# autres n'ont pas fini - pas grave, ils seront retentes au prochain cycle.
AUTO_UPGRADE_ALL_BUILDINGS = False

# Optionnel : IDs de batiments a ne jamais ameliorer automatiquement
# (par exemple si tu veux garder le controle manuel sur un batiment
# precis). Vide par defaut = tout est eligible.
EXCLUDED_BUILDING_IDS = []


# ----------------------------------------------------------------------------
# GUILDE
# ----------------------------------------------------------------------------
# Interrupteur general pour toutes les fonctionnalites de guilde
# (ressources, aide aux membres, cadeaux, don a la recherche). Mets a
# False si tu n'es pas encore dans une guilde - evite des tentatives
# inutiles qui ralentissent le demarrage et remplissent les logs.
ENABLE_GUILD_FEATURES = False

# Don a la recherche de guilde : optionnel, desactive par defaut (mettre
# GUILD_TECH_ID a None pour desactiver). GUILD_TECH_ID est la recherche
# ACTUELLEMENT active pour ta guilde - change avec le temps, a mettre a
# jour manuellement de temps en temps (voir README.md). Le vrai client
# "spamme" ce don plusieurs fois d'affilee - GUILD_TECH_DONATE_TIMES
# controle combien de fois par cycle.
GUILD_TECH_ID = None
GUILD_TECH_LEVEL = 1
GUILD_TECH_DONATE_TIMES = 10


# ----------------------------------------------------------------------------
# COLLECTE CITOYENNE ET FERME
# ----------------------------------------------------------------------------
# Collecte citoyenne (correspond a l'ecran "Details fiscaux") : optionnel,
# liste vide par defaut. collect_id est propre a ton compte - trouve par
# capture reseau (voir README.md).
CITIZEN_COLLECT_IDS = []

# Recolte de ferme (mini-jeu separe) : optionnel, liste vide par defaut.
# pen_id est propre a ton compte.
FARM_PEN_IDS = []


# ----------------------------------------------------------------------------
# TDCITY (exploration de parcelles / combats de zone)
# ----------------------------------------------------------------------------
# Exploration automatique TDCity : optionnel, desactive par defaut (mettre
# TD_CITY_AREA_ID a None pour desactiver). Les cases s'explorent dans
# l'ordre croissant - le bot avance automatiquement (grid, grid+1, ...) et
# s'arrete d'avancer en cas de defaite (la case en cours reste bloquante,
# le bot retentera au prochain cycle plutot que de sauter des cases).
# TD_CITY_MAX_GRID (optionnel) arrete l'avancee une fois cette case
# atteinte - laisse a None pour ne jamais s'arreter.
TD_CITY_AREA_ID = None
TD_CITY_STARTING_GRID = 1
TD_CITY_MAX_GRID = None


# ----------------------------------------------------------------------------
# DELAIS DE REESSAI (avance - generalement pas besoin d'y toucher)
# ----------------------------------------------------------------------------
RETRY_STILL_TRAINING = 60       # heure de fin inconnue, on retente prudemment
RETRY_INSUFFICIENT_RES = 300    # pas assez de ressources, ca prend du temps a s'accumuler
RETRY_GENERIC_ERROR = 60
