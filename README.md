# EMOTIV Drone BCI

Fly with your mind. Train mental commands on an EMOTIV headset, steer by turning
your head, and fly a drone simulator through a timed ring run — no aircraft, no
propellers, nothing to crash.

![UI Dashboard](bg.png)

## 📥 Install and set up

For someone installing the app. If you are working on the code, the source
route is under [Installation & Setup](#-installation--setup-from-source).

### 1. What you need first

| | |
|---|---|
| **An EMOTIV headset** | Insight, EPOC, EPOC+ or EPOC X. |
| **An EMOTIV account** | Free, at [emotiv.com](https://www.emotiv.com/). The Launcher and your API credentials both hang off it. |
| **EMOTIV Launcher** | The desktop program that talks to the headset and runs the Cortex service this app connects to. Install it from your account and **sign in**. |
| **A computer** | Windows 10/11, or a Mac with Apple Silicon. There is no phone version — the Launcher is a desktop program. |

The Launcher has to be **running and signed in** whenever you fly. It connects
over `wss://localhost:6868`; no brain data leaves your machine.

### 2. Create your own API credentials

The app talks to Cortex as an *application*, and every person needs their own
application key. They are free and take a minute to make.

1. Sign in at [emotiv.com](https://www.emotiv.com/) and open
   **[My Account → Cortex Apps](https://www.emotiv.com/my-account/cortex-apps/)**.
2. Create a new application. Any name will do — it is only a label for your key.
3. Copy the **Client ID** and the **Client Secret**.

**The secret is shown once.** Copy it somewhere safe before closing the page; if
you lose it, make a new application rather than hunting for it.

The app asks for both on first launch and stores them in `credentials.json` in
your own user data directory, never in the installer.

### 3. Install the app

Download from the
[latest release](https://github.com/Emotiv/emotiv-drone/releases/latest):

| Platform | File |
|---|---|
| Windows 10/11 (x64) | `EMOTIV-Drone-BCI-windows-x64-setup.exe` |
| macOS 11+ (Apple Silicon) | `EMOTIV-Drone-BCI-macos-arm64.dmg` |

Intel Macs are not covered — the build is Apple Silicon only, and Rosetta does
not help with an arm64 binary.

Neither build is **code-signed**, so both operating systems object the first
time. Nothing is wrong with the download; there is no certificate on it yet.

**Windows.** Run the installer. It installs for your user only — no admin
rights, no UAC prompt — and adds a Start menu entry and an uninstaller.
SmartScreen shows *"Windows protected your PC"*: click **More info** → **Run
anyway**.

**macOS.** Open the `.dmg` and drag the app to **Applications** first. Do not
run it from the mounted image: that volume is read-only and flagged, so
Gatekeeper blocks it there and the flag cannot even be cleared.

macOS marks downloads with a quarantine flag, which for an unsigned app usually
appears as *"EMOTIV Drone BCI is damaged and can't be opened"*. It is not
damaged. Clear the flag once, in Terminal:

```bash
xattr -dr com.apple.quarantine "/Applications/EMOTIV Drone BCI.app"
```

Then open it normally. On macOS 15 and later the old right-click → *Open* trick
no longer works for unnotarised apps, which is why the command above is the one
to use.

macOS asks for **local network** permission on first run — allow it, or the app
cannot reach Cortex.

### 4. First run

1. Start **EMOTIV Launcher**, sign in, and put the headset on.
2. Open the app and paste your **Client ID** and **Client Secret** when it asks.
3. Pick your headset, then a **trained profile**. The profile must be trained on
   the *same headset model* you are using — an EPOC X profile will not load on
   an Insight.
4. Fly the **simulator**: hold your command, watch the stick values respond, and
   start a timed ring run when it feels right.

---

## 🚀 Key Features

- **Head Steering**: Turn your head left or right and the drone points where you
  are looking. Position control, not rate control — your head's angle *is* the
  drone's heading, so it holds steady when you do and returns to centre when you
  do. Head tilt is deliberately ignored; see
  [HOW_IT_WORKS.md](HOW_IT_WORKS.md) for why.
- **Mental Command Integration**: A trained thought flies the drone forward.
  `push` maps to **MoveForward** by default; the mapping and its activation
  threshold live in `config.json`.
- **Real-time Telemetry & Video**: The dashboard provides a live H.264 video feed from the drone and displays real-time battery status, altitude, temperature, and RC command logs.
- **Premium Dark Dashboard**: A custom-built PyQt6 interface designed for professional BCI experimentation.
- **60-second Ring Run**: A timed score attack in the simulator — collect glowing rings against the clock, then see where you landed on a local leaderboard. Built for passing one headset around a room: finish a run, hand over, next person trains and plays.
- **English and 中文**: Switch language from the header at any time — the whole interface follows immediately, no restart. Your choice is remembered in `config.json`.
- **Simulation Mode**: Test your BCI mapping and head tracking precision in a safe software-only environment before taking flight.

## 📡 What flies the drone

Nothing leaves your computer. The headset's data becomes four stick values —
left/right, forward/back, up/down and yaw — exactly the four a real transmitter
sends, refreshed twenty times a second, and the simulator flies them.

1.  **Head motion → aim.** Quaternions from the headset become a heading, with
    the centre measured at the start of every run so drift is cancelled rather
    than flown.
2.  **Mental commands → actions.** A trained command becomes take off, land or a
    movement, once it passes its threshold.
3.  **Sticks → flight.** `DroneAdapter` holds the four values; the simulator
    reads them each frame. Keeping that boundary means the flight model can
    change without touching anything about the brain side.

---

## 🏗 Project Architecture

The system is built on a modular architecture to ensure low latency and reliable data processing:

### 1. The Core Bridge (`drone_controller.py`)
`BCIDroneClient`, the main engine between the Emotiv Cortex API and the flight
model. It handles the WebSocket lifecycle, authentication, and data stream
subscriptions.

### 2. Signal Processing (`bci_core/`)
- **QuaternionProcessor**: Converts raw spatial data from the headset into normalized Euler angles for flight control.
- **MentalCommandProcessor**: Filters and thresholds mental command data to prevent accidental triggers.

### 3. Drone Adaptation (`drone_adapter.py`)
Translates processed BCI signals into the four stick values, with deadzones,
sensitivity scaling and smoothing so flight stays fluid.

### 4. Dashboard (`ui.py`)
A PyQt6-based graphical interface that provides:
- The flight simulator and its ring run.
- Telemetry visualization.
- Interactive configuration of sensitivity and mental command thresholds.

> **Working on the code?** [HOW_IT_WORKS.md](HOW_IT_WORKS.md) is the developer
> guide: the full pipeline from Cortex stream to drone, the steering maths and
> why the control model is what it is, the diagnostics to read when it
> misbehaves, and the configuration and build details.

### 5. Diagnostics (`applog.py`, `pipeline_log.py`, `motion_capture.py`)
Three layers, because these failures usually happen on someone else's machine:
a file log that survives the window closing, a `[pipe]` heartbeat every five
seconds carrying every stage of the pipeline at once, and a full-rate CSV of the
first minute of head motion for anything a one-second log is too coarse to
answer.

---

## 🔒 Security & Configuration

We've implemented a split-configuration system to keep your development environment secure:

- **`config.json`**: Steering feel, mental command mappings and thresholds, and
  per-model overrides.
- **`credentials.json`**: Your Emotiv Client ID and Secret. Git-ignored. The app
  ships with none and asks on first launch.
- **`config_manager.py`**: Merges `DEFAULT_CONFIG` with what is on disk, runs
  `migrate()`, and splits the two files on save.

**Both live beside the source in a checkout, and in the per-user data directory
in an installed build** (`%APPDATA%\EmotivDrone` on Windows). The copy in the
repository is therefore *not* what a built application reads — settings do not
travel with the installer. Anything that should be everyone's default belongs in
`DEFAULT_CONFIG`, with a migration for machines that already have the old value
written to disk.

---

## 🛠 Prerequisites

- **Hardware**: 
  - Emotiv Headset (Insight, EPOC, EPOC+, or EPOC X).
- **Software**:
  - Emotiv Cortex App (running and logged in).
  - Python 3.8 or higher.

---

## 📦 Installation & Setup (from source)

1. **Clone the repository**:
   ```bash
   git clone https://github.com/Emotiv/emotiv-drone.git
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

The app flies a simulator and nothing else. The code that connected to an
aircraft over WiFi — its video stream, the flight dashboard and the drone SDK —
was removed, along with the OpenCV and PyAV dependencies it needed. Git history
has it if it is ever wanted back.

The flow a player walks is: **pick a headset → check the sensors → train → fly**.
Three flags at the top of `ui.py` keep it that short, and each can be flipped
back on without touching anything else:

| Flag | Off means |
| :--- | :--- |
| `SHOW_MOTION_TUNING` | No ⚙ Configurations button, which is where the motion tuning now lives. **🎯 Recenter** is the one motion control on the page. Values still come from `config.json`. |
| `SHOW_PROFILE_LIST` | No list of past profiles; each player types their own name. |

One more, and it is a stopgap rather than a preference:

| Flag | On means |
| :--- | :--- |
| `COINS_STRAIGHT_AHEAD` | Rings spawn dead ahead of the drone rather than off to one side, so a run can be flown on forward motion alone. It dates from a period when steering did not work; steering works now, and setting it `False` restores the real game. |

The credentials screen is not a flag. The app ships with no credentials, asks
once on first launch, saves them after EMOTIV Launcher approves, and never asks
again — after that the same screen is only reached on a connection failure.

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

### The controls, in full

| Input | Effect |
| :--- | :--- |
| **Turn your head left / right** | The drone points where you are looking, and holds there. |
| **Your trained command** (`push`) | The drone flies forward while you hold the thought. |
| **Tilt your head** | Nothing, on purpose. |

Head steering is absolute: 10° of head is 3.4° of heading, 30° is 21°, and
letting your head come back to centre brings the drone back with it. The curve
is set by `head_gain` and `head_expo` — see
[HOW_IT_WORKS.md](HOW_IT_WORKS.md#3-steering-the-heads-angle-is-the-heading).

### Default mental mappings

| Command | Action |
| :--- | :--- |
| `push` | `MoveForward` |
| `pull`, `lift`, `drop` | `None` |

Take-off, landing and emergency stop are real actions in `drone_adapter.py` and
map fine, but nothing uses them: there is no drone to take off. A run is one
trained command and your head.

---

## 📁 Repository Structure

```text
├── .github/workflows/  # CI build pipeline (Windows installers are built locally now)
├── assets/             # Optional branding artwork and headset product shots
├── bci_core/           # Signal processing — see bci_core/README.md
│   ├── processor.py    #   QuaternionProcessor: head angle -> drone heading
│   ├── mental.py       #   MentalCommandProcessor: threshold lookup
│   └── program.py      #   ProgramSimulator: thin adapter over both
├── certificates/       # rootCA.pem for the Cortex TLS connection
├── packaging/          # PyInstaller spec, Inno Setup script, icon builder
├── app_paths.py        # Resource and user-data paths (source vs. bundle)
├── applog.py           # File log with rollover, and the excepthook into it
├── config_manager.py   # DEFAULT_CONFIG, DEVICE_DEFAULTS, migrate()
├── cortex.py           # Emotiv Cortex JSON-RPC client and event dispatcher
├── drone_adapter.py    # Mental commands -> RC velocities (head motion no longer)
├── drone_controller.py # BCIDroneClient: binds Cortex events to everything else
├── i18n.py             # English / 中文 translation table
├── leaderboard.py      # Local high scores for the Ring Run
├── motion_capture.py   # Full-rate motion CSV for diagnosing drift
├── pipeline_log.py     # Stream rates and stall detection behind [pipe]
├── ui.py               # PyQt6 dashboard and the drone simulator
├── run.sh              # Entry point script
└── requirements.txt    # Project dependencies
```

---

## 📦 Desktop Builds

Download links, the credentials walkthrough and the Gatekeeper and SmartScreen
steps are up in [Install and set up](#-install-and-set-up). This section is
about where those files come from.

Both installers are built by
[`.github/workflows/build.yml`](.github/workflows/build.yml) on `macos-14` and
`windows-latest`, and attached to a GitHub release:

| Platform | File |
|---|---|
| macOS 11+ (Apple Silicon) | `EMOTIV-Drone-BCI-macos-arm64.dmg` |
| Windows 10/11 (x64) | `EMOTIV-Drone-BCI-windows-x64-setup.exe` |

To cut a release:

```bash
git tag v1.0.2
git push origin v1.0.2
```

The tag builds both platforms, creates the release and attaches both files. The
tag minus its leading `v` is the version stamped into the Windows installer.
Running the workflow from the **Actions** tab builds identically, versions it
`0.0.0` and leaves the results as workflow artifacts instead of publishing.

Windows is packaged as an installer rather than a bare `.exe` on purpose. The
PyInstaller build is *onedir* — the executable needs the `_internal` folder
beside it — and the alternative, a single-file build, unpacks PyQt6, OpenCV and
PyAV into `%TEMP%` on every launch, which costs 10–20 seconds of cold start. The
installer puts the folder down once and keeps startup at a couple of seconds.

EMOTIV Launcher must be running before you start the app, and it will ask you to
approve access on first launch. Settings are stored per user, not next to the
app: `~/Library/Application Support/EmotivDrone` on macOS, `%APPDATA%\EmotivDrone`
on Windows — including the Ring Run leaderboard.

The icons are generated rather than committed: `packaging/make_icon.py` builds
the Windows `.ico` and the macOS `.icns` from `assets/logo_white.png`, and the
workflow runs it before PyInstaller, so changing the logo brings every icon with
it.

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
Without `/DAppVersion=...` it is stamped `0.0.0`. A build only ever targets the
OS it runs on, so the Windows bundle has to come from a Windows machine.

Two things worth knowing before handing a build to someone:

- **Settings do not travel with it.** `config.json` and `credentials.json` live
  in the user data directory, not in the installer, so a machine you have tuned
  and a fresh install behave differently unless the value is in `DEFAULT_CONFIG`.
- **A fresh timestamp is not proof the build contains your change.** Read the
  symbols back out of the shipped executable with
  `PyInstaller.archive.readers` if it matters.

---

## ⚠️ A note on what this is

Everything here flies a simulator. There is no aircraft, no propeller and
nothing to damage — which is exactly why it is a good place to find out how
reliable your mental commands really are.

Take the headset off between players, and give each person their own profile:
a signature trained on someone else's head is the most common reason a command
"stops working".
