# Tello BCI Drone Controller

Control a DJI Tello drone with your mind and head movements using an Emotiv EEG headset.

## 🚀 Features

- **Head Tracking → Flight**: Tilt your head to fly the drone — pitch forward/back and roll left/right
- **Mental Commands**: Map trained mental commands to discrete actions (TakeOff, Land, Flip, Emergency Stop)
- **Live Camera Feed**: See the Tello's camera stream in real-time inside the dashboard
- **Telemetry**: Battery, altitude, temperature, and RC command values displayed live
- **Simulation Mode**: Test the full pipeline without a drone or headset
- **Dark Premium UI**: GitHub-inspired dark theme with smooth controls

## 🛠 Prerequisites

- **Python 3.8+**
- **DJI Tello** drone (connected to your computer's WiFi)
- **Emotiv Headset** (Insight, EPOC+, etc.) + Cortex App running
- **Emotiv Credentials** (Client ID and Client Secret)

## 📦 Installation

```bash
cd tello-controller
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

## 🎮 Usage

### Launch the Dashboard (Recommended)

```bash
python3 ui.py
```

From the dashboard you can:
1. Enter your Cortex credentials
2. Toggle Simulation Mode
3. Click **Connect Drone** to link to the Tello
4. Click **Take Off** to get airborne
5. Click **Start BCI** to begin head tracking control
6. Tilt your head to fly!

### Flight Controls

| Head Motion | Drone Action |
|---|---|
| Tilt forward (pitch down) | Fly forward |
| Tilt backward (pitch up) | Fly backward |
| Turn left (yaw left) | Move left |
| Turn right (yaw right) | Move right |

### Mental Commands (Configurable)

| Default Command | Default Action |
|---|---|
| Push | Take Off |
| Pull | Land |
| Drop | Emergency Stop |
| Lift | Flip Forward |

### Command Line (Without UI)

```bash
# With real drone and headset
python3 drone_controller.py

# Simulation mode
python3 drone_controller.py --simulate
```

## 📁 Project Structure

- `ui.py` — PyQt6 Dashboard with camera feed, telemetry, and configuration
- `drone_controller.py` — Core Emotiv → Tello bridge (Cortex client)
- `drone_adapter.py` — Translates head motion deltas into Tello RC commands
- `config_manager.py` — Persistent settings (config.json)
- `cortex.py` — Emotiv Cortex API WebSocket wrapper
- `neurogaming/` — Shared signal processing (QuaternionProcessor, MentalCommandProcessor)

## ⚠️ Safety

- The drone will **not move** until you explicitly Take Off and Start BCI
- **Emergency Stop** button cuts all motors immediately
- Drone lands automatically if the app is closed
- Start in **Simulation Mode** first to verify your head tracking feels right
