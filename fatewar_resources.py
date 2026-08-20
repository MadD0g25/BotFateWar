import time

from fatewar_core import (
    build_frame, walk_protobuf, split_messages,
    find_message_of_type, recv_all,
)

# Categories d'attributs joueur (champ "type" de PlayerAttribute), extrait
# de dump.cs (enum PlayerAttributeType). IMPORTANT : "type" est une
# CATEGORIE generale, pas un identifiant de monnaie precis - kPlayerAttrCurrency
# (1) regroupe TOUTES les monnaies confondues, la monnaie precise est dans
# le champ "sub_type" (voir CURRENCY_NAMES dans fatewar_actions_rewards.py).
# Bug corrige : le code affichait auparavant "Emoney" pour TOUT type=1 sans
# jamais regarder sub_type, et pouvait meme afficher un "faux pic" quand un
# AUTRE type d'attribut (Puissance, Armee...) partageait par coincidence
# une valeur proche de celle de la monnaie.
PLAYER_ATTRIBUTE_TYPE_NAMES = {
    0: "Aucun", 1: "Monnaie", 2: "Objet", 4: "Exp. heros", 5: "Puissance",
    6: "Exp. etoile heros", 7: "Monnaie de guilde", 8: "Monnaie du mall",
    9: "AP", 11: "Heros", 12: "Cadeau de guilde", 13: "Score quotidien",
    14: "Armee", 15: "Blesses", 16: "Equipement", 17: "Apparence de marche",
    19: "Exp. honneur", 20: "Carte d'or honneur", 22: "Tete", 23: "Cadre",
    24: "Technologie", 25: "Skin", 26: "Pass avance",
    27: "Batiment decoratif", 28: "Statistiques", 29: "Bulle de chat",
    30: "Titre individuel", 31: "Score activite jalon",
    32: "Score guilde activite jalon", 33: "Battle pass (paye)",
    34: "Pass public (paye)", 35: "Skin de marche", 36: "Joyau",
    37: "Reliques", 38: "Mini-jeu", 39: "Tirage activite", 40: "Fonds",
    41: "Dette", 42: "Gemmes payees", 43: "Carte de temps",
    44: "Equipement de heros", 45: "Obtention equipement de heros",
    54: "Cadeau homme riche", 80: "Paiement caravane commerciale",
    1003: "Statut", 1004: "Activite du mall", 2001: "Nombre d'ennemis tues",
}

# Table de correspondance type_code -> ressource, trouvee empiriquement en
# comparant les valeurs de CityInfoReply avec l'affichage en jeu (a
# completer/corriger si de nouveaux type_code apparaissent) :
#   2104 -> Bois (Wood)
#   2404 -> Nourriture (Food)
#   2504 -> Connaissances (Knowledge/Recherche)
#   2204/2304 -> Pierre (Stone) et Fer (Iron), dans un ordre incertain -
#   les deux valeurs reelles etaient trop proches (316K vs 317K) pour
#   trancher avec certitude sur une seule comparaison ; a corriger si tu
#   remarques que c'est invers ete plus tard.
RESOURCE_TYPE_CODES = {
    2104: "Bois (Wood)",
    2204: "Pierre (Stone) ?",
    2304: "Fer (Iron) ?",
    2404: "Nourriture (Food)",
    2504: "Connaissances (Knowledge)",
}

# Conversion entre les type_code de CityInfoReply (ci-dessus) et les
# res_type "simples" utilises dans TROOP_RESOURCE_COSTS (fatewar_troop_data.py,
# extraite directement du fichier de configuration du jeu - meme
# numerotation que CurrencyType : 2=Pierre, 3=Nourriture, 4=Bois, 5=Fer,
# 17=Connaissances). Necessaire pour calculer le max de troupes
# entrainables a partir des ressources actuelles.
TYPE_CODE_TO_CURRENCY = {
    2104: 4,   # Bois
    2204: 2,   # Pierre
    2304: 5,   # Fer
    2404: 3,   # Nourriture
    2504: 17,  # Connaissances
}


