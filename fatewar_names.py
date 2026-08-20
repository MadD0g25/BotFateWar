"""Tables de traduction des noms de heros et de batiments, extraites du
fichier de configuration reel du jeu (string_fr.json, obtenu via
AssetStudio - merci a l'utilisateur pour cette extraction complete !).

HERO_NAMES : cle = hero_id (instance, ex: 100011), valeur = nom affiche.
Correspond au champ "hero1"/"hero2" de MarchCommand (fatewar_actions_battle.py)
et aux hero_id utilises pour l'amelioration de talent (fatewar_actions_misc.py).

BUILDING_NAMES : cle = building "type" (PAS l'id d'instance - voir
get_city_buildings() dans fatewar_resources.py), valeur = nom affiche.

ATTENTION : ces tables ne couvrent que les entrees presentes chez
l'utilisateur au moment de l'extraction (43 heros, 44 batiments) - pas
forcement exhaustif pour tous les heros/batiments existants dans le jeu."""

HERO_NAMES = {
    5025: "Baleygr",
    5033: "Draugr",
    5040: "Collectionneur de pierres magiques",
    100001: "Baldur",
    100002: "Reynald",
    100003: "Elia",
    100004: "Champion Berserker Corrompu",
    100005: "Champion Cavalier Corrompu",
    100006: "Champion de Soutien Corrompu",
    100007: "Voll",
    100008: "Erin",
    100009: "Aelfwine",
    100010: "Linda",
    100011: "Rex",
    100012: "Elena",
    100013: "Kalthas",
    100014: "Vista",
    100015: "Aria",
    100016: "Selena",
    100017: "Reid",
    100018: "Karl",
    100019: "Sara",
    100020: "Kiana",
    100021: "Skerne",
    100022: "Sigrid",
    100023: "Helda",
    100024: "Erik",
    100026: "Freyja",
    100027: "Reinhardt",
    100028: "Kaira",
    100030: "Wukong",
    100031: "Amaterasu",
    100032: "Yi Sun-sin",
    100033: "Iris",
    100037: "Roro",
    100038: "Arthur",
    100039: "Aska",
    100040: "Farhad",
    100041: "Morgane la Fée",
    100042: "Jeanne",
    100043: "Petra",
    100044: "Sylvan",
    100045: "Oda Nobunaga",
}


BUILDING_NAMES = {
    1000: "Hall du chef de tribu",
    1001: "Tombeau",
    1002: "Mur",
    1003: "Hall de tribu",
    1008: "Hall de guerre",
    1009: "Entrepôt",
    1012: "Hutte des miracles",
    1013: "Tour de garde",
    1028: "Camps d'éclaireurs",
    1029: "Tour de guet",
    1031: "Dépôt de tribu",
    1032: "Infirmerie",
    1034: "Camp des berserkers",
    1035: "Camp Lanceurs de haches",
    1036: "Camp des cavaliers",
    1037: "Camp Chevauch. de bêtes",
    1038: "Atelier d'équipement",
    1041: "Maison",
    1042: "Maison de commerce",
    1043: "Atelier de forge",
    1044: "Atelier d'artisan",
    1045: "Cuisine commune",
    1046: "Camp des mercenaires",
    1047: "Temple de Valkyrheim",
    1048: "Cercle de Woden",
    1049: "Tableau d'affichage",
    1050: "Stèle de héros",
    1051: "Toilettes",
    1052: "Bains publics",
    1053: "Boutique",
    1200: "Tour de baliste",
    1201: "Tour de catapulte",
    1202: "Tour d'arcane",
    1999: "Bâtiment de constructeur",
    2000: "Musée",
    2001: "Manoir du chef",
    2002: "Barrière fluviale",
    2003: "Puit",
    2004: "Alarme",
    2010: "Totem de troupe de guerre",
    2011: "Totem Gardiens",
    2012: "Totem Écailles noires",
    2013: "Totem Sanctuaire vert",
    2014: "Totem Voyageurs du Vent",
}