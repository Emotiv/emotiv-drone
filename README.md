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

### Ring Run and the leaderboard

On the **Test Virtual Flight Controls** screen, type a name and press **Start
Run**. Rings spawn ahead of the drone for 60 seconds; each one is 10 points, and
the clock turns red for the last ten seconds. When time is up you get your score,
your position, and the top five, with **Try Again**, **Show Leaderboard**, or
**Finish — next player** (which returns to profile selection so the next person
can train their own profile).

Scores live in `leaderboard.json` beside the other settings — one table per
computer, no account and nothing uploaded. Leaving the test screen mid-run
abandons that run rather than recording it.

### Language
Pick **English** or **中文** from the dropdown in the top-right corner. The change
applies live, and the app reopens in the same language next time.

Two things stay in English on purpose: the raw Cortex/MOT/COM stream dumps in
the log pane, and telemetry channel abbreviations (`PWR`, `ALT`, `THR`, `YAW`)
on the HUD — they are protocol identifiers, not prose.

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

Prebuilt, **unsigned** bundles for macOS (Apple Silicon) and Windows (x64) are
produced by GitHub Actions — no Python install needed to run them.

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
- **Windows** — unzip anywhere, run `EMOTIV Drone BCI.exe`. On the SmartScreen
  prompt choose **More info** → **Run anyway**.

EMOTIV Launcher must be running before you start the app, and it will ask you to
approve access on first launch. Settings are stored per user, not next to the
app: `~/Library/Application Support/EmotivDrone` on macOS,
`%APPDATA%\EmotivDrone` on Windows — including the Ring Run leaderboard.

### Building locally

```bash
pip install -r requirements.txt pyinstaller
pyinstaller packaging/EmotivDrone.spec --noconfirm
```

Output lands in `dist/`. A build only ever targets the OS it runs on — the
Windows bundle has to come from a Windows machine (or the CI runner).

---

## ⚠️ Safety Guidelines
1. **Always start in Simulation Mode** to verify your head tracking calibration.
2. Ensure you have plenty of open space (minimum 3m x 3m).
3. The **Emergency Stop** button in the UI is your primary safety mechanism.
4. If the application loses connection or is closed, the drone is programmed to land automatically.

---

*Developed with ❤️ for the BCI community.*