def parse_player_attributes(response):
    """Cherche des messages PlayerAttribute (10009) et retourne une liste
    de (type, sub_type, value, action_type). "type" est une CATEGORIE
    d'attribut (voir PLAYER_ATTRIBUTE_TYPE_NAMES), "sub_type" precise
    LEQUEL au sein de cette categorie (ex: type=1/Monnaie + sub_type=1 =
    Emoney precisement, voir CURRENCY_NAMES). Ce message sert au client a
    synchroniser en temps reel divers attributs du joueur (pas
    exclusivement des ressources - a utiliser avec prudence, voir
    get_city_resources() pour les vrais totaux de ressources)."""
    results = []
    for msg_type, body in split_messages(response):
        if msg_type != 10009:
            continue
        fields = walk_protobuf(body)
        for fn, wt, val in fields:
            if fn == 1 and wt == "bytes":
                attr_fields = walk_protobuf(val)
                atype = None
                asubtype = None
                avalue = None
                aaction = None
                for afn, awt, aval in attr_fields:
                    if afn == 1:
                        atype = aval
                    elif afn == 2:
                        asubtype = aval
                    elif afn == 3:
                        avalue = aval
                    elif afn == 4:
                        aaction = aval
                if atype is not None and avalue is not None:
                    results.append((atype, asubtype, avalue, aaction))
    return results


class ResourceTracker:
    """Garde en memoire les derniers totaux connus de chaque attribut
    PlayerAttribute, et estime un taux d'evolution par heure en observant
    les changements dans le temps. Approximation empirique, pas une
    donnee officielle du jeu.

    CORRIGE : le champ "type" de PlayerAttribute est une CATEGORIE
    generale (kPlayerAttrCurrency=1 regroupe TOUTES les monnaies, par
    exemple), pas un identifiant precis - c'est le champ "sub_type" qui
    precise LEQUEL au sein de la categorie. L'ancien code ignorait
    sub_type et affichait tout type=1 comme "Emoney", ce qui expliquait
    aussi le "faux pic" observe autrefois (un AUTRE type d'attribut,
    comme Puissance ou Armee, partageait occasionnellement une valeur
    dans la meme fourchette). Desormais suivi par (type, sub_type)."""

    def __init__(self, history_window_seconds=600):
        self.history_window = history_window_seconds
        self.history = {}  # (type,sub_type) -> liste de (timestamp, value)
        self.latest = {}   # (type,sub_type) -> valeur la plus recente connue

    def update(self, attributes):
        now = time.time()
        for atype, asubtype, avalue, aaction in attributes:
            key = (atype, asubtype)
            self.latest[key] = avalue
            self.history.setdefault(key, []).append((now, avalue))
            cutoff = now - self.history_window
            self.history[key] = [(t, v) for t, v in self.history[key] if t >= cutoff]

    def estimated_rate_per_hour(self, key):
        points = self.history.get(key, [])
        if len(points) < 2:
            return None
        t_first, v_first = points[0]
        t_last, v_last = points[-1]
        elapsed_hours = (t_last - t_first) / 3600
        if elapsed_hours <= 0:
            return None
        return (v_last - v_first) / elapsed_hours

    def print_summary(self):
        from fatewar_actions_rewards import CURRENCY_NAMES
        print("\n=== ATTRIBUTS JOUEUR (PlayerAttribute) ===")
        if not self.latest:
            print("  Aucune donnee recue pour l'instant.")
            return
        for key in sorted(self.latest, key=lambda k: (k[0], k[1] or 0)):
            atype, asubtype = key
            category = PLAYER_ATTRIBUTE_TYPE_NAMES.get(atype, "Type " + str(atype))
            if atype == 1:  # kPlayerAttrCurrency -> sub_type = vraie monnaie
                name = CURRENCY_NAMES.get(asubtype, category + " (sous-type " + str(asubtype) + ")")
            else:
                name = category
                if asubtype:
                    name += " (sous-type " + str(asubtype) + ")"
            value = self.latest[key]
            rate = self.estimated_rate_per_hour(key)
            line = "  " + name + " : " + str(value)
            if rate is not None and abs(rate) >= 1:
                sign = "+" if rate >= 0 else ""
                line += "  (" + sign + str(int(rate)) + "/h estime)"
            print(line)


