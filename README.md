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
- [Installation](#-installation)
- [Utilisation](#-utilisation)
- [Configuration : récupérer tes identifiants](#-configuration--récupérer-tes-identifiants)
- [Fonctionnalités](#-fonctionnalités)
- [Capturer ton `barrack_id`](#-capturer-ton-barrack_id)
- [Ce qui manque](#-ce-qui-manque--contributions-bienvenues)
- [Journal des collectes](#-journal-des-collectes)
- [Renouveler tes identifiants](#-renouveler-tes-identifiants)
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
| 🚦 **Rate-limit possible** | Une limitation de fréquence semble exister sur les tentatives de connexion au Login Server — évite de relancer les scripts en boucle rapide. |

---

## 🏗️ Comment ça marche

Le login se fait en deux étapes, auprès de deux serveurs différents. Seule
la première nécessite un appareil Apple ; la seconde peut tourner
**indéfiniment** sur n'importe quelle machine (Raspberry Pi, PC Linux, Mac).

```
┌─────────────────────┐        nonce         ┌──────────────────────────────┐
│   📱 iPhone           │  ──────────────────▶ │   🖥️  Raspberry Pi / Linux    │
│   (a-Shell)           │      (réseau,         │                                │
│                        │       ~1 seconde)     │                                │
│   ls_login.py          │                       │   gs_bot.py                   │
│   → login Login Server │                       │   → login Game Server         │
│   → récupère le nonce  │                       │   → synchronisation           │
│   → l'envoie au Pi     │                       │   → actions de jeu            │
│                        │                       │   → maintien de session       │
└─────────────────────┘                       │      (tourne en continu)       │
                                                └──────────────────────────────┘
```

`ls_login.py` se connecte au Login Server, récupère un nonce de session,
puis l'envoie **automatiquement** par le réseau à `gs_bot.py` qui tourne en
écoute sur l'autre appareil. Pas de copie manuelle : le transfert prend
environ une seconde, ce qui évite tout risque d'expiration du nonce.

---

## 📦 Installation

Sur les **deux appareils**, place ces fichiers dans le même dossier :

Puis édite `config.py` avec tes propres identifiants
(voir [Configuration](#-configuration--récupérer-tes-identifiants) ci-dessous).

Dans `ls_login.py`, renseigne l'IP locale de ton Raspberry Pi :

```python
PI_HOST = "192.168.1.XXX"   # trouve-la avec "hostname -I" sur le Pi
PI_PORT = 5555               # peut rester par defaut
```

**Fichiers requis par appareil :**

| Fichier | iPhone (a-Shell) | Pi / Linux |
|---|:---:|:---:|
| `config.py` | ✅ | ✅ |
| `fatewar_protocol.py` | ✅ | ✅ |
| `ls_login.py` | ✅ | ❌ |
| `gs_bot.py` | ❌ | ✅ |

---

## ▶️ Utilisation

**1. Sur le Pi**, lance en premier — il se met en attente :

```bash
python3 gs_bot.py
```
```
En attente du nonce sur le port 5555...
(lance ls_login.py sur ton iPhone maintenant)
```

**2. Sur l'iPhone**, une fois le message ci-dessus affiché :

```bash
python3 ls_login.py
```

Le nonce est transmis automatiquement, et le bot démarre **immédiatement**
côté Pi. Tu peux ensuite fermer a-Shell — son rôle est terminé, le Pi
continue seul.

**Pour relancer une session plus tard** (la session finit toujours par
expirer), relance simplement `gs_bot.py` sur le Pi puis `ls_login.py` sur
l'iPhone.

---

## 🔑 Configuration : récupérer tes identifiants

### Ce qu'il te faut

- Un iPhone/iPad avec Fate War installé
- Une app de capture réseau avec certificat MITM (recherche "network
  sniffer" sur l'App Store, doit pouvoir exporter en HAR)

### Étape 1 — Capturer une session de connexion

1. Ferme complètement Fate War (pas juste en arrière-plan)
2. Lance ton app de capture réseau, démarre l'enregistrement
3. Ouvre Fate War, laisse charger jusqu'à voir ta base
4. Arrête la capture, exporte en HAR

### Étape 2 — Extraire `WEB_SESSION`, `USER_ID`, `KEY_UUID`

Cherche une requête vers :
```
https://apis-dsa.iggapis.com/ums/member/binding?access_token=eyJ...
```
Le paramètre `access_token` (commence par `eyJ`, 3 parties séparées par des
points) est ta valeur `WEB_SESSION`.

Décode la 2e partie (entre les deux points) en base64 :
```bash
echo "PARTIE_DU_MILIEU" | base64 -d
```
*(ajoute des `=` à la fin si le décodage échoue — base64 attend un multiple
de 4 caractères)*

Le JSON obtenu contient :
- `"sub"` → ta valeur `USER_ID`
- `"key"` → ta valeur `KEY_UUID`

### Étape 3 — Extraire `DEVICE_ID`

Cherche une requête contenant `device_id=` dans son URL (endpoint de
logging/analytics). La valeur (format UUID) est ton `DEVICE_ID`.

### Étape 4 — `GAME_ID`, `APP_VERSION`, `DEVICE_MODEL`, `GPU_MODEL`

```python
APP_VERSION = "1.2.20"        # version actuelle de l'app
DEVICE_MODEL = "iPhone16,2"   # modele technique de ton iPhone
GPU_MODEL = "Apple A17 Pro GPU"
GAME_ID = "11570603034"       # identique pour tous les joueurs (a verifier
                                # si le login echoue de maniere inattendue)
```

### Étape 5 — Remplir `config.py`

```bash
cp config.example.py config.py
```
Édite `config.py` avec les valeurs récupérées ci-dessus.

---

## ✨ Fonctionnalités

| Action | Statut | Détail |
|---|:---:|---|
| **Login complet** (LS + GS) | ✅ Stable | Architecture à deux appareils |
| **Maintien de session** | ⚠️ Partiel | Heartbeat 5s, coupures occasionnelles après ~1-2 min (en cours de debug) |
| **Gains hors ligne** (`PrivilegeEscrow`) | ✅ Stable | Collecte automatique |
| **Ressources de production** (`CollectInfo`/`CollectResource`) | ✅ Stable | Vérifie et collecte |
| **Entraînement de troupes** (`Train`) | ✅ Confirmé | Nécessite ton `barrack_id` (voir plus bas) |
| **Tâches/quêtes terminées** (`TaskPeriod`) | ✅ Implémenté | Écoute les notifications serveur et réclame automatiquement |
| **Sign-in quotidien** (`SignInReward`) | ❌ Désactivé | Pas encore confirmé fonctionnel — voir [Ce qui manque](#-ce-qui-manque--contributions-bienvenues) |
| **Journal horodaté** | ✅ Stable | `fatewar_bot.log` |

---

## 🏰 Capturer ton `barrack_id`

Nécessaire pour l'entraînement de troupes — **unique à ta ville**, la
valeur fournie par défaut ne fonctionnera pas pour toi.

1. Capture le trafic TCP brut vers le Game Server (port `12040` ou `12042`)
   pendant que tu lances un entraînement manuellement dans l'app
2. Cherche le message client→serveur de type **10402**
   (`kMsgCL2GSTrainRequest`, octets `a2 28` après le préfixe de longueur)
3. Décode le corps Protobuf : sous-champ `army` (army_id + count) et champ
   `barrack_id` — voir `build_gs_login_packet()` dans `fatewar_protocol.py`
   pour un exemple de décodage
4. Remplace la valeur dans l'appel à `train_troops(...)` dans `gs_bot.py`

> 💡 `army_id` provient d'une table de configuration globale du jeu
> (`TroopCfgData`) — probablement identique pour tous les joueurs ayant le
> même type de troupe débloqué.

---

## 🚧 Ce qui manque (contributions bienvenues)

Le jeu comporte des **milliers** de types de messages. Voici ce qui reste à
faire, avec la même méthode que le reste du projet (chercher la classe dans
un dump IL2Cpp, décoder les champs, tester par capture réseau) :

- [ ] Débugger le sign-in quotidien (activité peut-être inactive, ou
      mauvais numéro de jour)
- [ ] Stabiliser le heartbeat sur de longues durées (coupures après ~1-2 min)
- [ ] Construction et amélioration de bâtiments
- [ ] Marches de troupes (attaque, récolte sur la carte du monde)
- [ ] Alliance (aide aux membres, dons, événements de guilde)
- [ ] Boîte mail (récupération des pièces jointes)
- [ ] Recherche technologique

---

## 📝 Journal des collectes

Chaque collecte réussie (gains hors ligne, ressources, entraînements,
tâches) est enregistrée avec horodatage dans `fatewar_bot.log`, créé
automatiquement à côté des scripts :

```
[2026-08-16 19:51:15] Entrainement lance : 50x armee 1201 (caserne 1007)
[2026-08-16 20:01:57] Gains hors ligne : rien a collecter cette fois.
```

---

## 🔄 Renouveler tes identifiants

Le `WEB_SESSION` (JWT) reste valide plusieurs jours mais finira par
expirer. Si `ls_login.py` échoue avec *"connexion réinitialisée"*, refais
une capture réseau (étapes 1-2 de la [Configuration](#-configuration--récupérer-tes-identifiants))
pour en récupérer un frais.

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

Les types de message et structures de champs ont été extraits par
décompilation IL2Cpp du client officiel (`global-metadata.dat` +
`libil2cpp.so`, **non redistribués ici** pour raisons de droits d'auteur).

---

## 🤝 Contribuer

Toute contribution pour décoder de nouvelles actions est bienvenue ! Voir
`fatewar_protocol.py` pour des exemples complets de décodage (structure
claire : `encode_field_varint`, `encode_field_string`, `walk_protobuf`,
`find_message_of_type`).

**Process type pour ajouter une action :**
1. Trouve le nom du message dans un dump IL2Cpp (`kMsgCL2GS...Request`)
2. Note sa valeur numérique, convertis en hex little-endian
3. Trouve la classe correspondante pour connaître ses champs
4. Capture une vraie requête/réponse par `tcpdump` pour valider
5. Ajoute la fonction dans `fatewar_protocol.py`, en suivant le style
   existant

---

<div align="center">

*Fait avec 🍵 et beaucoup de paquets réseau capturés.*

</div>
