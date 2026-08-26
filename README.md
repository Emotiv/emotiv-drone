# Emotiv Drone: BCI-Powered Flight Control

Control a DJI Tello drone using only your mind and head movements. This project bridges the **Emotiv EEG Headset** with the **DJI Tello Drone**, creating an immersive Brain-Computer Interface (BCI) for flight.

![UI Dashboard](bg.png)

## 🚀 Key Features

- **Intuitive Head Tracking**: Fly the drone naturally by tilting your head. 
  - **Pitch Forward/Back**: Moves the drone forward and backward.
  - **Roll Left/Right**: Tilts the drone to the side.
  - **Yaw Control**: Turn your head to rotate the drone.
- **Mental Command Integration**: Map trained thoughts (Push, Pull, Lift, etc.) to critical flight actions like **Take Off**, **Land**, or **Emergency Stop**.
- **Real-time Telemetry & Video**: The dashboard provides a live H.264 video feed from the drone and displays real-time battery status, altitude, temperature, and RC command logs.
- **Premium Dark Dashboard**: A custom-built PyQt6 interface designed for professional BCI experimentation.
- **60-second Ring Run**: A timed score attack in the simulator — collect glowing rings against the clock, then see where you landed on a local leaderboard. Built for passing one headset around a room: finish a run, hand over, next person trains and plays.
- **English and 中文**: Switch language from the header at any time — the whole interface follows immediately, no restart. Your choice is remembered in `config.json`.
- **Simulation Mode**: Test your BCI mapping and head tracking precision in a safe software-only environment before taking flight.

## 📡 How the Drone Connection Works

The connection between your computer and the DJI Tello is established over a dedicated WiFi link. Here is the step-by-step process:

1.  **Direct WiFi Link**: The DJI Tello acts as a WiFi Access Point. You must manually connect your computer's WiFi to the network broadcast by the drone (usually named `TELLO-XXXXXX`).
2.  **Communication Protocol**: Once connected, the application uses the **Tello SDK** via the `djitellopy` library. Communication happens over UDP:
    *   **Commands (Port 8889)**: For sending flight instructions (TakeOff, Land, RC movements).
    *   **State (Port 8890)**: For receiving real-time telemetry (battery, altitude, etc.).
    *   **Video (Port 11111)**: For streaming the live H.264 camera feed.
3.  **Dashboard Integration**: When you click **"Connect to Drone"** in the UI:
    *   The app initializes the Tello SDK and attempts to "ping" the drone.
    *   Upon success, it triggers a background **Video Thread** to start decoding the camera stream.
    *   It starts a 20Hz (50ms) **RC Control Loop** that continuously sends movement data to ensure responsive flight.

---

## 🏗 Project Architecture

The system is built on a modular architecture to ensure low latency and reliable data processing:

### 1. The Core Bridge (`drone_controller.py`)
The main engine that synchronizes data between the Emotiv Cortex API and the Tello SDK. It handles the WebSocket lifecycle, authentication, and data stream subscriptions.

### 2. Signal Processing (`bci_core/`)
- **QuaternionProcessor**: Converts raw spatial data from the headset into normalized Euler angles for flight control.
- **MentalCommandProcessor**: Filters and thresholds mental command data to prevent accidental triggers.

### 3. Drone Adaptation (`drone_adapter.py`)
Translates processed BCI signals into standard Tello RC (Remote Control) commands. It implements deadzones, sensitivity scaling, and command smoothing to ensure fluid flight.

### 4. Dashboard (`ui.py`)
A PyQt6-based graphical interface that provides:
- Live video decoding via OpenCV.
- Telemetry visualization.
- Interactive configuration of sensitivity and mental command thresholds.

---

## 🔒 Security & Configuration

We've implemented a split-configuration system to keep your development environment secure:

- **`config.json`**: Stores your sensitivity settings, flight limits, and mental command mappings. This file **is tracked** by Git, allowing you to share your fine-tuned flight profiles.
- **`credentials.json`**: Stores your sensitive Emotiv Client ID and Secret. This file is **automatically ignored** by Git to prevent accidental exposure of your credentials.
- **`config_manager.py`**: Automatically handles the merging and splitting of these files during runtime.

---

## 🛠 Prerequisites

- **Hardware**: 
  - DJI Tello Drone.
  - Emotiv Headset (Insight, EPOC, EPOC+, or EPOC X).