def get_city_resources(sock):
    """Interroge CityInfoRequest et en extrait les vrais totaux de
    ressources actuels (bois, nourriture, connaissances confirmes). La
    reponse arrive generalement emballee dans un CompressedMessage (zlib) -
    decompression geree automatiquement par find_message_of_type. Retourne
    un dict {type_code: valeur}."""
    print("\n=== RECUPERATION : Totaux de ressources (CityInfo) ===")
    packet = build_frame("2b27", b"")  # kMsgCL2GSCityInfoRequest = 10027
    sock.sendall(packet)
    # Delai plus genereux que les autres actions : la reponse est souvent
    # une grosse structure compressee (CityInfoReply), qui peut prendre
    # plus de temps a arriver completement qu'un simple accuse de reception,
    # surtout en pleine boucle active avec d'autres messages qui circulent.
    response, total = recv_all(sock, drain_seconds=6)
    print("Recu " + str(total) + " octets au total.")

    if total == 0:
        print("Aucune reponse.")
        return {}

    decompressed = find_message_of_type(response, 10028)  # kMsgGS2CLCityInfoReply
    if decompressed is None:
        print("Message CityInfoReply non trouve (meme apres tentative de decompression).")
        print("Types de messages recus dans cette reponse :")
        for mt, body in split_messages(response):
            print("  type " + str(mt) + " (taille=" + str(len(body)) + ")")
        return {}

    # "micro_world" = champ 4 de CityInfoReply ; a l'interieur, une liste
    # d'entrees avec un type_code (champ 1) et une valeur imbriquee assez
    # profondement (champ 2 -> champ 21 -> champ 2).
    top_fields = walk_protobuf(decompressed)
    resources = {}
    for fn, wt, val in top_fields:
        if fn != 4 or wt != "bytes":
            continue
        for ifn, iwt, ival in walk_protobuf(val):
            if iwt != "bytes":
                continue
            entry_fields = walk_protobuf(ival)
            entry_dict = {f: v for f, wt2, v in entry_fields if wt2 == "varint"}
            type_code = entry_dict.get(1)
            for ffn, fwt, fval in entry_fields:
                if ffn == 2 and fwt == "bytes":
                    for gfn, gwt, gval in walk_protobuf(fval):
                        if gfn == 21 and gwt == "bytes":
                            for hfn, hwt, hval in walk_protobuf(gval):
                                if hfn == 2 and hwt == "varint" and hval > 1000:
                                    if type_code:
                                        resources[type_code] = hval

    print("Ressources trouvees :")
    for type_code, value in resources.items():
        name = RESOURCE_TYPE_CODES.get(type_code, "Type inconnu " + str(type_code))
        print("  " + name + " : " + str(value))

    return resources


BUILDING_STATUS_NAMES = {
    0: "Aucun", 1: "En amelioration", 2: "En attente d'activation",
    3: "Normal", 4: "En cours de suppression",
}


def get_city_buildings(sock):
    """Interroge CityInfoRequest et liste TOUS les batiments de la ville
    avec leur id/type/niveau/statut, directement depuis CityInfoReply
    (champ 1 "map" -> champ 1 "buildings"). Utile pour decouvrir
    automatiquement tes building_id sans avoir a faire une capture
    reseau manuelle pour chaque batiment que tu veux automatiser.

    ATTENTION : le "type" renvoye est un identifiant numerique interne du
    jeu - dump.cs ne contient que la STRUCTURE du code, pas les donnees
    de configuration reelles (noms/valeurs), qui vivent dans des fichiers
    d'assets separes qu'on n'a pas. Impossible donc de traduire ces
    "type" en noms lisibles ("Caserne", "Ferme"...) sans capture
    complementaire - mais ca reste tres utile pour repartir les
    batiments par groupes et reperer les IDs a utiliser."""
    buildings, _ = get_city_buildings_and_queue(sock)
    return buildings


