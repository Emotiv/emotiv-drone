import json
import os

CONFIG_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "config.json")
CREDENTIALS_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "credentials.json")

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
        config = DEFAULT_CONFIG.copy()
        
        # Load main config
        if os.path.exists(CONFIG_FILE):
            try:
                with open(CONFIG_FILE, 'r') as f:
                    config.update(json.load(f))
            except Exception as e:
                print(f"Error loading config: {e}")
                
        # Load credentials
        if os.path.exists(CREDENTIALS_FILE):
            try:
                with open(CREDENTIALS_FILE, 'r') as f:
                    config.update(json.load(f))
            except Exception as e:
                print(f"Error loading credentials: {e}")
                
        # Ensure we always save files if they don't exist
        if not os.path.exists(CONFIG_FILE) or not os.path.exists(CREDENTIALS_FILE):
            ConfigManager.save_config(config)

        return config

    @staticmethod
    def save_config(config: dict):
        credentials_keys = ["client_id", "client_secret"]
        credentials_dict = {k: config[k] for k in credentials_keys if k in config}
        main_config_dict = {k: v for k, v in config.items() if k not in credentials_keys}
        
        try:
            with open(CONFIG_FILE, 'w') as f:
                json.dump(main_config_dict, f, indent=4)
            with open(CREDENTIALS_FILE, 'w') as f:
                json.dump(credentials_dict, f, indent=4)
        except Exception as e:
            print(f"Error saving config: {e}")