- **Software**:
  - Emotiv Cortex App (running and logged in).
  - Python 3.8 or higher.

---

## 📦 Installation & Setup

1. **Clone the repository**:
   ```bash
   git clone https://github.com/giovaniemotiv/emotiv-drone.git
   cd emotiv-drone
   ```

2. **Setup Virtual Environment**:
   ```bash
   python3 -m venv venv
   source venv/bin/activate
   pip install -r requirements.txt
   ```

3. **Configure Credentials**:
   Run the app once to generate the files, then enter your Emotiv Client ID and Secret in the UI dashboard. They will be saved securely to `credentials.json`.

---

## 🎮 Usage

### Launching the App
The easiest way to start is via the included shell script:
```bash
./run.sh
```

### Scope: the simulator

The real-drone path — Tello WiFi setup and the flight dashboard — is complete and
still in the tree, but its entry points are hidden while the simulator is the
product. Set `SHOW_REAL_DRONE = True` in `ui.py` to bring it back; no code was
removed and the page indices are unchanged.

The flow a player walks is: **pick a headset → check the sensors → train → fly**.
Three flags at the top of `ui.py` keep it that short, and each can be flipped
back on without touching anything else:

| Flag | Off means |
| :--- | :--- |
| `SHOW_AUTH_PAGE` | The credentials form is not a step. `cortex.py` carries the Cortex client id and secret, so it collects nothing the app uses. It is now a **Connection problem** screen, reached only on failure — see below. |
| `SHOW_MOTION_TUNING` | No ⚙ Configurations button, which is where head-tilt and deadzone tuning now lives. **🎯 Recenter** is the one motion control on the page. Values still come from `config.json`. |
| `SHOW_PROFILE_LIST` | No list of past profiles; each player types their own name. |

### The log file

Everything the app prints — the in-window log pane, the raw Cortex traffic, the
status changes — is mirrored to a file, so a problem can be diagnosed after the
window has been closed and from a packaged build with no console attached:

- **From a checkout:** `emotiv-drone.log` beside the source (git-ignored).
- **Installed:** `%APPDATA%\EmotivDrone\emotiv-drone.log` on Windows,
  `~/Library/Application Support/EmotivDrone/emotiv-drone.log` on macOS.

The path is printed at startup and shown on the **Connection problem** screen,
where someone about to report a fault will be looking. It rolls over at 4 MB
keeping one previous file, and `sys.excepthook` is redirected into it so an
unhandled exception is recorded rather than vanishing into a missing console.

Lines the app writes itself follow the UI language; raw Cortex output is
English either way.

### When the headset drops out

A headset going quiet mid-session used to look like the drone simply refusing
to respond — nothing detected it. Cortex warning 103 now surfaces as a
full-window notice, and the app spends **30 seconds** trying to get the device
back before giving up.

The Cortex *session* is deliberately left alone during that window. Reconnecting
the device is enough for the existing subscriptions to resume, so the loaded
profile and the run in progress both survive a brief dropout — the run clock
pauses and restarts from where it stopped. Contact data arriving again is what
counts as recovery. If the 30 seconds run out, the run is abandoned and the app
returns to the headset list.

### Getting out, and letting go of the headset

The training screens carry **Start over — back to headsets**. Training is the
longest part of the flow and the easiest to get stuck in — a bad take, the wrong
headset, the wrong person sitting down — and it previously had no exit at all.

Connecting to a different headset releases the current one first. Cortex
otherwise leaves the previous device connected and the new session still bound
to it.

### Picking a headset

The devices in range are shown as a **list**, not a dropdown: with several
headsets in a room, how many there are and what state each is in is the useful
information, and a collapsed combo hides exactly that until you click it.

Each row carries the product shot for that model, the id, its state, and **its
own Connect button** — selecting a device and then confirming were two steps for
one decision, since nobody highlights a headset they do not intend to use.
Double-clicking a row does the same thing. While a connection is in flight every
row's button is disabled, because two headsets cannot come up at once.

Model artwork is matched from the id prefix (`INSIGHT2-A3D208D9` → `insight.png`)
with the longest prefix winning, so INSIGHT2 is not swallowed by INSIGHT and an
unrecognised variant still shows its family. An unknown model just gets no
picture.

There is no connection status badge any more. It spent most of its life reading
"BCI: Scan Finished / Not Found", which told the user nothing the list does not
already show; connection progress goes to the log.

