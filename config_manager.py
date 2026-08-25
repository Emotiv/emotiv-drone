import json
import os

from app_paths import user_data_dir

CONFIG_FILE = os.path.join(user_data_dir(), "config.json")
CREDENTIALS_FILE = os.path.join(user_data_dir(), "credentials.json")

DEFAULT_CONFIG = {
    # UI language: "en" or "zh"
    "language": "en",

    # Skip the credentials screen and connect on launch once a real Client ID
    # and Secret are stored. Turn off from the checkbox on that screen.
    "auto_connect": True,

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

    # Turning the head left should steer left. This stays False for every
    # headset except the ones that report yaw the other way round — MN8 sets it
    # in its device profile below. It used to be missing here and switched on
    # at the top level of config.json instead, which silently inverted every
    # other headset too.
    "invert_yaw": False,

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
    ],

    # Device Specific Overrides (e.g., {"MN8": {"invert_yaw": true, ...}})
    "device_profiles": {}
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

    @staticmethod
    def get_device_config(config: dict, device_type: str) -> dict:
        """Returns a copy of the config tailored for the specified device type."""
        device_profiles = config.get("device_profiles", {})
        device_config = config.copy()
        
        # If we have a profile for this device, apply it over the base config
        if device_type in device_profiles:
            device_config.update(device_profiles[device_type])
        else:
            # Create a default profile for this new device type
            profile = {}
            if device_type == "MN8":
                # MN8-specific default overrides
                profile["invert_yaw"] = True
                profile["sens_left"] = 30.0
                profile["sens_right"] = 30.0
                profile["sens_fwd"] = 25.0
                profile["sens_back"] = 25.0
            
            config.setdefault("device_profiles", {})[device_type] = profile
            device_config.update(profile)
            ConfigManager.save_config(config)
            
        return device_config

    @staticmethod
    def update_device_profile(config: dict, device_type: str, new_settings: dict) -> None:
        """Update the device profile with new settings and save to disk."""
        if not device_type:
            return
            
        profiles = config.setdefault("device_profiles", {})
        profile = profiles.setdefault(device_type, {})
        
        # We only want to save keys that are device-specific overrides
        # For simplicity, we just save motion/control keys
        overridable_keys = [
            "invert_yaw", "sens_left", "sens_right", "sens_fwd", "sens_back",
            "sensitivity", "deadzone", "smoothing_window", 
            "max_speed", "yaw_sensitivity", "throttle_sensitivity",
            "mental_mappings"
        ]
        
        for k in overridable_keys:
            if k in new_settings:
                profile[k] = new_settings[k]
                
        ConfigManager.save_config(config)
