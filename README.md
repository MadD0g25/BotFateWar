<div align="center">

# ⚔️ Fate War Bot

**Client Python non officiel pour Fate War (IGG)**
*Reverse-engineering complet du protocole reseau — sans dependance externe*

[![Python](https://img.shields.io/badge/Python-3.7+-blue.svg)](https://www.python.org/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
[![Platform](https://img.shields.io/badge/Login-iOS%20requis-lightgrey.svg)](#-avertissements-importants)

</div>

---

## 📖 Sommaire

- [Avertissements importants](#-avertissements-importants)
- [Comment ça marche](#-comment-ça-marche)
- [Structure du projet](#-structure-du-projet)
- [Installation](#-installation)
- [Utilisation](#-utilisation)
- [Configuration : récupérer tes identifiants](#-configuration--récupérer-tes-identifiants)
- [Fonctionnalités](#-fonctionnalités)
- [Reprise après plantage](#-reprise-après-plantage)
- [Capturer tes propres IDs (casernes, bâtiments, etc.)](#-capturer-tes-propres-ids)
- [Journal des découvertes et de l'avancement](#-journal-des-découvertes-et-de-lavancement)
- [Ce qui manque](#-ce-qui-manque--contributions-bienvenues)
- [Renouvellement des identifiants](#-renouvellement-des-identifiants)
- [Structure du protocole](#-structure-du-protocole)
- [Contribuer](#-contribuer)

---

## ⚠️ Avertissements importants

> **Projet non officiel**, non affilié à IGG. Utilisation à tes risques —
> ceci peut enfreindre les conditions d'utilisation du jeu.

| Point | Détail |
|---|---|
| 🍎 **Login iOS uniquement** | Le login sur le *Login Server* ne fonctionne, à ce jour, que depuis un appareil Apple réel (iPhone/iPad/Mac). Une vérification d'empreinte réseau bas niveau bloque les connexions depuis Linux (testé et confirmé à plusieurs reprises). |
| 📱 **a-Shell recommandé** | Sur iOS, exécute le script dans [a-Shell](https://apps.apple.com/app/a-shell/id1473805438) (gratuit). |
| ⏱️ **Pas de bot continu sur iOS** | Les apps iOS étant suspendues en arrière-plan, a-Shell ne peut pas faire tourner un bot pendant des heures — d'où l'architecture à deux appareils ci-dessous. |
| 🚦 **Rate-limit possible** | Une limitation de fréquence semble exister sur les tentatives de connexion au Login Server, en particulier après plusieurs tentatives rapprochées — laisse reposer 1-2h si ça persiste. Un deuxième serveur LS est disponible en secours (`ls_login.py 2`), mais s'est révélé peu fiable en pratique (voir [journal des découvertes](#-journal-des-découvertes-et-de-lavancement)). |

---

## 🏗️ Comment ça marche

Le login se fait en deux étapes, auprès de deux serveurs différents. Seule
la première nécessite un appareil Apple ; la seconde peut tourner
**indéfiniment** sur n'importe quelle machine (Raspberry Pi, PC Linux, Mac).

```
 📱 iPhone (a-Shell)                    🖥️  Raspberry Pi / Linux
┌─────────────────────┐    nonce      ┌──────────────────────────────┐
│   ls_login.py         │ ─(réseau,──▶ │   gs_bot.py + bot_config.py    │
│  → login Login Server │  ~1 seconde) │  → login Game Server           │
│  → récupère le nonce  │              │  → synchronisation             │
│  → l'envoie au Pi     │              │  → actions de jeu              │
└─────────────────────┘              │  → boucle infinie autonome     │
                                       │     (survit aux plantages)     │
                                       └──────────────────────────────┘
```

---

## 📦 Structure du projet

| Fichier | Rôle |
|---|---|
| `bot_config.py` | **Toute la configuration** — casernes, bâtiments, guilde, TDCity... C'est le seul fichier que tu dois éditer au quotidien. |
| `fatewar_core.py` | Encodage/décodage Protobuf bas niveau, journal, état persistant, décompression zlib automatique |
| `fatewar_login.py` | Connexion Login Server + Game Server, maintien de session |
| `fatewar_actions_troops.py` | Entraînement et récupération de troupes (multi-casernes, quantité "max" automatique) |
| `fatewar_actions_building.py` | Amélioration de bâtiments |
| `fatewar_actions_rewards.py` | Gains hors ligne, tâches/quêtes, courrier, guilde (ressources/aide/dons/cadeaux), collecte citoyenne, ferme, sign-in |
| `fatewar_actions_tdcity.py` | Combats de zone TDCity (exploration de parcelles), quêtes principales |
| `fatewar_resources.py` | Totaux de ressources en temps réel, liste des bâtiments de la ville |
| `gs_bot.py` | **Script principal (Pi)** — orchestre tous les modules ci-dessus, lit `bot_config.py` |
| `ls_login.py` | **Script iPhone** — login initial uniquement |

Cette séparation permet d'ajouter de nouvelles options (`bot_config.py`) ou
de nouvelles actions (nouveau module `fatewar_actions_*.py`) sans jamais
avoir à toucher au cœur de `gs_bot.py`.

---

## 📦 Installation

Sur les **deux appareils**, place les fichiers nécessaires dans le même
dossier (voir tableau ci-dessous) :

```bash
git clone https://github.com/toncompte/fatewar-bot.git
cd fatewar-bot
cp config.example.py config.py
cp bot_config.example.py bot_config.py
```

Édite `config.py` avec tes identifiants (voir
[Configuration](#-configuration--récupérer-tes-identifiants)), et
`bot_config.py` avec tes casernes/options (voir
[Capturer tes propres IDs](#-capturer-tes-propres-ids)).

Dans `bot_config.py`, `LISTEN_PORT` peut rester par défaut. Dans
`ls_login.py`, renseigne l'IP locale de ton Raspberry Pi :

```python
PI_HOST = "192.168.1.XXX"   # trouve-la avec "hostname -I" sur le Pi
```

**Fichiers requis par appareil :**

| Fichier | iPhone (a-Shell) | Pi / Linux |
|---|:---:|:---:|
| `config.py` | ✅ | ✅ |
| `bot_config.py` | ❌ | ✅ |
| `fatewar_core.py` | ✅ | ✅ |
| `fatewar_login.py` | ✅ | ✅ |
| `fatewar_actions_troops.py` | ❌ | ✅ |
| `fatewar_actions_building.py` | ❌ | ✅ |
| `fatewar_actions_rewards.py` | ❌ | ✅ |
| `fatewar_actions_tdcity.py` | ❌ | ✅ |
| `fatewar_resources.py` | ❌ | ✅ |
| `ls_login.py` | ✅ | ❌ |
| `gs_bot.py` | ❌ | ✅ |

---

## ▶️ Utilisation

**1. Sur le Pi**, lance en premier — il se met en attente :

```bash
python3 gs_bot.py
```

**2. Sur l'iPhone**, une fois "En attente du nonce..." affiché :

```bash
python3 ls_login.py       # serveur LS par defaut
python3 ls_login.py 2     # serveur LS alternatif si rate-limite
```

Le nonce est transmis automatiquement, le bot démarre **immédiatement**
côté Pi. Ferme a-Shell ensuite — le Pi continue seul, en boucle,
potentiellement pendant des jours (voir [Reprise après plantage](#-reprise-après-plantage)).

**Pour une nouvelle session** (la connexion GS finit par expirer), relance
`gs_bot.py` puis `ls_login.py`. L'état (casernes, bâtiments, position
TDCity) est repris automatiquement.

---

## 🔑 Configuration : récupérer tes identifiants

### Ce qu'il te faut
- Un iPhone/iPad avec Fate War installé
- Une app de capture réseau avec certificat MITM (export HAR)

### Étape 1 — Capturer une session de connexion
1. Ferme complètement Fate War, lance ta capture réseau
2. Ouvre Fate War, connecte-toi, laisse charger jusqu'à voir ta base
3. Arrête la capture, exporte en HAR

### Étape 2 — `WEB_SESSION` et `USER_ID`
Cherche une requête vers `apis-dsa.iggapis.com/ums/member/binding?access_token=eyJ...`.
Ce paramètre est ta valeur `WEB_SESSION`.

Décode la 2ᵉ partie (entre les deux points) en base64 :
```bash
echo "PARTIE_DU_MILIEU" | base64 -d
```
*(ajoute des `=` à la fin si besoin)*. Le JSON obtenu contient `"sub"` →
ta valeur `USER_ID`.

> ⚠️ **Ce JSON contient aussi un champ `"key"` — ce n'est PAS ta valeur
> `KEY_UUID`, malgré les apparences.** Voir l'étape suivante et le
> [journal des découvertes](#-journal-des-découvertes-et-de-lavancement)
> pour l'explication complète (erreur vécue en changeant de compte).

### Étape 3 — `KEY_UUID` (attention, piège)
`KEY_UUID` est un identifiant lié à **l'appareil/l'installation de l'app**,
pas à ton compte de jeu. Il reste **identique** même si tu changes de
compte IGG sur le même téléphone.

Pour le trouver de façon fiable : capture le trafic **TCP brut** (pas
HTTPS, un vrai `tcpdump`) vers le port `9310` pendant un login réel dans
l'app, et lis directement le **champ 10** de la requête
`kMsgCL2LSLoginRequest` — voir `build_ls_login_packet()` dans
`fatewar_login.py`. C'est une chaîne du style
`1D18308B-89D9-41CF-83F5-372A0B07A6A9`.

### Étape 4 — `DEVICE_ID`
Cherche une requête HTTPS contenant `device_id=` dans son URL (endpoint de
logging/analytics).

### Étape 5 — `GAME_ID`, `APP_VERSION`, `DEVICE_MODEL`, `GPU_MODEL`
```python
APP_VERSION = "1.2.20"
DEVICE_MODEL = "iPhone16,2"
GPU_MODEL = "Apple A17 Pro GPU"
GAME_ID = "11570603034"   # identique pour tous les joueurs de cette version
```

### Étape 6 — Remplir `config.py`
```bash
cp config.example.py config.py
```

---

## ✨ Fonctionnalités

| Action | Statut | Module | Détail |
|---|:---:|---|---|
| **Login complet** (LS + GS) | ✅ Stable | `fatewar_login.py` | Deux appareils, serveur LS de secours (peu fiable, voir découvertes) |
| **Maintien de session** | ✅ Stable | `fatewar_login.py` | Keepalive natif du jeu (`KeepLiveRequest`), toutes les 5s |
| **Gains hors ligne** | ⚠️ Incertain | `fatewar_actions_rewards.py` | Renvoie systématiquement vide même quand l'app affiche des valeurs — probablement calculé côté client, jamais confirmé transmis par le réseau malgré plusieurs captures dédiées |
| **Entraînement multi-casernes** | ✅ Stable | `fatewar_actions_troops.py` | Plusieurs casernes en parallèle, quantité "max" auto-détectée sans gaspillage |
| **Récupération de troupes** | ✅ Stable | `fatewar_actions_troops.py` | Distingue "encore en cours" de "caserne vide" (piège Protobuf, voir découvertes) |
| **Amélioration de tous les bâtiments** | ✅ Stable | `fatewar_actions_building.py` + `fatewar_resources.py` | Découverte automatique via `get_city_buildings()`, aucun ID à chercher manuellement |
| **Tâches/quêtes de guilde** | ✅ Stable | `fatewar_actions_rewards.py` | Écoute en continu |
| **Quêtes principales** | ✅ Stable | `fatewar_actions_tdcity.py` | `claim_main_task_reward()` |
| **Courrier** | ✅ Stable | `fatewar_actions_rewards.py` | Détection et réclamation automatique |
| **Ressources de guilde + aide aux membres** | ✅ Stable | `fatewar_actions_rewards.py` | Désactivable en bloc (`ENABLE_GUILD_FEATURES`) |
| **Don à la recherche de guilde** | ✅ Stable | `fatewar_actions_rewards.py` | Reproduit le "spam" du vrai client |
| **Cadeaux de guilde et quotidiens (mall)** | ✅ Stable | `fatewar_actions_rewards.py` | Boutons "tout réclamer", sans risque |
| **Collecte citoyenne** | ✅ Stable | `fatewar_actions_rewards.py` | Correspond à l'écran "Détails fiscaux" |
| **Récolte de ferme** | ✅ Stable | `fatewar_actions_rewards.py` | Mini-jeu séparé découvert tardivement |
| **Combats de zone TDCity** | ✅ Stable | `fatewar_actions_tdcity.py` | Exploration incrémentale de parcelles, limite configurable |
| **Totaux de ressources réels** | ✅ Stable | `fatewar_resources.py` | Bois/nourriture/pierre/fer/connaissances confirmés via `CityInfoReply` compressé |
| **Reprise après plantage** | ✅ Stable | `fatewar_core.py` | État sauvegardé sur disque, fusion propre (pas d'écrasement) |
| **Sign-in quotidien** | ❌ Désactivé | `fatewar_actions_rewards.py` | Jamais confirmé fonctionnel |
| **Système citoyen complet (Appoint/Arrived)** | 🔍 Repéré, non implémenté | — | Trop complexe (UUID, plusieurs étapes) pour une automatisation fiable |
| **Construction de nouveau bâtiment** | 🔍 Repéré, non implémenté | — | Confirmé par capture (`CityCreateBuildingRequest`), mais nécessite de choisir un emplacement |

---

## 🔄 Reprise après plantage

Le bot sauvegarde automatiquement dans `fatewar_state.json` le timestamp
de fin connu de chaque caserne, bâtiment et la position TDCity, à chaque
mise à jour — en **fusionnant** avec l'existant (pas d'écrasement, bug
corrigé pendant le développement). Si le bot plante ou redémarre, il
reprend directement avec l'heure connue.

---

## 🏰 Capturer tes propres IDs

Les valeurs par défaut dans `bot_config.py` sont vides ou correspondent au
compte de développement — **remplace-les par les tiennes**.

### Casernes (`TRAINING_SLOTS`)
1. Capture le trafic TCP brut vers le Game Server (`tcpdump`, port 12040-12056 selon session) pendant un entraînement manuel, une fois par type de troupe.
2. Cherche le message type `10402` (`kMsgCL2GSTrainRequest`, octets `a2 28`).
3. Le corps contient `army` (army_id + count) et `barrack_id`.
4. Renseigne `TRAINING_SLOTS` dans `bot_config.py`.

> 💡 `army_id` semble provenir d'une table de config globale du jeu
> (`TroopCfgData`) — potentiellement identique pour tous les comptes ayant
> le même type de troupe débloqué (confirmé à plusieurs reprises entre
> deux comptes différents : `1001`=lanceurs de haches, `1101`=berserkers,
> `1201`=cavalerie, de façon constante). `barrack_id` reste propre à
> chaque ville, mais suit souvent un schéma proche (`8`, `~1004-1007`).

### Bâtiments
Aucune capture nécessaire ! `AUTO_UPGRADE_ALL_BUILDINGS = True` dans
`bot_config.py` découvre et améliore automatiquement tout ce qui est
disponible.

### Ressources de guilde, aide, don à la recherche
Passe `ENABLE_GUILD_FEATURES = True` une fois dans une guilde. Pour
`GUILD_TECH_ID`, capture une requête `GuildTechDonateRequest` (type
`10655`) pendant que tu contribues manuellement à une recherche.

### Collecte citoyenne / Ferme / TDCity
Voir les commentaires dans `bot_config.py` — chacun nécessite une capture
ciblée de l'action correspondante en jeu (`CitizenCollectSettleRequest`
type `12348`, `FarmHarvestRequest` type `13147`,
`TDCitySetStateRequest` type `14298`).

---

## 📓 Journal des découvertes et de l'avancement

Historique des trouvailles marquantes de ce projet, dans l'ordre
chronologique — utile pour comprendre certains choix de code inhabituels.

**Protocole de base**
- Login en deux serveurs (LS puis GS), architecture à deux appareils imposée par une vérification d'empreinte TCP (Linux rejeté par le LS).
- Plusieurs messages peuvent arriver concaténés dans un seul paquet TCP — le parsing découpe toujours par longueur, jamais en supposant un seul message.

**Le vrai bug du heartbeat (correction majeure)**
Le "ping" utilisé pendant des jours (`0400a127`) n'était pas un keepalive
du tout mais `kMsgCL2GSEnterGameRequest` (une action à usage unique !). Le
vrai keepalive est `kMsgCL2GSKeepLiveRequest` (type `10006`, confirmé par
capture réelle). Ce mélange expliquait la quasi-totalité des coupures de
connexion après 1-2 minutes.

**Le piège des valeurs par défaut Protobuf**
En Protobuf, un champ valant `0` n'est **jamais transmis** sur le réseau.
Conséquence concrète : le code d'erreur `5809` (récupération de troupes)
est renvoyé aussi bien pour "encore en cours" (`work_status=1`) que pour
"caserne vide" (`work_status=0`, donc **absent** du message) — deux
situations demandant une réaction opposée. Contrôler `work_status is None`
→ traiter comme `0` a réglé un vrai risque de blocage infini.

**Compression zlib des grosses réponses**
`CityInfoReply` (et d'autres réponses volumineuses) arrivent enveloppées
dans un `CompressedMessage` générique (type `14028`, zlib). Sans cette
découverte, les totaux de ressources réels étaient invisibles.
`find_message_of_type()` gère cette décompression automatiquement pour
tous les modules.

**Ressources mal nommées**
`CurrencyType` 2 s'appelle en interne `kCurrencyTypeOil` ("pétrole") mais
correspond en réalité à la **Pierre** affichée en jeu — un nom de code
hérité, sans rapport avec l'affichage. Par déduction, le type `5`
("Steel") correspond au **Fer**, distinct de la Pierre.

**Gains hors ligne : mystère non résolu**
Malgré plusieurs captures réseau ciblées (dont une avec de vraies valeurs
visibles à l'écran : 1510 bois, 604 pierre, 1229 nourriture), **aucune**
de ces valeurs n'a jamais été retrouvée dans le trafic réseau, même après
décompression zlib exhaustive sur toute la capture. Hypothèse retenue :
l'affichage est calculé côté client (taux de production × temps hors
ligne), sans transmission serveur au moment de l'ouverture de la popup.

**Changement de compte : le piège `KEY_UUID`**
En passant à un second compte (compte IGG lié, vs compte invité), le
`KEY_UUID` a été incorrectement recalculé depuis le champ `"key"` d'un JWT
— alors qu'une comparaison octet-par-octet avec le trafic réel de l'app a
confirmé que ce champ **ne change jamais**, quel que soit le compte
connecté. Le vrai blocage n'était donc pas un rate-limit comme supposé au
début, mais cette valeur incorrecte.

**Multi-casernes et découverte de bâtiments**
`army_id` semble être une constante globale du jeu (confirmée identique
sur deux comptes différents), tandis que `barrack_id` reste propre à
chaque ville. `get_city_buildings()` (via `CityInfoReply`) permet de lister
tous les bâtiments d'un compte automatiquement, sans capture manuelle par
bâtiment.

**TDCity et quêtes principales**
Une session de capture "libre" (jouer normalement pendant 15 minutes avec
`tcpdump` actif) a révélé un système de combats de zone entièrement
séparé (`TDCitySetStateRequest`/`TDCityAreaBattleAwardRequest`), résolu
**instantanément** côté serveur (contrairement à l'entraînement/
amélioration qui prennent du temps réel) - confirmé par un cas gagné
(deux transitions d'état) et un cas perdu (une seule transition) sur la
même capture.

---

## 🚧 Ce qui manque (contributions bienvenues)

- [ ] Comprendre le mécanisme réel des gains hors ligne (voir ci-dessus)
- [ ] Sign-in quotidien (jamais confirmé fonctionnel)
- [ ] Construction de nouveaux bâtiments (repérée, nécessite un choix d'emplacement)
- [ ] Système citoyen complet (`Appoint`→`Arrived`→`Settle`, complexe)
- [ ] Utilisation d'objets d'inventaire (repérée, risque de gaspillage sans supervision)
- [ ] Marches de troupes (attaque/récolte sur la carte du monde)
- [ ] Arène locale (PvP — risqué d'automatiser sans supervision)
- [ ] Machine à sous, recrutement de héros (probablement payants en monnaie premium)

---

## 🔄 Renouvellement des identifiants

Le `WEB_SESSION` (JWT) reste valide plusieurs jours. Si `ls_login.py`
échoue de façon persistante avec "connexion réinitialisée" (même après
avoir attendu 1-2h et essayé le serveur alternatif), **vérifie d'abord que
le vrai jeu se connecte normalement** avant de soupçonner un token expiré
— dans notre historique, un token identique restait valide plusieurs
jours, et le vrai problème était ailleurs (`KEY_UUID`, voir le journal des
découvertes ci-dessus). Si le token a vraiment changé, refais une capture
réseau (Étape 1-2 de la Configuration).

---

## 🧩 Structure du protocole

Protobuf binaire sur TCP brut, framing simple :

```
┌──────────────────┬──────────────────┬─────────────────┐
│  Longueur (2 o.)  │  Type msg (2 o.)  │  Corps Protobuf  │
│  little-endian    │  little-endian    │                  │
│  self-inclusive   │                   │                  │
└──────────────────┴──────────────────┴─────────────────┘
```

Les réponses volumineuses peuvent être compressées en zlib et emballées
dans un `CompressedMessage` générique (type `14028`) —
`find_message_of_type()` dans `fatewar_core.py` gère cette décompression
automatiquement.

Les types de message et structures de champs ont été extraits par
décompilation IL2Cpp du client officiel (`global-metadata.dat` +
`libil2cpp.so`, **non redistribués ici**).

---

## 🤝 Contribuer

**Process type pour ajouter une action :**
1. Trouve le nom du message dans un dump IL2Cpp (`kMsgCL2GS...Request`)
2. Convertis sa valeur en hex little-endian
3. Trouve la classe correspondante pour ses champs
4. Capture une vraie requête/réponse par `tcpdump` pour valider
5. Ajoute la fonction dans le module d'action approprié, en t'inspirant
   du style existant (`train_troops`/`upgrade_building` pour un suivi de
   minuteur, `check_and_claim_mail` pour une liste + réclamation groupée)
6. Ajoute les nouvelles options dans `bot_config.py`, jamais dans `gs_bot.py`

---

<div align="center">

*Fait avec 🍵 et beaucoup de paquets réseau capturés.*

</div>