**Refresh** never sticks. It used to disable itself on the first press and stay
that way: the worker thread re-enabled it through `QTimer.singleShot(0, done)`,
and a timer created on a thread with no Qt event loop never fires. Both places
that did this now marshal back through `ui_task_signal`.

### Which way is left

`invert_yaw` belongs to the headset, not to the installation. It is `False` by
default — turning your head left steers left — and only MN8 overrides it,
because MN8 reports yaw the other way round.

It had been switched on at the *top level* of `config.json`, which is not the
same thing: every headset without an explicit profile inherits the top level, so
tuning done for an MN8 silently inverted Insight and EPOC X as well. The default
now lives in `DEFAULT_CONFIG` where the other motion settings are, and the
override stays where it belongs, in `device_profiles.MN8`.

### When the connection fails

Selecting a headset is step one; nothing is asked before it. If the app cannot
reach Cortex it stops waiting and shows a **Connection problem** screen, which
leads with the two things that are actually wrong in practice:

1. **EMOTIV Launcher is not running** (or is not signed in).
2. **This application has never been approved in it.**

The credentials sit below those, labelled as rarely being the problem, and the
exact message Cortex or the socket reported is shown in an amber banner above.
**Retry Connection** tears down the dead client and starts over.

Three failure signals feed that screen, none of which existed before — the app
used to sit on "Connecting…" indefinitely with EMOTIV Launcher closed:

- `connection_failed` — the websocket errored or closed before ever
  authorizing. A failing socket reports twice, once with the real reason and
  once with nothing, so the first specific message is the one kept.
- `access_right_pending` — `requestAccess` returned false. The approval banner
  appears on the headset screen, where the user already is.
- `access_right_rejected` — the user actively declined in EMOTIV Launcher
  (warning code 10). Nothing retries by itself from here, so this is stated
  plainly rather than left silent.

### Branding assets

Artwork lives in `assets/` and every piece is optional — a missing file means
that chrome is not drawn, so the app runs from a clean checkout with no images
at all.

| File | Where it appears |
| :--- | :--- |
| `assets/logo_white.png` | The persistent header on every page at 46px, held back to 75% opacity, and again at 132px above the title on the headset screen. |
| `assets/hero_drone.png` | Backdrop on the headset screen — centred, fitted to 88% of the page, drawn at 16% opacity. |

Both must be **transparent PNGs**. The artwork is white line work, so a JPEG of
the same image carries an opaque white background and renders as a white block
on the dark interface. The logo is a stacked lockup — drone mark over the
EMOTIV / BCI DRONE wordmark, about 3:2 — which is why it is given real height
rather than being squeezed into a slim header row; below roughly 40px the
second line stops being readable.

The hero is centred rather than corner-anchored because the drone is
left-right symmetric: bleeding one side off the edge reads as a mistake rather
than a crop.

`packaging/EmotivDrone.spec` ships the whole `assets/` directory, so the
desktop builds carry the branding too.

### One profile per player

The list of existing profiles is hidden (`SHOW_PROFILE_LIST` in `ui.py`). Each
player types their name, trains, and plays under that name — the profile name is
the leaderboard name, so nobody ends up on the board twice under two spellings.

### Tuning before a run

This page is laid out as a game rather than as another step in a form. The
scene fills it, and the chrome around it is arranged the way a game arranges it:

- **Player name, top left**, at scoreboard size — it is the one piece of
  identity on screen and the name that goes on the board.
- **▶ Start Run, bottom right**, large and green, the single thing the screen is
  asking you to do. The run length sits above it as a caption.
- **Secondary actions, bottom left**, deliberately quiet: Back, Recenter, Reset
  & Retrain, and the **Mental commands** sliders — one per trained command,
  setting how hard you have to think it before it fires. Changes apply live,
  which is the point. Values are pushed to Cortex on slider release rather than
  during the drag, since each call writes to the profile.
- **The controls are explained inside the scene**, not in a panel above it: the
  overlay names your own trained command and fades once the run is properly
  under way.

Everything else that used to sit in a column beside the scene is gone: flight
state, RC channel bars and the raw MOT/COM dump were each a readout of something
the simulator already shows, and they cost the game two thirds of the width. The
raw streams are still printed to the log pane. The step title, the subtitle and
the how-to panel went the same way — three layers of preamble above the thing
the player came for. The **Fullscreen** button is gone too; the page is the game
now, so there is less to escape from.

