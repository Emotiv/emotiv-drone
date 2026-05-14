import json
import os

CONFIG_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "config.json")

DEFAULT_CONFIG = {
    # Emotiv Cortex API
    "client_id": "YOUR_CLIENT_ID",
    "client_secret": "YOUR_CLIENT_SECRET",
    "device_id": "",
    "profile_name": "",

    # Drone Control Settings
    "simulate": False,
    "fix_indices": False,

    # Motion Processor Settings
    "sensitivity": 0.50,
    "deadzone": 0.02,
    "smoothing_window": 4,

    # Flight Settings
    "max_speed": 60,          # Max RC command value (0-100)
    "altitude_hold": True,    # Keep altitude stable when head is level
    "yaw_sensitivity": 0.5,   # Multiplier for yaw (rotation) control
    "throttle_sensitivity": 0.5,  # Multiplier for altitude control

    # Mental Command Mapping for Drone
    # Actions: None, TakeOff, Land, FlipForward, FlipBack, FlipLeft, FlipRight, EmergencyStop
    "mental_mappings": [
        {"command": "push", "action": "TakeOff", "threshold": 0.6, "auto_release": 0},
        {"command": "pull", "action": "Land", "threshold": 0.6, "auto_release": 0},
        {"command": "drop", "action": "EmergencyStop", "threshold": 0.5, "auto_release": 0},
        {"command": "lift", "action": "FlipForward", "threshold": 0.7, "auto_release": 0}
    ]
}

class ConfigManager:
    @staticmethod
    def load_config() -> dict:
        if not os.path.exists(CONFIG_FILE):
            ConfigManager.save_config(DEFAULT_CONFIG)
            return DEFAULT_CONFIG.copy()
        
        try:
            with open(CONFIG_FILE, 'r') as f:
                loaded = json.load(f)
                # Merge with defaults to ensure missing keys are populated
                config = DEFAULT_CONFIG.copy()
                config.update(loaded)
                return config
        except Exception as e:
            print(f"Error loading config: {e}. Using defaults.")
            return DEFAULT_CONFIG.copy()

    @staticmethod
    def save_config(config: dict):
        try:
            with open(CONFIG_FILE, 'w') as f:
                json.dump(config, f, indent=4)
        except Exception as e:
            print(f"Error saving config: {e}")
