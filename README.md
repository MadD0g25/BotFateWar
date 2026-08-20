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
- [Capturer tes propres IDs](#-capturer-tes-propres-ids)
- [Extraction des données de jeu (AssetStudio)](#-extraction-des-données-de-jeu-assetstudio)
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
| 🍎 **Login iOS uniquement** | Le login sur le *Login Server* ne fonctionne, à ce jour, que depuis un appareil Apple réel (iPhone/iPad/Mac). Une vérification d'empreinte réseau bas niveau bloque les connexions depuis Linux. |
| 📱 **a-Shell recommandé** | Sur iOS, exécute le script dans [a-Shell](https://apps.apple.com/app/a-shell/id1473805438) (gratuit). |
| ⏱️ **Pas de bot continu sur iOS** | Les apps iOS étant suspendues en arrière-plan, a-Shell ne peut pas faire tourner un bot pendant des heures — d'où l'architecture à deux appareils ci-dessous. |
| 🚦 **Rate-limit possible** | Une limitation de fréquence semble exister sur les tentatives de connexion au Login Server après plusieurs tentatives rapprochées — laisse reposer 1-2h si ça persiste. |
| ⚔️ **Combat automatique = risque élevé** | La fonctionnalité d'attaque de monstres envoie de vraies troupes. Vérifie toujours ta configuration avant de l'activer. |
| 🕐 **Maintenance serveur** | Une coupure après plusieurs heures de fonctionnement continu peut simplement correspondre à une maintenance planifiée côté serveur, pas un bug du bot. |

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
| `bot_config.py` | **Toute la configuration** — casernes, bâtiments, guilde, combats, TDCity... Le seul fichier à éditer au quotidien. |
| `fatewar_core.py` | Encodage/décodage Protobuf bas niveau, journal, état persistant, décompression zlib automatique, réception réseau avec limite de temps totale |
| `fatewar_login.py` | Connexion Login Server + Game Server, maintien de session |
| `fatewar_actions_troops.py` | Entraînement et récupération de troupes — calcul direct du maximum entraînable |
| `fatewar_actions_building.py` | Amélioration de bâtiments, gestion des erreurs structurelles/de file |
| `fatewar_actions_rewards.py` | Gains hors ligne, tâches/quêtes, courrier, guilde, collecte citoyenne, ferme |
| `fatewar_actions_tdcity.py` | Combats de zone TDCity (exploration de parcelles), quêtes principales |
| `fatewar_actions_misc.py` | Recherche personnelle, récompenses de chapitre/quotidiennes, talent de héros, soin à l'hôpital |
| `fatewar_actions_battle.py` | Recherche et attaque automatique de monstres Corrompus |
| `fatewar_troop_data.py` | **Données de jeu extraites via AssetStudio** — coût par unité de 321 troupes, capacité de caserne par niveau (0-30), quantité de troupes recommandée par niveau de Corrompu (1-30) |
| `fatewar_names.py` | **Traductions extraites via AssetStudio** — 43 noms de héros, 44 noms de bâtiments |
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

Dans `ls_login.py`, renseigne l'IP locale de ton Raspberry Pi :

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
| `fatewar_actions_misc.py` | ❌ | ✅ |
| `fatewar_actions_battle.py` | ❌ | ✅ |
| `fatewar_troop_data.py` | ❌ | ✅ |
| `fatewar_names.py` | ❌ | ✅ |
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
potentiellement pendant des heures (voir [Reprise après plantage](#-reprise-après-plantage)).

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
> [journal des découvertes](#-journal-des-découvertes-et-de-lavancement).

### Étape 3 — `KEY_UUID` (attention, piège)
`KEY_UUID` est un identifiant lié à **l'appareil/l'installation de l'app**,
pas à ton compte de jeu. Il reste **identique** même si tu changes de
compte IGG sur le même téléphone.

Pour le trouver de façon fiable : capture le trafic **TCP brut** (pas
HTTPS) vers le port `9310` pendant un login réel dans l'app, et lis
directement le **champ 10** de la requête `kMsgCL2LSLoginRequest` — voir
`build_ls_login_packet()` dans `fatewar_login.py`. C'est une chaîne du
style `1D18308B-89D9-41CF-83F5-372A0B07A6A9`.

### Étape 4 — `DEVICE_ID`
Cherche une requête HTTPS contenant `device_id=` dans son URL.

### Étape 5 — `GAME_ID`, `APP_VERSION`, `DEVICE_MODEL`, `GPU_MODEL`
```python
APP_VERSION = "1.2.20"
DEVICE_MODEL = "iPhone16,2"
GPU_MODEL = "Apple A17 Pro GPU"
GAME_ID = "11570603034"
```

### Étape 6 — Remplir `config.py`
```bash
cp config.example.py config.py
```

---

## ✨ Fonctionnalités

| Action | Statut | Module | Détail |
|---|:---:|---|---|
| **Login complet** (LS + GS) | ✅ Stable | `fatewar_login.py` | Deux appareils, serveur LS de secours |
| **Maintien de session** | ✅ Stable | `fatewar_login.py` | Keepalive natif du jeu, toutes les 5s |
| **Entraînement multi-casernes** | ✅ Stable | `fatewar_actions_troops.py` | Quantité "max" **calculée directement** (niveau de caserne + coût réel + ressources) |
| **Récupération de troupes** | ✅ Stable | `fatewar_actions_troops.py` | Distingue "encore en cours" de "caserne vide" |
| **Amélioration de tous les bâtiments** | ✅ Stable | `fatewar_actions_building.py` | Découverte auto, gestion des files simultanées, noms lisibles |
| **Recherche personnelle** | ✅ Stable | `fatewar_actions_misc.py` | Lance et réclame automatiquement |
| **Combat automatique contre Corrompus** | ✅ Stable (risqué) | `fatewar_actions_battle.py` | Recherche par niveau, attaque immédiate, **quantité de troupes calculée automatiquement** selon le niveau |
| **Soin à l'hôpital** | 🔧 Disponible, pas automatisé | `fatewar_actions_misc.py` | Nécessite de connaître le nombre de blessés par type |
| **Tâches (guilde/principales/chapitre/quotidiennes)** | ✅ Stable | plusieurs modules | Écoute continue ou réclamation groupée |
| **Courrier** | ✅ Stable | `fatewar_actions_rewards.py` | Détection et réclamation automatique |
| **Guilde (ressources/aide/dons/cadeaux)** | ✅ Stable | `fatewar_actions_rewards.py` | Désactivable en bloc |
| **Talents de héros** | ✅ Stable | `fatewar_actions_misc.py` | Bouton "recommandé" de l'app reproduit |
| **Collecte citoyenne / Ferme** | ✅ Stable | `fatewar_actions_rewards.py` | IDs propres au compte |
| **Combats de zone TDCity** | ✅ Stable | `fatewar_actions_tdcity.py` | Exploration incrémentale, limite configurable |
| **Totaux de ressources réels** | ✅ Stable | `fatewar_resources.py` | Toutes les ressources principales confirmées |
| **Noms lisibles dans les logs** | ✅ Stable | `fatewar_names.py` | Héros et bâtiments affichés par leur vrai nom |
| **Reprise après plantage** | ✅ Stable | `fatewar_core.py` | État sauvegardé sur disque, fusion propre |
| **Gains hors ligne** | ❌ Désactivé | — | Jamais confirmé transmis par le réseau |
| **Sign-in quotidien** | ❌ Désactivé | — | Jamais confirmé fonctionnel |
| **Système citoyen complet** | 🔍 Repéré, non implémenté | — | Trop complexe (UUID, plusieurs étapes) |
| **Construction de nouveau bâtiment** | 🔍 Repéré, non implémenté | — | Nécessite un choix d'emplacement |
| **Système d'auto-combat natif du jeu** | 🔍 Repéré, non implémenté | — | Jamais capturé en usage réel |
| **Découverte auto du roster de héros** | ❌ Abandonné | — | Aucune requête dédiée trouvée après recherche exhaustive (voir journal) |

---

## 🔄 Reprise après plantage

Le bot sauvegarde automatiquement dans `fatewar_state.json` le timestamp
de fin connu de chaque caserne, la position TDCity, à chaque mise à jour —
en **fusionnant** avec l'existant. Si le bot plante ou redémarre, il
reprend directement avec l'heure connue.

---

## 🏰 Capturer tes propres IDs

### Casernes (`TRAINING_SLOTS`)
Capture le trafic pendant un entraînement manuel, cherche le message type
`10402` (`kMsgCL2GSTrainRequest`). Le corps contient `army_id` + `count` +
`barrack_id`.

> 💡 `army_id` semble être une constante globale du jeu (confirmée
> identique sur deux comptes différents). `barrack_id` reste propre à
> chaque ville — et son **type de bâtiment** (donc son vrai nom) peut se
> trouver dans `fatewar_names.py` une fois `get_city_buildings()` appelé.

### Bâtiments
Aucune capture nécessaire ! `AUTO_UPGRADE_ALL_BUILDINGS = True` découvre
et améliore automatiquement tout ce qui est disponible.

### Combat contre Corrompus (`BATTLE_HERO1/2`)
Capture le flow manuel : loupe → recherche → ATQ → rassemblement des
troupes → lancer. Cherche `kMsgCL2GSCreateMarchRequest` (type `10126`).
Alternative sans capture : regarde dans `fatewar_names.py` (HERO_NAMES)
si le héros que tu veux utiliser y figure déjà.

### Recherche personnelle / Guilde / Citoyens / Ferme
Voir les commentaires dans `bot_config.py` — chacun nécessite une capture
ciblée de l'action correspondante en jeu.

---

## 🧰 Extraction des données de jeu (AssetStudio)

En plus du protocole réseau, certaines données de configuration statiques
du jeu peuvent être extraites directement des assets de l'app avec
**AssetStudio** ([github.com/aelurum/AssetStudio](https://github.com/aelurum/AssetStudio)),
sans passer par une capture réseau.

**Procédure résumée :**
1. Ouvre AssetStudio, charge le dossier `assets` extrait de l'APK
2. Configure le support IL2Cpp avec `global-metadata.dat` + `libil2cpp.so`
3. Filtre par type `MonoBehaviour`, cherche par nom (`troop`, `hero`,
   `city_building`, `city_barracks_lv`, `science`, `monster`, `string_fr`...)
4. Onglet **Dump** pour voir le contenu structuré, **Export** pour extraire

**Déjà extrait et intégré :**
- `troop` (321 troupes) → coût en ressources par unité (`fatewar_troop_data.py`)
- `city_barracks_lv` (niveaux 0-30) → capacité de la file d'entraînement par niveau de caserne
- `monster` (4914 entrées, filtré sur `MonsterTypeId=1003`) → quantité de troupes recommandée par niveau de Corrompu (niveaux 1-30)
- `string_fr` (30958 entrées) → **table de traduction complète** : noms de héros (`hero_nameXXXXX`) et bâtiments (`ss_buildingnameXXXX`)
- `city_building` → structure des bâtiments, clé de nommage
- `science` → structure de l'arbre de recherche personnelle (coûts, prérequis, niveaux)

**Pistes tentées sans succès** (recherches infructueuses malgré plusieurs essais) :
- Table des types de ressources/monnaies (`CurrencyType`) — les codes `2414`/`2424` restent non identifiés, aucune table nommée de façon évidente trouvée
- Recherche de guilde (`GuildTech`) — semble ne pas exister sous ce nom, ou structure différente non identifiée
- **Liste complète du roster de héros possédés** — malgré deux captures ciblées et une recherche exhaustive de la rafale de connexion initiale (81 types de messages, contenu compressé inclus), aucune requête dédiée n'a été trouvée. Conclusion retenue : cette donnée est probablement mise en cache côté client dès la création du compte et n'est plus jamais retransmise par le réseau par la suite. Solution de contournement : les héros peuvent être identifiés par leur **nom** directement via `string_fr.json` → `fatewar_names.py` (HERO_NAMES), sans capture réseau.

**Autres pistes possibles pour qui veut continuer :**
- `item` — pour le soin à l'hôpital (types de troupes blessées) et de futures fonctionnalités liées aux objets
- `task` — pour des noms de tâches lisibles dans les logs
- `respoint` / `ResPointType` — piste alternative pour les ressources mystères, jamais testée directement

---

## 📓 Journal des découvertes et de l'avancement

Historique des trouvailles marquantes de ce projet, dans l'ordre
chronologique — utile pour comprendre certains choix de code inhabituels.

**Protocole de base**
Login en deux serveurs (LS puis GS), architecture à deux appareils imposée
par une vérification d'empreinte TCP. Plusieurs messages peuvent arriver
concaténés dans un seul paquet TCP.

**Le vrai bug du heartbeat**
Le "ping" utilisé initialement n'était pas un keepalive du tout mais
`kMsgCL2GSEnterGameRequest` (usage unique). Le vrai keepalive est
`kMsgCL2GSKeepLiveRequest` (type `10006`). Expliquait la quasi-totalité
des coupures de connexion après 1-2 minutes.

**Le piège des valeurs par défaut Protobuf**
Un champ valant `0` n'est **jamais transmis** sur le réseau. Le code
d'erreur `5809` (récupération de troupes) est renvoyé aussi bien pour
"encore en cours" que pour "caserne vide" (statut absent, donc
implicitement 0) — deux situations demandant une réaction opposée.

**Compression zlib des grosses réponses**
`CityInfoReply` et d'autres réponses volumineuses arrivent enveloppées
dans un `CompressedMessage` générique (type `14028`, zlib), géré
automatiquement par `find_message_of_type()`.

**Ressources mal nommées**
`CurrencyType` 2 s'appelle en interne `kCurrencyTypeOil` mais correspond
à la **Pierre** affichée en jeu — nom de code hérité sans rapport avec
l'affichage, confirmé par comparaison directe avec des captures d'écran.

**Gains hors ligne : mystère non résolu**
Malgré plusieurs captures ciblées avec des valeurs visibles à l'écran,
**aucune** n'a jamais été retrouvée dans le trafic réseau. Fonctionnalité
désactivée — de toute façon peu utile pour un bot qui tourne en continu.

**Changement de compte : le piège `KEY_UUID`**
En passant à un second compte, le `KEY_UUID` a été incorrectement
recalculé depuis le champ `"key"` d'un JWT — alors qu'une comparaison
octet-par-octet avec le trafic réel de l'app a confirmé que ce champ ne
change jamais, quel que soit le compte connecté.

**Multi-casernes et découverte de bâtiments**
`army_id` semble être une constante globale du jeu (confirmée identique
sur deux comptes différents), tandis que `barrack_id` reste propre à
chaque ville. `get_city_buildings()` liste tous les bâtiments d'un compte
automatiquement.

**TDCity et quêtes principales**
Une session de capture "libre" a révélé un système de combats de zone
entièrement séparé, résolu **instantanément** côté serveur.

**Le bug de `recv_all()` et les coupures mystérieuses**
Une fonction censée attendre "un silence de X secondes" pouvait
s'éterniser indéfiniment si le serveur envoyait une grosse réponse en
petits paquets espacés de moins que ce délai. Corrigé en ajoutant une
limite de temps **totale**, indépendante des pauses entre paquets.

**Recherche, hôpital, tâches de chapitre**
La lecture exhaustive d'une grosse capture (131 types de messages
différents) a révélé plusieurs systèmes jamais explorés d'un coup.

**Le système de combat contre les Corrompus**
Repéré via une notification "radar" passive, puis simplifié en
découvrant `MapSearchRequest` — une requête unique (niveau en paramètre)
qui donne directement la cible à attaquer. Composition d'attaque vérifiée
**octet par octet** contre une vraie capture avant intégration.

**Deux casernes mal étiquetées (pas un bug fonctionnel)**
Les commentaires associaient `barrack_id=1004` aux "lanceurs de haches"
et `barrack_id=8` aux "berserkers" — en réalité l'inverse, révélé par les
vrais noms de bâtiments extraits via AssetStudio. L'entraînement
fonctionnait déjà correctement (le serveur valide la compatibilité
army_id/bâtiment), seule l'étiquette en commentaire était fausse.

**Optimisation cassée par elle-même : appels réseau redondants**
L'ajout du calcul direct de quantité max de troupes a introduit un
nouveau problème : chaque caserne en mode `"max"` refaisait
indépendamment les mêmes gros appels réseau (liste des bâtiments +
ressources), au lieu de les partager. Avec 4 casernes, cela quadruplait
inutilement la charge et a provoqué de nouvelles coupures de connexion.
Corrigé en ne récupérant ces informations qu'**une seule fois** par
passage, partagées entre toutes les casernes du cycle.

**Le vrai bug de `PlayerAttribute` (type vs sub_type)**
Le champ "type" de `PlayerAttribute` est une **catégorie générale**
(`kPlayerAttrCurrency=1` regroupe TOUTES les monnaies confondues), pas un
identifiant précis — c'est le champ "sub_type", totalement ignoré par le
code jusque-là, qui précise LEQUEL. Ce bug expliquait un "faux pic"
observé bien plus tôt dans le projet (un autre type d'attribut, comme la
Puissance, partageant occasionnellement une valeur dans la même
fourchette que la monnaie) — corrigé en suivant désormais les deux
champs ensemble.

**Percée AssetStudio : calcul direct du max de troupes**
Face à l'impossibilité d'obtenir le "maximum entraînable" par le réseau,
l'extraction directe des tables `troop` et `city_barracks_lv` a permis de
**calculer** ce maximum au lieu de le deviner par tâtonnement réseau
successif — un seul appel suffit désormais dans la grande majorité des cas.

**Percée AssetStudio : traduction complète et combat entièrement automatique**
L'extraction de `string_fr` (30958 entrées de traduction) a permis
d'afficher enfin de vrais noms partout dans les logs, et de corriger au
passage l'étiquetage erroné des casernes. L'extraction de `monster.json`
(filtrée sur le bon `MonsterTypeId`, après une première tentative
incohérente qui mélangeait tous les types de monstres) a révélé la vraie
table "niveau → quantité de troupes recommandée", rendant le système de
combat automatique **totalement autonome** : recherche, calcul de la
composition, attaque, sans plus aucune valeur à deviner manuellement.

**La chasse infructueuse au roster de héros**
Recherche exhaustive sur deux captures réseau ciblées (dont une avec des
clics individuels sur chaque héros) : aucune requête dédiée "liste de mes
héros" trouvée. Plusieurs fausses pistes prometteuses écartées après
vérification du contenu réel (une liste de primes/courrier partageait par
coïncidence des motifs numériques avec des ID de héros). Conclusion : les
héros possédés ne sont visibles que par sous-produit de données d'Arène
PvP (formations de défense), qui ne couvrent pas forcément l'intégralité
du roster — la table de noms par ID reste la méthode la plus fiable.

---

## 🚧 Ce qui manque (contributions bienvenues)

- [ ] Table de traduction des codes de ressources mystères (`2414`/`2424`)
- [ ] Résultat du combat contre un Corrompu (victoire/défaite, butin) — on sait lancer l'attaque, pas encore suivre son issue
- [ ] Système d'auto-combat natif du jeu (`StartAutoFightMonsterRequest`) — repéré mais jamais capturé en usage réel
- [ ] Requête dédiée de liste du roster de héros (recherche exhaustive déjà tentée, sans succès)
- [ ] Sign-in quotidien (jamais confirmé fonctionnel)
- [ ] Construction de nouveaux bâtiments (nécessite un choix d'emplacement)
- [ ] Système citoyen complet (`Appoint`→`Arrived`→`Settle`, complexe)
- [ ] Soin à l'hôpital automatique (nécessite de connaître le nombre de blessés par type)

---

## 🔄 Renouvellement des identifiants

Le `WEB_SESSION` (JWT) reste valide plusieurs jours. Si `ls_login.py`
échoue de façon persistante, **vérifie d'abord que le vrai jeu se
connecte normalement** avant de soupçonner un token expiré — dans notre
historique, un token identique restait valide plusieurs jours, et le vrai
problème était ailleurs (`KEY_UUID`, voir le journal ci-dessus).

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
`libil2cpp.so`, **non redistribués ici**). Certaines données de
configuration statiques ont été extraites séparément via AssetStudio
depuis les assets Unity du jeu.

---

## 🤝 Contribuer

**Process type pour ajouter une action réseau :**
1. Trouve le nom du message dans un dump IL2Cpp (`kMsgCL2GS...Request`)
2. Convertis sa valeur en hex little-endian
3. Trouve la classe correspondante pour ses champs
4. Capture une vraie requête/réponse par `tcpdump` pour valider
5. Ajoute la fonction dans le module d'action approprié
6. Ajoute les nouvelles options dans `bot_config.py`, jamais dans `gs_bot.py`

**Process type pour extraire une donnée de configuration :**
1. Trouve le nom de classe C# probable dans `dump.cs`
2. Cherche ce nom (ou une variante proche) dans AssetStudio, filtre `MonoBehaviour`
3. Vérifie que le contenu correspond (champs cohérents, valeurs plausibles) avant d'intégrer
4. **Attention aux tables mélangeant plusieurs sous-catégories** (comme `monster.json`) — vérifie toujours la cohérence des valeurs en filtrant sur le bon identifiant avant de faire confiance aux données

---

<div align="center">

*Fait avec 🍵 et beaucoup de paquets réseau capturés.*

</div>
