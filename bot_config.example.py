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
# pour laisser le bot calculer automatiquement la plus grande quantite
# possible a chaque cycle, a partir des vraies donnees de configuration du
# jeu (voir fatewar_troop_data.py) - evite d'avoir a ajuster ce fichier a
# chaque fois que tes ressources ou ton niveau de caserne augmentent.
TRAINING_SLOTS = [
    # {"barrack_id": TON_ID, "army_id": TON_ARMY_ID, "count": "max"},
]


# ----------------------------------------------------------------------------
# BATIMENTS
# ----------------------------------------------------------------------------
# Amelioration automatique de TOUS les batiments disponibles. A chaque
# cycle, le bot verifie d'abord combien d'ameliorations sont DEJA en cours
# (statut "Upgrading"), et ne lance de nouvelles ameliorations que sur les
# places encore libres dans la limite de MAX_CONCURRENT_BUILDING_UPGRADES -
# evite de spammer des tentatives vouees a l'echec (erreur "file occupee").
AUTO_UPGRADE_ALL_BUILDINGS = False

# Nombre de files de construction simultanees autorisees par le jeu (VIP/
# niveau du compte). Observe a 2 en pratique - augmente cette valeur si tu
# debloques plus de files.
MAX_CONCURRENT_BUILDING_UPGRADES = 2

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
# RECHERCHE PERSONNELLE (arbre technologique de ta ville)
# ----------------------------------------------------------------------------
# Optionnel, desactive par defaut (mettre PERSONAL_TECH_ID a None). C'est
# la recherche ACTUELLEMENT selectionnee dans ton arbre - change avec ta
# progression, a mettre a jour manuellement de temps en temps.
PERSONAL_TECH_ID = None

# Recompense de chapitre d'histoire : actif par defaut, aucun risque
# (bouton "tout reclamer" sans parametre).
CLAIM_CHAPTER_AWARD = True

# Talents de heros a ameliorer automatiquement (bouton "recommande" de
# l'app) : optionnel, liste vide par defaut. hero_id propre a ton compte
# (voir fatewar_names.py pour la table de noms connus).
HERO_TALENT_IDS = []

# Taches quotidiennes a reclamer : optionnel, liste vide par defaut (les
# task_id changent chaque jour, pas encore de decouverte automatique).
DAILY_TASK_IDS = []


# ----------------------------------------------------------------------------
# COMBATS AUTOMATIQUES CONTRE MONSTRES CORROMPUS
# ----------------------------------------------------------------------------
# Reproduit le flow manuel : loupe -> recherche par niveau -> ATQ ->
# rassemblement des troupes -> lancer. Une seule requete de recherche
# (par niveau choisi) donne directement la cible a attaquer - confirme
# par capture reseau reelle, bien plus fiable qu'une notification radar
# passive. Optionnel, desactive par defaut - ATTENTION, action la plus
# sensible du bot (envoie de vraies troupes), verifie bien ta config
# avant d'activer.
AUTO_ATTACK_MONSTERS = False

# Niveau de Corrompu a rechercher (correspond au curseur "Niveau" dans
# l'app). Augmente-le au fur et a mesure que tes troupes montent en
# puissance.
MONSTER_ATTACK_LEVEL = 5

# Heros a envoyer sur chaque attaque - propres a ton compte, trouves par
# capture reseau (kMsgCL2GSCreateMarchRequest) ou par nom via AssetStudio
# (voir fatewar_names.py et le README pour la procedure).
BATTLE_HERO1 = None
BATTLE_HERO2 = None

# Composition de troupes a envoyer sur chaque attaque - deux modes :
#
# MODE AUTOMATIQUE (recommande) : laisse BATTLE_TROOPS vide et renseigne
# BATTLE_AUTO_TROOP_ARMY_ID - le bot calcule automatiquement la quantite
# recommandee pour le niveau attaque (MONSTER_ATTACK_LEVEL), extraite de
# la vraie config du jeu (fatewar_troop_data.py, correspond au texte
# "Troupe recommandee" affiche dans l'app). Un seul type de troupe.
BATTLE_AUTO_TROOP_ARMY_ID = None

# MODE MANUEL : composition fixe, plusieurs types de troupes possibles.
# Utilise seulement si BATTLE_AUTO_TROOP_ARMY_ID est None. ATTENTION :
# contrairement a l'entrainement, il n'y a pas de mode "max" ici - choisis
# une quantite qui laisse suffisamment de troupes de defense en ville.
BATTLE_TROOPS = []


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
