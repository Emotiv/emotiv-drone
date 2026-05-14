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
- **Simulation Mode**: Test your BCI mapping and head tracking precision in a safe software-only environment before taking flight.

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
├── bci_core/           # Signal processing and BCI logic
├── certificates/       # SSL certificates for Emotiv connection
├── config_manager.py   # Secure configuration handler
├── cortex.py           # Emotiv Cortex API wrapper
├── drone_adapter.py    # BCI to Tello command translator
├── drone_controller.py # Core background engine
├── ui.py               # Graphical Dashboard
├── run.sh              # Entry point script
└── requirements.txt    # Project dependencies
```

---

## ⚠️ Safety Guidelines
1. **Always start in Simulation Mode** to verify your head tracking calibration.
2. Ensure you have plenty of open space (minimum 3m x 3m).
3. The **Emergency Stop** button in the UI is your primary safety mechanism.
4. If the application loses connection or is closed, the drone is programmed to land automatically.

---

*Developed with ❤️ for the BCI community.*