def get_city_buildings_and_queue(sock):
    """Comme get_city_buildings(), mais recupere EN PLUS les vraies heures
    de fin des ameliorations en cours (champ 2 "queue" -> BuildQueueInfo
    -> works, dans la MEME reponse CityInfoReply - aucun appel reseau
    supplementaire necessaire). Permet de programmer precisement la
    prochaine verification au lieu de sonder betement toutes les X
    minutes, exactement comme pour les casernes.

    Retourne (buildings, queue_end_times) ou queue_end_times est un dict
    {building_id: end_time}."""
    print("\n=== RECUPERATION : Liste des batiments de la ville ===")
    packet = build_frame("2b27", b"")  # kMsgCL2GSCityInfoRequest = 10027
    sock.sendall(packet)
    response, total = recv_all(sock, drain_seconds=6)

    if total == 0:
        print("Aucune reponse.")
        return [], {}

    decompressed = find_message_of_type(response, 10028)  # kMsgGS2CLCityInfoReply
    if decompressed is None:
        print("Message CityInfoReply non trouve.")
        return [], {}

    top_fields = walk_protobuf(decompressed)
    buildings = []
    queue_end_times = {}

    for fn, wt, val in top_fields:
        if fn == 1 and wt == "bytes":
            # champ 1 = "map" (CityInfo) -> champ 1 = "buildings" (repeated)
            for ifn, iwt, ival in walk_protobuf(val):
                if ifn != 1 or iwt != "bytes":
                    continue
                b_fields = walk_protobuf(ival)
                b = {}
                for bfn, bwt, bval in b_fields:
                    if bfn == 1:
                        b["id"] = bval
                    elif bfn == 2:
                        b["type"] = bval
                    elif bfn == 3:
                        b["level"] = bval
                    elif bfn == 5:
                        b["status"] = bval
                if b:
                    buildings.append(b)
        elif fn == 2 and wt == "bytes":
            # champ 2 = "queue" (BuildQueueInfo) -> champ 1 = "works"
            # (repeated BuildWorkInfo), chacun avec building_id + end_time.
            for qfn, qwt, qval in walk_protobuf(val):
                if qfn != 1 or qwt != "bytes":
                    continue
                w_fields = walk_protobuf(qval)
                w_building_id = None
                w_end_time = None
                for wfn, wwt, wval in w_fields:
                    if wfn == 2:
                        w_building_id = wval
                    elif wfn == 4:
                        w_end_time = wval
                if w_building_id and w_end_time:
                    queue_end_times[w_building_id] = w_end_time

    print(str(len(buildings)) + " batiment(s) trouve(s), " +
          str(len(queue_end_times)) + " en cours de construction :")
    by_type = {}
    for b in buildings:
        by_type.setdefault(b.get("type"), []).append(b)

    from fatewar_names import BUILDING_NAMES
    for btype in sorted(by_type):
        entries = by_type[btype]
        name = BUILDING_NAMES.get(btype, "Type " + str(btype))
        print("  " + name + " (" + str(len(entries)) + " batiment(s)) :")
        for b in entries:
            status_name = BUILDING_STATUS_NAMES.get(b.get("status"), "?")
            extra = ""
            if b.get("id") in queue_end_times:
                extra = "  (fin: " + str(queue_end_times[b["id"]]) + ")"
            print("    id=" + str(b.get("id")) + "  niveau=" + str(b.get("level")) +
                  "  statut=" + status_name + extra)

    return buildings, queue_end_times

