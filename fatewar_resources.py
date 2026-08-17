import time

from fatewar_core import (
    build_frame, walk_protobuf, split_messages,
    find_message_of_type, recv_all,
)

# Table de correspondance type_code -> ressource, trouvee empiriquement en
# comparant les valeurs de CityInfoReply avec l'affichage en jeu (a
# completer/corriger si de nouveaux type_code apparaissent) :
#   2104 -> Bois (Wood)
#   2404 -> Nourriture (Food)
#   2504 -> Connaissances (Knowledge/Recherche)
RESOURCE_TYPE_CODES = {
    2104: "Bois (Wood)",
    2404: "Nourriture (Food)",
    2504: "Connaissances (Knowledge)",
}


def parse_player_attributes(response):
    """Cherche des messages PlayerAttribute (10009) et retourne une liste
    de (type, value, action_type). Ce message sert au client a
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
    """Garde en memoire les derniers totaux connus de chaque attribut
    PlayerAttribute, et estime un taux d'evolution par heure en observant
    les changements dans le temps. Approximation empirique, pas une donnee
    officielle du jeu.

    ATTENTION : le champ 'type' de PlayerAttribute ne semble pas etre
    exactement le meme enum que CurrencyType - il couvre probablement
    d'autres statistiques du joueur qui peuvent occasionnellement partager
    le meme code numerique par coincidence, causant de faux pics isoles
    (observe en pratique : une valeur ~3.5x plus grande apparue une seule
    fois puis disparue). Un filtre anti-aberration rejette les sauts trop
    brusques d'une mise a jour a l'autre plutot que de les enregistrer."""

    MAX_PLAUSIBLE_RATIO = 2.5  # rejette un saut de plus de x2.5 en un seul update

    def __init__(self, history_window_seconds=600):
        self.history_window = history_window_seconds
        self.history = {}  # type -> liste de (timestamp, value)
        self.latest = {}   # type -> valeur la plus recente connue

    def update(self, attributes):
        now = time.time()
        for atype, avalue, aaction in attributes:
            previous = self.latest.get(atype)
            if previous and previous > 0:
                ratio = avalue / previous if avalue >= previous else previous / avalue
                if ratio > self.MAX_PLAUSIBLE_RATIO:
                    # Saut trop brusque pour etre plausible - probablement
                    # un attribut different qui partage temporairement le
                    # meme type_code. On ignore ce point plutot que de
                    # polluer l'historique et fausser le taux estime.
                    continue
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
        from fatewar_actions_rewards import CURRENCY_NAMES
        print("\n=== ATTRIBUTS JOUEUR (PlayerAttribute) ===")
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