Head-tilt and deadzone tuning is behind `SHOW_MOTION_TUNING`. Adjusting it
mid-demo was how a working setup got broken between players, and **🎯 Recenter**
— which makes your current head position the new straight-ahead — covers the
adjustment that actually helps.

**♻ Reset & Retrain** erases the profile's training, including the neutral
baseline, and sends you back through the signal check. It is there because this
is the screen where you discover the training is no good.

### Handing the headset to the next player

**Finish — next player** deletes the trained profile, disconnects the headset,
rescans and drops you on the device list. The disconnect matters: without it the
next person sees a device still held open by the run that just ended. Nothing to confirm: the score already lives in
`leaderboard.json` independent of Cortex, so the name stays on the board for the
record while the training itself is binned. Landing on the device list rather
than profile creation is deliberate — the next person may be on a different
headset.

To keep a profile and only redo its training, use **♻ Reset & Retrain** on the
simulator screen instead.

Cortex will not modify a profile that is loaded on the headset, so both actions
unload it first. There is no single "reset profile" call either: the reset walks
the profile's active actions and erases them one at a time, neutral included.

### The signal check

Contact quality is drawn on a head seen from above, nose at the top, with each
sensor at its real place in the international 10–20 system — so a bad contact
points at the electrode to reseat rather than at a bar labelled `S2`. Electrode
names come from Cortex per headset, so an Insight shows its five and an EPOC X
its fourteen. Anything outside the 10–20 table is still drawn, in a row beneath
the head, rather than dropped.

The summary at the top is **contact quality as a percentage**, and so is the
gate on **Start Training** (50% or better).

It used to read the `signal` field, which is the *wireless link* between headset
and dongle — a different measurement entirely. A simulated headset pins that at
1, so the screen said "Overall Signal: Very Bad (1/4)" with every electrode
green, and produced advice about moving closer to the USB receiver on a screen
that is about electrodes. Cortex already ships the right number: the `OVERALL`
column of the contact-quality stream is a percentage. Where a headset does not
send one, the per-electrode 0–4 grades are averaged instead.

Bands match emotiv-brain-light — 80%+ good, 50%+ fair, below that poor — so the
two applications agree on what "good" means.

### Knowing the headset is still on

The flight screen and both training screens carry a **device pill**: a small head map, the headset id,
and one contact-quality percentage, modelled on the pill in
emotiv-brain-light and recoloured to this project's palette. A contact going
bad during a run otherwise shows up only as the drone quietly not responding,
and a training take recorded through a loose electrode is what produces a
profile that never works. The pill also carries the **headset battery**, which
turns amber below 40% and red below 20%.

Contact data is no longer gated on the signal-check page being open, and every
pill is driven from one place rather than each page wiring its own.

### Ring Run and the leaderboard

Pressing **Start Run** does not start the clock. A three-second countdown runs
first — *Get Ready!* over 3, 2, 1, then *Go!* — so nobody's timed round begins
while they are still looking at the button they pressed. The scene dims behind
it, the drone is reset, and nothing scores until *Go!*. Leaving the page
mid-countdown cancels it the same way leaving mid-run abandons the run.

On the **Fly the Simulator** screen, press **Start Run** — you play under the
name you trained your profile with. Rings spawn ahead of the drone for 60
seconds; each one is 10 points, and the clock turns red for the last ten. When
time is up you get your score, your position and the top five, with **Try
Again**, **Show Leaderboard**, or **Finish — next player**.

The result screen congratulates the player by position and says what they just
did — flew it with their mind. A top-three finish also gets confetti.

`FullscreenResultDialog` still exists and still works; with the Fullscreen
button removed nothing reaches it, so turning fullscreen back on restores that
path unchanged.

Scores live in `leaderboard.json` beside the other settings — one table per
computer, no account and nothing uploaded. Leaving the test screen mid-run
abandons that run rather than recording it.

### Language
Pick **English** or **中文** from the dropdown in the top-right corner. The change
applies live, and the app reopens in the same language next time.

Two things stay in English on purpose: the raw Cortex/MOT/COM stream dumps in
the log pane, and telemetry channel abbreviations (`PWR`, `ALT`, `THR`, `YAW`)
on the HUD — along with electrode names like `AF3`, which are standard notation.
They are protocol identifiers, not prose.

