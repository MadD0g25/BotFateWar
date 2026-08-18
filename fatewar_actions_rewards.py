import time

from fatewar_core import (
    encode_varint, encode_field_varint, build_frame,
    walk_protobuf, split_messages, find_message_of_type,
    find_all_messages_of_type, recv_all, log_event,
)

CURRENCY_NAMES = {
    1: "Emoney", 2: "Pierre (Stone)", 3: "Nourriture (Food)", 4: "Bois (Wood)",
    5: "Fer (Iron/Steel)", 16: "Gold", 17: "TechnologyPoint",
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
# Gains hors ligne (delegation / PrivilegeEscrow)
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


# ============================================================================
# Ressources de production (souvent obsolete si collecte auto activee)
# ============================================================================

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


# ============================================================================
# Sign-in quotidien (desactive par defaut dans gs_bot.py, pas confirme
# fonctionnel - voir README.md)
# ============================================================================

def claim_daily_signin_reward(sock, day=1):
    """Reclame la recompense de connexion quotidienne (calendrier de sign-in).

    activity_id=43 correspond a "SignInAct" dans l'enum MallLabelType du jeu
    (confirme via dump.cs). Le parametre "day" est en revanche une
    estimation - a verifier/ajuster si le serveur renvoie une erreur."""
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
# Taches / quetes
# ============================================================================

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
    partout ou on recoit des donnees du serveur - une quete peut se
    terminer a tout moment pendant que le bot tourne."""
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


# ============================================================================
# Courrier
# ============================================================================

def check_and_claim_mail(sock):
    """Liste le courrier, repere les mails avec une piece jointe non
    reclamee (read_flag=2, kMailFlagNotExtract) et les reclame
    automatiquement (read_flag=6, kMailFlagCollect envoye dans
    MailOperatorRequest)."""
    print("\n=== VERIFICATION : Courrier avec pieces jointes ===")

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


# ============================================================================
# Ressources de guilde (contribution des membres)
# ============================================================================

def check_and_collect_guild_resource(sock):
    """Verifie puis collecte les ressources de guilde disponibles pour le
    joueur (contribution personnelle accumulee via la guilde). Les deux
    requetes sont vides (aucun champ necessaire) - confirme via dump.cs."""
    print("\n=== ACTION : Ressources de guilde ===")
    packet = build_frame("9329", b"")  # kMsgCL2GSGuildCollectPlayerGuildResourceRequest = 10643
    sock.sendall(packet)
    response, total = recv_all(sock, drain_seconds=3)
    print("Reponse brute : " + response.hex())

    if total == 0:
        print("Aucune reponse.")
        return

    reply_body = find_message_of_type(response, 10644)  # ...Reply
    if reply_body is None:
        print("Message de reponse non trouve.")
        return

    fields = walk_protobuf(reply_body)
    has_error = False
    collected_any = False
    for fn, wt, val in fields:
        if fn == 99:
            has_error = True
            print("Erreur, code : " + str(val))
        elif fn == 1 and wt == "bytes":
            # Structure particuliere pour cette action : le champ "res_type"
            # (sous-champ 1) vaut toujours 1 ici (pas le vrai identifiant de
            # ressource comme dans les autres messages du jeu) - le vrai
            # type de ressource est dans le champ "sub_type" (sous-champ 2),
            # confirme par capture reelle (bois/nourriture recus mais tous
            # affiches comme "Emoney" avant ce correctif).
            res_fields = walk_protobuf(val)
            res = {}
            for rfn, rwt, rval in res_fields:
                if rfn == 2:
                    res["res_type"] = rval  # sub_type = le vrai type ici
                elif rfn == 3:
                    res["value"] = rval
            if res:
                res_name = CURRENCY_NAMES.get(res.get("res_type"), "Type " + str(res.get("res_type")))
                log_event("Ressource de guilde : +" + str(res.get("value", 0)) + " " + res_name)
                collected_any = True

    if has_error:
        print("Echec de la collecte des ressources de guilde.")
    elif not collected_any:
        print("Rien a collecter cote guilde pour l'instant.")
    else:
        print("Ressources de guilde collectees !")


def help_guild_members(sock):
    """Aide tous les membres de guilde ayant une demande d'assistance en
    attente (equivalent au bouton 'aider tout le monde' de l'app). Requete
    vide, aucun parametre necessaire - confirme via dump.cs
    (kMsgCL2GSGuildAssistHelpOtherRequest)."""
    print("\n=== ACTION : Aide aux membres de guilde ===")
    packet = build_frame("e228", b"")  # kMsgCL2GSGuildAssistHelpOtherRequest = 10466
    sock.sendall(packet)
    response, total = recv_all(sock, drain_seconds=3)
    print("Reponse brute : " + response.hex())

    if total == 0:
        print("Aucune reponse.")
        return

    reply_body = find_message_of_type(response, 10467)  # ...Reply
    if reply_body is None:
        print("Message de reponse non trouve.")
        return

    fields = walk_protobuf(reply_body)
    has_error = False
    assist_count = 0
    contribution = 0
    for fn, wt, val in fields:
        if fn == 99:
            has_error = True
            print("Erreur, code : " + str(val))
        elif fn == 1 and wt == "varint":
            assist_count = val
        elif fn == 2 and wt == "varint":
            contribution = val

    if has_error:
        print("Echec de l'aide aux membres.")
    elif assist_count == 0:
        print("Personne a aider pour l'instant.")
    else:
        log_event(str(assist_count) + " membre(s) de guilde aide(s), " +
                   "+" + str(contribution) + " points de contribution.")


# ============================================================================
# Don a la recherche de guilde (GuildTechDonate). Confirme par capture
# reseau reelle : le vrai client l'envoie en rafale (32 fois en quelques
# secondes) pour le meme tech_id/level - clairement concu pour etre
# "spamme" par le joueur, action peu couteuse par appel.
# ============================================================================

def donate_guild_tech(sock, tech_id, level=1, use_gem=False, times=1):
    """Fait un (ou plusieurs) don(s) a la recherche de guilde en cours.

    IMPORTANT : tech_id correspond a la recherche ACTUELLEMENT active pour
    ta guilde - ce n'est pas une valeur fixe, elle change avec le temps a
    mesure que la guilde progresse. Il faut la mettre a jour manuellement
    de temps en temps (capture reseau, ou observation en jeu) - contexte
    trouve par capture reelle : tech_id=21003, level=1."""
    print("\n=== ACTION : Don a la recherche de guilde (tech=" + str(tech_id) +
          ", " + str(times) + " fois) ===")
    body = (encode_field_varint(1, tech_id) + encode_field_varint(2, level) +
            encode_field_varint(3, 1 if use_gem else 0))
    packet = build_frame("9f29", body)  # kMsgCL2GSGuildTechDonateRequest = 10655

    success_count = 0
    for _ in range(times):
        sock.sendall(packet)
        response, total = recv_all(sock, drain_seconds=2)
        if total == 0:
            break
        reply_body = find_message_of_type(response, 10656)  # ...Reply
        if reply_body is None:
            break
        fields = walk_protobuf(reply_body)
        has_error = any(fn == 99 for fn, wt, val in fields)
        if has_error:
            break
        success_count += 1

    if success_count > 0:
        log_event("Don a la recherche de guilde : " + str(success_count) +
                   "/" + str(times) + " reussi(s) (tech " + str(tech_id) + ").")
    else:
        print("Aucun don reussi (recherche peut-etre terminee, ou plus de ressources).")

    return success_count


# ============================================================================
# Collecte citoyenne (CitizenCollectSettle) - correspond a l'ecran "Details
# fiscaux" vu dans l'app. Confirme par capture reseau reelle : collect_id
# semble identifier un "citoyen"/source de collecte specifique, qui genere
# des ressources en continu et se recolte periodiquement.
# ============================================================================

def collect_citizen_settle(sock, collect_id):
    """Collecte les gains accumules pour un citoyen/une source fiscale
    donnee. collect_id est propre a ton compte (par ex. 10004 observe en
    capture reelle, revenant regulierement toutes les quelques minutes -
    semble etre une source fixe/permanente, contrairement a d'autres
    collect_id vus une seule fois qui pourraient etre ponctuels)."""
    print("\n=== ACTION : Collecte citoyenne (collect_id=" + str(collect_id) + ") ===")
    body = encode_field_varint(1, collect_id)
    packet = build_frame("3c30", body)  # kMsgCL2GSCitizenCollectSettleRequest = 12348
    sock.sendall(packet)
    response, total = recv_all(sock, drain_seconds=3)
    print("Reponse brute : " + response.hex())

    if total == 0:
        print("Aucune reponse.")
        return

    reply_body = find_message_of_type(response, 12349)  # ...Reply
    if reply_body is None:
        print("Message de reponse non trouve.")
        return

    fields = walk_protobuf(reply_body)
    has_error = False
    collected_any = False
    for fn, wt, val in fields:
        if fn == 99:
            has_error = True
            print("Erreur, code : " + str(val))
        elif fn == 3 and wt == "bytes":  # champ "award" (ResourceSet)
            resources = decode_resource_set(val)
            for r in resources:
                res_name = CURRENCY_NAMES.get(r.get("res_type"), "Type " + str(r.get("res_type")))
                log_event("Collecte citoyenne (id " + str(collect_id) + ") : +" +
                           str(r.get("value", 0)) + " " + res_name)
                collected_any = True

    if has_error:
        print("Echec de la collecte citoyenne.")
    elif not collected_any:
        print("Rien a collecter pour cette source pour l'instant.")
    else:
        print("Collecte citoyenne reussie !")


# ============================================================================
# Cadeaux de guilde (reclamation groupee) et cadeaux de calendrier mensuel
# (reclamation groupee egalement) - deux "boutons tout reclamer" simples,
# aucun parametre necessaire, confirmes via dump.cs.
# ============================================================================

def claim_all_guild_gifts(sock):
    """Reclame tous les cadeaux de guilde disponibles en une fois
    (kMsgCL2GSGuildGiftClaimAllRequest, corps vide)."""
    print("\n=== ACTION : Reclamation de tous les cadeaux de guilde ===")
    packet = build_frame("8629", b"")  # kMsgCL2GSGuildGiftClaimAllRequest = 10630
    sock.sendall(packet)
    response, total = recv_all(sock, drain_seconds=3)
    print("Reponse brute : " + response.hex())

    if total == 0:
        print("Aucune reponse.")
        return

    reply_body = find_message_of_type(response, 10631)  # ...Reply
    if reply_body is None:
        print("Message de reponse non trouve.")
        return

    fields = walk_protobuf(reply_body)
    has_error = any(fn == 99 for fn, wt, val in fields)
    if has_error:
        error_code = next(val for fn, wt, val in fields if fn == 99)
        if error_code == 1353:  # kECGuildNoGiftToClaim
            print("Aucun cadeau de guilde disponible pour l'instant.")
        else:
            print("Echec, code erreur : " + str(error_code))
    else:
        log_event("Cadeaux de guilde reclames (tous).")


def claim_all_daily_gifts(sock):
    """Reclame tous les cadeaux de selection quotidienne du mall en une
    fois (kMsgCL2GSMallGetAllDaysSelectOpitonGiftRequest, corps vide)."""
    print("\n=== ACTION : Reclamation de tous les cadeaux quotidiens (mall) ===")
    packet = build_frame("d934", b"")  # ...Request = 13529
    sock.sendall(packet)
    response, total = recv_all(sock, drain_seconds=3)
    print("Reponse brute : " + response.hex())

    if total == 0:
        print("Aucune reponse.")
        return

    reply_body = find_message_of_type(response, 13530)  # ...Reply
    if reply_body is None:
        print("Message de reponse non trouve.")
        return

    fields = walk_protobuf(reply_body)
    has_error = any(fn == 99 for fn, wt, val in fields)
    if has_error:
        error_code = next(val for fn, wt, val in fields if fn == 99)
        print("Echec, code erreur : " + str(error_code))
    else:
        log_event("Cadeaux quotidiens (mall) reclames.")


# ============================================================================
# Recolte de ferme (systeme de mini-jeu separe : farmInfo/farmLivestock/
# farmHarvest). Confirme par capture reseau reelle.
# ============================================================================

def harvest_farm(sock, pen_id):
    """Recolte un enclos de ferme donne. pen_id est propre a ton compte -
    trouve par capture reseau (kMsgCL2GSFarmHarvestRequest)."""
    print("\n=== ACTION : Recolte de ferme (enclos " + str(pen_id) + ") ===")
    body = encode_field_varint(1, pen_id)
    packet = build_frame("5b33", body)  # kMsgCL2GSFarmHarvestRequest = 13147
    sock.sendall(packet)
    response, total = recv_all(sock, drain_seconds=3)
    print("Reponse brute : " + response.hex())

    if total == 0:
        print("Aucune reponse.")
        return

    reply_body = find_message_of_type(response, 13167)  # kMsgGS2CLFarmHarvestReply
    if reply_body is None:
        print("Message de reponse non trouve.")
        return

    fields = walk_protobuf(reply_body)
    has_error = False
    collected_any = False
    for fn, wt, val in fields:
        if fn == 99:
            has_error = True
            print("Erreur, code : " + str(val))
        elif fn == 2 and wt == "bytes":
            # champ 2 = "rewards" (PBList<Resource>), chaque occurrence
            # est un Resource individuel (meme pattern que TDCity/quetes).
            res_fields = walk_protobuf(val)
            res = {f: v for f, wt2, v in res_fields if wt2 == "varint"}
            if res:
                res_name = CURRENCY_NAMES.get(res.get(1), "Type " + str(res.get(1)))
                value = res.get(3, res.get(2, 0))
                log_event("Recolte de ferme (enclos " + str(pen_id) + ") : +" +
                           str(value) + " " + res_name)
                collected_any = True

    if has_error:
        print("Echec de la recolte.")
    elif collected_any:
        print("Recolte reussie !")
    else:
        print("Rien a recolter pour l'instant.")
