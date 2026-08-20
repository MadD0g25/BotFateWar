<div align="center">

# ⚔️ Fate War Bot

**Unofficial Python client for Fate War (IGG)**
*Complete reverse-engineering of the network protocol — zero external dependencies*

[![Python](https://img.shields.io/badge/Python-3.7+-blue.svg)](https://www.python.org/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
[![Platform](https://img.shields.io/badge/Login-iOS%20required-lightgrey.svg)](#-important-warnings)

</div>

---

## 📖 Table of Contents

- [Important warnings](#-important-warnings)
- [How it works](#-how-it-works)
- [Project structure](#-project-structure)
- [Installation](#-installation)
- [Usage](#-usage)
- [Configuration: retrieving your credentials](#-configuration-retrieving-your-credentials)
- [Features](#-features)
- [Crash recovery](#-crash-recovery)
- [Capturing your own IDs](#-capturing-your-own-ids)
- [Game data extraction (AssetStudio)](#-game-data-extraction-assetstudio)
- [Discovery and progress log](#-discovery-and-progress-log)
- [What's missing](#-whats-missing--contributions-welcome)
- [Renewing credentials](#-renewing-credentials)
- [Protocol structure](#-protocol-structure)
- [Contributing](#-contributing)

---

## ⚠️ Important warnings

> **Unofficial project**, not affiliated with IGG. Use at your own risk —
> this may violate the game's terms of service.

| Point | Details |
|---|---|
| 🍎 **iOS Login only** | Logging into the *Login Server* currently only works from a real Apple device (iPhone/iPad/Mac). A low-level network fingerprint check blocks connections from Linux. |
| 📱 **a-Shell recommended** | On iOS, run the script in [a-Shell](https://apps.apple.com/app/a-shell/id1473805438) (free). |
| ⏱️ **No continuous bot on iOS** | Because iOS apps are suspended in the background, a-Shell cannot run a bot for hours — hence the dual-device architecture below. |
| 🚦 **Possible rate-limiting** | Rate-limiting appears to apply to Login Server connection attempts after multiple rapid tries — let it rest for 1-2 hours if persistent. |
| ⚔️ **Auto-battle = high risk** | The monster attack feature sends real troops. Always double-check your configuration before enabling it. |
| 🕐 **Server maintenance** | Disconnections after several hours of continuous operation may simply be scheduled server maintenance, not a bot bug. |

---

## 🏗️ How it works

Login takes place in two steps across two different servers. Only
the first step requires an Apple device; the second can run
**indefinitely** on any machine (Raspberry Pi, Linux PC, Mac).

```
 📱 iPhone (a-Shell)                    🖥️  Raspberry Pi / Linux
┌─────────────────────┐    nonce      ┌──────────────────────────────┐
│   ls_login.py         │ ─(network,──▶│   gs_bot.py + bot_config.py    │
│  → Login Server login │  ~1 second) │  → Game Server login         │
│  → gets the nonce     │              │  → synchronization           │
│  → sends it to Pi     │              │  → in-game actions           │
└─────────────────────┘              │  → autonomous infinite loop  │
                                       │     (survives crashes)       │
                                       └──────────────────────────────┘
```

---

## 📦 Project structure

| File | Role |
|---|---|
| `bot_config.py` | **All configuration** — barracks, buildings, guild, battles, TDCity... The only file you need to edit day-to-day. |
| `fatewar_core.py` | Low-level Protobuf encoding/decoding, logging, persistent state, automatic zlib decompression, network reception with total timeout |
| `fatewar_login.py` | Login Server + Game Server connection, session keepalive |
| `fatewar_actions_troops.py` | Troop training and collection — direct calculation of maximum trainable units |
| `fatewar_actions_building.py` | Building upgrades, structural/queue error management |
| `fatewar_actions_rewards.py` | Offline rewards, tasks/quests, mail, guild, citizen collection, farm |
| `fatewar_actions_tdcity.py` | TDCity zone battles (plot exploration), main quests |
| `fatewar_actions_misc.py` | Personal research, chapter/daily rewards, hero talents, hospital healing |
| `fatewar_actions_battle.py` | Automatic Corrupted monster search and attack |
| `fatewar_troop_data.py` | **Game data extracted via AssetStudio** — per-unit resource cost for 321 troops, training queue capacity per level (0-30), recommended troop count per Corrupted level (1-30) |
| `fatewar_names.py` | **Translations extracted via AssetStudio** — 43 hero names, 44 building names |
| `fatewar_resources.py` | Real-time resource totals, list of city buildings |
| `gs_bot.py` | **Main script (Pi)** — orchestrates all above modules, reads `bot_config.py` |
| `ls_login.py` | **iPhone script** — initial login only |

This separation allows you to add new options (`bot_config.py`) or
new actions (new `fatewar_actions_*.py` module) without ever
touching the core `gs_bot.py`.

---

## 📦 Installation

On **both devices**, place the required files in the same
directory (see table below):

```bash
git clone 
cd fatewar-bot
cp config.example.py config.py
cp bot_config.example.py bot_config.py
```

Edit `config.py` with your credentials (see
[Configuration](#-configuration-retrieving-your-credentials)), and
`bot_config.py` with your barracks/options (see
[Capturing your own IDs](#-capturing-your-own-ids)).

In `ls_login.py`, set your Raspberry Pi's local IP:

```python
PI_HOST = "192.168.1.XXX"   # find it using "hostname -I" on the Pi
```

**Required files per device:**

| File | iPhone (a-Shell) | Pi / Linux |
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

## ▶️ Usage

**1. On the Pi**, start it first — it will wait for incoming connections:

```bash
python3 gs_bot.py
```

**2. On the iPhone**, once "Waiting for nonce..." is displayed:

```bash
python3 ls_login.py       # default LS server
python3 ls_login.py 2     # alternative LS server if rate-limited
```

The nonce is transferred automatically, and the bot starts **immediately**
on the Pi. You can close a-Shell afterwards — the Pi will keep running on its own,
potentially for hours (see [Crash recovery](#-crash-recovery)).

**For a new session** (the GS connection eventually expires), rerun
`gs_bot.py` then `ls_login.py`. State information (barracks, buildings,
TDCity position) is automatically retained.

---

## 🔑 Configuration: retrieving your credentials

### Prerequisites
- An iPhone/iPad with Fate War installed
- A network capture app with MITM certificate (HAR export support)

### Step 1 — Capture a login session
1. Completely close Fate War, start your network capture
2. Open Fate War, log in, let it load until you reach your base
3. Stop the capture and export as HAR

### Step 2 — `WEB_SESSION` and `USER_ID`
Look for a request targeting `apis-dsa.iggapis.com/ums/member/binding?access_token=eyJ...`.
This parameter is your `WEB_SESSION` value.

Decode the second part (between the two dots) using base64:
```bash
echo "MIDDLE_PART" | base64 -d
```
*(add `=` padding at the end if needed)*. The resulting JSON contains `"sub"` →
your `USER_ID` value.

> ⚠️ **This JSON also contains a `"key"` field — this is NOT your
> `KEY_UUID` value, despite appearances.** See the next step and the
> [discovery log](#-discovery-and-progress-log).

### Step 3 — `KEY_UUID` (watch out, it's a trap)
`KEY_UUID` is an identifier tied to **the device/app installation**,
not your game account. It stays **identical** even if you switch
IGG accounts on the same phone.

To find it reliably: capture **raw TCP traffic** (not HTTPS)
on port `9310` during a real in-app login, and read
**field 10** of the `kMsgCL2LSLoginRequest` query directly — see
`build_ls_login_packet()` in `fatewar_login.py`. It looks like
`1D18308B-89D9-41CF-83F5-372A0B07A6A9`.

### Step 4 — `DEVICE_ID`
Find an HTTPS request containing `device_id=` in its URL.

### Step 5 — `GAME_ID`, `APP_VERSION`, `DEVICE_MODEL`, `GPU_MODEL`
```python
APP_VERSION = "1.2.20"
DEVICE_MODEL = "iPhone16,2"
GPU_MODEL = "Apple A17 Pro GPU"
GAME_ID = "11570603034"
```

### Step 6 — Fill in `config.py`
```bash
cp config.example.py config.py
```

---

## ✨ Features

| Action | Status | Module | Details |
|---|:---:|---|---|
| **Full login** (LS + GS) | ✅ Stable | `fatewar_login.py` | Two devices, fallback LS server |
| **Session keepalive** | ✅ Stable | `fatewar_login.py` | Native game keepalive, every 5s |
| **Multi-barracks training** | ✅ Stable | `fatewar_actions_troops.py` | "Max" quantity **calculated directly** (barracks level + real cost + resources) |
| **Troop collection** | ✅ Stable | `fatewar_actions_troops.py` | Distinguishes "in progress" from "empty barracks" |
| **All buildings upgrade** | ✅ Stable | `fatewar_actions_building.py` | Auto-discovery, concurrent queue handling, human-readable names |
| **Personal research** | ✅ Stable | `fatewar_actions_misc.py` | Auto-start and claim |
| **Auto-combat vs Corrupted** | ✅ Stable (risky) | `fatewar_actions_battle.py` | Search by level, immediate attack, **troop count calculated automatically** by level |
| **Hospital healing** | 🔧 Available, unautomated | `fatewar_actions_misc.py` | Requires knowing injured count per troop type |
| **Tasks (guild/main/chapter/daily)** | ✅ Stable | multiple modules | Continuous listening or batch claiming |
| **Mail** | ✅ Stable | `fatewar_actions_rewards.py` | Auto detection and claiming |
| **Guild (resources/help/donations/gifts)** | ✅ Stable | `fatewar_actions_rewards.py` | Can be toggled off entirely |
| **Hero talents** | ✅ Stable | `fatewar_actions_misc.py` | Replicates the in-app "recommended" button |
| **Citizen collection / Farm** | ✅ Stable | `fatewar_actions_rewards.py` | Account-specific IDs |
| **TDCity zone battles** | ✅ Stable | `fatewar_actions_tdcity.py` | Incremental exploration, configurable limit |
| **Real resource totals** | ✅ Stable | `fatewar_resources.py` | All main resources confirmed |
| **Readable log names** | ✅ Stable | `fatewar_names.py` | Heroes and buildings displayed by real names |
| **Crash recovery** | ✅ Stable | `fatewar_core.py` | State saved to disk, clean merge |
| **Offline rewards** | ❌ Disabled | — | Never confirmed transmitted via network |
| **Daily sign-in** | ❌ Disabled | — | Never confirmed functional |
| **Full citizen system** | 🔍 Spotted, unimplemented | — | Too complex (UUID, multi-step) |
| **Construct new building** | 🔍 Spotted, unimplemented | — | Requires slot selection |
| **In-game auto-battle system** | 🔍 Spotted, unimplemented | — | Never captured in real usage |
| **Hero roster auto-discovery** | ❌ Abandoned | — | No dedicated request found after exhaustive search (see log) |

---

## 🔄 Crash recovery

The bot automatically saves the known end timestamp for each barracks
and the current TDCity position to `fatewar_state.json` on every update,
**merging** with existing data. If the bot crashes or restarts, it
resumes directly with known times.

---

## 🏰 Capturing your own IDs

### Barracks (`TRAINING_SLOTS`)
Capture traffic during manual training, look for message type
`10402` (`kMsgCL2GSTrainRequest`). The payload contains `army_id` + `count` +
`barrack_id`.

> 💡 `army_id` appears to be a global game constant (confirmed
> identical across two different accounts). `barrack_id` is unique to
> each city — its **building type** (and actual name) can be
> found in `fatewar_names.py` once `get_city_buildings()` runs.

### Buildings
No capture needed! `AUTO_UPGRADE_ALL_BUILDINGS = True` automatically
discovers and upgrades everything available.

### Corrupted Monster Battles (`BATTLE_HERO1/2`)
Capture the manual flow: search icon → search → Attack → gather
troops → launch. Look for `kMsgCL2GSCreateMarchRequest` (type `10126`).
Alternative without capture: check `fatewar_names.py` (HERO_NAMES)
to see if your preferred hero is already listed.

### Personal Research / Guild / Citizens / Farm
See comments in `bot_config.py` — each requires a targeted packet
capture of the corresponding in-game action.

---

## 🧰 Game data extraction (AssetStudio)

In addition to the network protocol, certain static game configuration
data can be extracted directly from app assets using
**AssetStudio** ([github.com/aelurum/AssetStudio](https://github.com/aelurum/AssetStudio)),
without network capturing.

**Summary procedure:**
1. Open AssetStudio, load the extracted `assets` folder from the APK
2. Configure IL2Cpp support using `global-metadata.dat` + `libil2cpp.so`
3. Filter by `MonoBehaviour` type, search by name (`troop`, `hero`,
   `city_building`, `city_barracks_lv`, `science`, `monster`, `string_fr`...)
4. **Dump** tab to view structured content, **Export** to extract

**Already extracted and integrated:**
- `troop` (321 troops) → per-unit resource cost (`fatewar_troop_data.py`)
- `city_barracks_lv` (levels 0-30) → training queue capacity per barracks level
- `monster` (4914 entries, filtered on `MonsterTypeId=1003`) → recommended troop count per Corrupted level (levels 1-30)
- `string_fr` (30958 entries) → **complete translation table**: hero names (`hero_nameXXXXX`) and building names (`ss_buildingnameXXXX`)
- `city_building` → building structure, naming keys
- `science` → personal research tree structure (costs, prerequisites, levels)

**Unsuccessful extraction attempts** (unfruitful searches despite multiple tries):
- Resource/currency type mapping table (`CurrencyType`) — codes `2414`/`2424` remain unidentified, no obviously named table found
- Guild research (`GuildTech`) — does not seem to exist under this name, or uses an unidentified structure
- **Complete roster of owned heroes** — despite two targeted captures and an exhaustive search of the initial login burst (81 message types, including compressed content), no dedicated request was found. Conclusion: this data is likely cached client-side upon account creation and never retransmitted over the network. Workaround: heroes can be identified by **name** directly via `string_fr.json` → `fatewar_names.py` (HERO_NAMES), without network captures.

**Other potential avenues for future work:**
- `item` — for hospital healing (injured troop types) and future item-related features
- `task` — for human-readable task names in logs
- `respoint` / `ResPointType` — alternative lead for mystery resources, never directly tested

---

## 📓 Discovery and progress log

Chronological history of key breakthroughs in this project —
helpful for understanding specific unusual code choices.

**Base protocol**
Two-server login sequence (LS then GS), dual-device architecture imposed
by TCP fingerprinting checks. Multiple messages can arrive concatenated
within a single TCP packet.

**The real heartbeat bug**
The "ping" initially used was not a keepalive at all, but
`kMsgCL2GSEnterGameRequest` (one-time use). The actual keepalive is
`kMsgCL2GSKeepLiveRequest` (type `10006`). This explained nearly
all connection drops occurring after 1-2 minutes.

**The Protobuf default value trap**
A field equal to `0` is **never sent** over the wire. Error code
`5809` (troop collection) is returned for both "still in progress"
and "empty barracks" (absent status, thus implicitly 0) — two
states requiring opposite handling.

**zlib compression on large responses**
`CityInfoReply` and other large responses arrive wrapped in a
generic `CompressedMessage` (type `14028`, zlib), automatically
handled by `find_message_of_type()`.

**Mislabeled resources**
`CurrencyType` 2 is named `kCurrencyTypeOil` internally but corresponds
to **Stone** displayed in-game — a legacy internal codename unrelated
to UI labels, confirmed via direct comparison with screenshots.

**Offline rewards: unsolved mystery**
Despite multiple targeted captures showing visible rewards on screen,
**none** were ever detected in network traffic. Feature disabled —
of limited utility anyway for a continuously running bot.

**Account switching: the `KEY_UUID` trap**
When switching to a second account, `KEY_UUID` was incorrectly
recomputed from a JWT's `"key"` field — whereas byte-for-byte
comparison with actual app traffic confirmed this field never changes,
regardless of the logged-in account.

**Multi-barracks and building discovery**
`army_id` appears to be a global game constant (confirmed identical
across two different accounts), while `barrack_id` is unique to each
city. `get_city_buildings()` lists all buildings on an account
automatically.

**TDCity and main quests**
A "free-play" capture session revealed an entirely separate zone battle
system, resolved **instantly** server-side.

**The `recv_all()` bug and mysterious disconnects**
A function supposed to wait for "X seconds of silence" could
hang indefinitely if the server sent a large response split into small
chunks spaced slightly under that delay. Fixed by adding a **total**
timeout limit, independent of inter-packet pauses.

**Research, hospital, chapter tasks**
Exhaustive inspection of a large capture (131 different message types)
revealed several unmapped systems all at once.

**Corrupted battle system**
Spotted via a passive "radar" notification, then simplified upon
discovering `MapSearchRequest` — a single request (level as parameter)
that directly returns the attack target. Attack payload verified
**byte-by-byte** against a real capture prior to integration.

**Two mislabeled barracks (not a functional bug)**
Comments linked `barrack_id=1004` to "axe throwers" and `barrack_id=8`
to "berserkers" — actually reversed, as revealed by true building
names extracted via AssetStudio. Training functioned properly
anyway (server validates army_id/building compatibility), only comment
labels were wrong.

**Self-defeating optimization: redundant network calls**
Adding direct max troop calculations introduced a new issue:
each barracks set to `"max"` mode independently repeated the same heavy
network calls (building list + resources), instead of sharing them.
With 4 barracks, this quadrupled load unnecessarily and caused
new disconnects. Fixed by fetching this data **only once**
per cycle, shared across all barracks.

**The real `PlayerAttribute` bug (type vs sub_type)**
The "type" field in `PlayerAttribute` is a **general category**
(`kPlayerAttrCurrency=1` groups ALL currencies together), not a specific
identifier — the "sub_type" field, previously ignored by the code,
specifies WHICH ONE. This bug explained a "ghost spike" observed
much earlier in the project (another attribute type, like Might,
occasionally sharing a value in the same range as currency) — fixed
by tracking both fields together.

**AssetStudio breakthrough: direct max troop calculation**
Faced with the inability to obtain the "trainable maximum" via network,
direct extraction of `troop` and `city_barracks_lv` tables enabled
**calculating** this maximum instead of guessing via trial-and-error network
requests — a single call now suffices in the vast majority of cases.

**AssetStudio breakthrough: full translation & fully automated battle**
Extracting `string_fr` (30,958 translation entries) allowed showing
proper names throughout logs, correcting mislabeled barracks along the
way. Extracting `monster.json` (filtered on correct `MonsterTypeId`,
after an initial failed attempt that mixed all monster types) revealed
the true "level → recommended troop count" table, making the automated
battle system **completely autonomous**: searching, computing army composition,
and attacking without needing manual parameter guessing.

**The fruitless search for the hero roster**
Exhaustive search across two targeted network captures (including one
with individual clicks on every hero): no dedicated "owned heroes list"
request was found. Several promising false leads were dismissed after
verifying actual payload contents (a list of bounties/mail coincidentally
shared numerical patterns with hero IDs). Conclusion: owned heroes
are only visible as a byproduct of PvP Arena data (defense formations),
which does not necessarily cover the full roster — mapping names via ID
remains the most reliable method.

---

## 🚧 What's missing (contributions welcome)

- [ ] Translation mapping table for mystery resource codes (`2414`/`2424`)
- [ ] Corrupted battle outcome processing (victory/defeat, loot) — attack launching works, tracking outcome does not yet
- [ ] Native in-game auto-battle system (`StartAutoFightMonsterRequest`) — spotted but never captured in actual use
- [ ] Dedicated request for owned hero roster list (exhaustive search already attempted without success)
- [ ] Daily sign-in (never confirmed functional)
- [ ] Construction of new buildings (requires slot selection)
- [ ] Full citizen system (`Appoint`→`Arrived`→`Settle`, complex)
- [ ] Automated hospital healing (requires knowing injured count per type)

---

## 🔄 Renewing credentials

`WEB_SESSION` (JWT) remains valid for several days. If `ls_login.py`
persistently fails, **first verify that the actual game logs in normally**
before assuming token expiration — in our experience, a single token
remained valid for days, and root causes lay elsewhere (`KEY_UUID`, see log above).

---

## 🧩 Protocol structure

Binary Protobuf over raw TCP, simple framing:

```
┌──────────────────┬──────────────────┬─────────────────┐
│  Length (2 B)    │  Msg Type (2 B)  │  Protobuf Body  │
│  little-endian   │  little-endian   │                 │
│  self-inclusive  │                  │                 │
└──────────────────┴──────────────────┴─────────────────┘
```

Large responses may be zlib-compressed and wrapped in a
generic `CompressedMessage` (type `14028`) —
`find_message_of_type()` in `fatewar_core.py` handles this decompression
automatically.

Message types and field structures were extracted via IL2Cpp decompilation
of the official client (`global-metadata.dat` + `libil2cpp.so`, **not
redistributed here**). Certain static configuration data was extracted
separately via AssetStudio from Unity game assets.

---

## 🤝 Contributing

**Typical workflow to add a network action:**
1. Find the message name in an IL2Cpp dump (`kMsgCL2GS...Request`)
2. Convert its value to little-endian hex
3. Find the corresponding class for its fields
4. Capture a real request/reply using `tcpdump` to validate
5. Add the function in the appropriate action module
6. Add new configuration options in `bot_config.py`, never in `gs_bot.py`

**Typical workflow to extract configuration data:**
1. Find candidate C# class names in `dump.cs`
2. Search for the name (or close variant) in AssetStudio, filter `MonoBehaviour`
3. Verify contents match (consistent fields, plausible values) before integrating
4. **Beware of tables merging multiple sub-categories** (like `monster.json`) — always check data consistency by filtering on the correct identifier before relying on values

---

<div align="center">

*Made with 🍵 and lots of captured network packets.*

</div>