Drone actions are translated for display through `i18n.drone_action()`. The
adapter names them in English CamelCase (`MoveForward`) because that is what the
config file and the Cortex layer speak; without that lookup the in-game banner
printed the raw identifier in every language.

### Head Tracking Controls
| Movement | Drone Action |
| :--- | :--- |
| **Tilt Forward** | Pitch Forward |
| **Tilt Backward** | Pitch Backward |
| **Tilt Side-to-Side** | Roll Left / Right |
| **Turn Head** | Yaw (Rotate) |

### Default Mental Mappings
- **Push**: Take Off
- **Pull**: Land
- **Drop**: Emergency Stop (Cuts motors instantly)
- **Lift**: Flip Forward

---

## 📁 Repository Structure

```text
├── .github/workflows/  # macOS + Windows build pipeline
├── bci_core/           # Signal processing and BCI logic
├── certificates/       # SSL certificates for Emotiv connection
├── packaging/          # PyInstaller spec
├── app_paths.py        # Resource and user-data paths (source vs. bundle)
├── config_manager.py   # Secure configuration handler
├── cortex.py           # Emotiv Cortex API wrapper
├── drone_adapter.py    # BCI to Tello command translator
├── drone_controller.py # Core background engine
├── i18n.py             # English / 中文 translation table
├── leaderboard.py      # Local high scores for the Ring Run
├── ui.py               # Graphical Dashboard
├── run.sh              # Entry point script
└── requirements.txt    # Project dependencies
```

---

## 📦 Desktop Builds

Prebuilt, **unsigned** installers for macOS (Apple Silicon) and Windows (x64)
are produced by GitHub Actions — no Python install needed to run them. One file
per platform: a `.dmg` for macOS, a `setup.exe` for Windows.

Windows is packaged as an installer rather than a bare `.exe` on purpose. The
PyInstaller build is *onedir* — the executable needs the `_internal` folder
beside it — and the alternative, a single-file build, unpacks PyQt6, OpenCV and
PyAV into `%TEMP%` on every launch, which costs 10–20 seconds of cold start. The
installer puts the folder down once and keeps startup at a couple of seconds.

**Getting one:** open the **Actions** tab → *Build desktop app* → pick a run →
download `EMOTIV-Drone-BCI-macos-arm64` or `EMOTIV-Drone-BCI-windows-x64`.
Pushing a `v*` tag also attaches both to a GitHub release.

**Opening them past the OS warning** (they carry no developer signature):

- **macOS** — mount the `.dmg`, drag the app to Applications, then right-click →
  **Open** → **Open**. Double-clicking gives a dead-end "cannot be opened" dialog.
  If Gatekeeper still refuses:
  ```bash
  xattr -dr com.apple.quarantine "/Applications/EMOTIV Drone BCI.app"
  ```
- **Windows** — run `EMOTIV-Drone-BCI-windows-x64-setup.exe`. On the SmartScreen
  prompt choose **More info** → **Run anyway**. It installs per user, so it does
  not ask for administrator rights, and it adds a Start Menu entry and an
  uninstaller.

EMOTIV Launcher must be running before you start the app, and it will ask you to
approve access on first launch. Settings are stored per user, not next to the
app: `~/Library/Application Support/EmotivDrone` on macOS,
`%APPDATA%\EmotivDrone` on Windows — including the Ring Run leaderboard.

### Building locally

```bash
pip install -r requirements.txt pyinstaller
pyinstaller packaging/EmotivDrone.spec --noconfirm
```

Output lands in `dist/`. To wrap the Windows build into its installer, with
[Inno Setup](https://jrsoftware.org/isinfo.php) on PATH:

```bash
iscc packaging/EmotivDrone.iss
```

That writes `EMOTIV-Drone-BCI-windows-x64-setup.exe` to the repository root.
Without `/DAppVersion=...` it is stamped `0.0.0`; CI passes the tag. A build only ever targets the OS it runs on — the
Windows bundle has to come from a Windows machine (or the CI runner).

---

## ⚠️ Safety Guidelines
1. **Always start in Simulation Mode** to verify your head tracking calibration.
2. Ensure you have plenty of open space (minimum 3m x 3m).
3. The **Emergency Stop** button in the UI is your primary safety mechanism.
4. If the application loses connection or is closed, the drone is programmed to land automatically.

---

*Developed with ❤️ for the BCI community.*
