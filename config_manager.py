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
    # Empty until the user enters their own and Cortex accepts them. These
    # used to be the literal strings YOUR_CLIENT_ID / YOUR_CLIENT_SECRET, which
    # looked like filled-in values to anything checking for emptiness.
    "client_id": "",
    "client_secret": "",
    "device_id": "",
    "profile_name": "",

    # Drone Control Settings
    "simulate": False,
    "fix_indices": False,

    # Motion Processor Settings
    "sensitivity": 0.50,
    "deadzone": 0.02,
    "smoothing_window": 4,

    # Head-tilt response per direction. Without these the app fell back to a
    # literal in _apply_config_to_client, so a fresh install flew differently
    # from a tuned checkout for no visible reason.
    "sens_left": 40.0,
    "sens_right": 40.0,
    "sens_fwd": 25.0,
    "sens_back": 25.0,

    # Tilting forward should fly forward. Per-model overrides live in
    # DEVICE_DEFAULTS alongside invert_yaw.
    "invert_pitch": False,

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

    # Mental Command Mapping
    # Actions: None, TakeOff, Land, FlipForward, FlipBack, FlipLeft, FlipRight,
    #          EmergencyStop, MoveForward/Back/Left/Right/Up/Down
    #
    # The trained command flies the drone forward. These used to default to the
    # real-drone set (push = TakeOff, pull = Land, and so on), which is wrong
    # for the simulator this app now is: on a machine with no config.json yet
    # — every fresh install — thinking "push" made the drone take off instead
    # of moving, and the in-scene hint could not name the command either,
    # because it looks for whichever one maps to MoveForward.
    #
    # Only push is bound. The player trains neutral and push; binding commands
    # nobody trained just invites accidental triggers.
    "mental_mappings": [
        {"command": "push", "action": "MoveForward", "threshold": 0.5, "auto_release": 0},
        {"command": "pull", "action": "None", "threshold": 0.5, "auto_release": 0},
        {"command": "drop", "action": "None", "threshold": 0.5, "auto_release": 0},
        {"command": "lift", "action": "None", "threshold": 0.5, "auto_release": 0}
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
                
        migrated = ConfigManager.migrate(config)

        # Ensure we always save files if they don't exist
        if (migrated or not os.path.exists(CONFIG_FILE)
                or not os.path.exists(CREDENTIALS_FILE)):
            ConfigManager.save_config(config)

        return config

    # Per-model motion defaults. Which way a headset reports yaw depends on how
    # it sits on the head, so this is a property of the hardware rather than of
    # anyone's installation. EPOC sits on a back strap and MN8 in the ears; both
    # report yaw opposite to Insight, which is the one the base config suits.
    DEVICE_DEFAULTS = {
        "MN8": {
            "invert_yaw": True,
            "sens_left": 30.0, "sens_right": 30.0,
            "sens_fwd": 25.0, "sens_back": 25.0,
        },
        "EPOC": {"invert_yaw": True},
        "EPOCX": {"invert_yaw": True},
        "EPOCPLUS": {"invert_yaw": True},
        "EPOCFLEX": {"invert_yaw": True},
    }

    # The mapping shipped before the app became a simulator. Anyone who ran an
    # earlier build still has it in their saved config, and a saved config wins
    # over DEFAULT_CONFIG — so fixing the default alone left every existing
    # install thinking "push" meant take off.
    LEGACY_MENTAL_MAPPINGS = [
        ("push", "TakeOff"), ("pull", "Land"),
        ("drop", "EmergencyStop"), ("lift", "FlipForward"),
    ]

    @staticmethod
    def _is_legacy_mapping(mappings) -> bool:
        """True only for the untouched old default, never a deliberate choice."""
        pairs = [(m.get("command"), m.get("action")) for m in (mappings or [])]
        return pairs == ConfigManager.LEGACY_MENTAL_MAPPINGS

    @staticmethod
    def migrate(config: dict) -> bool:
        """Bring a saved config forward. Returns True if anything changed.

        Deliberately conservative: only an exact match for the old default is
        replaced, so anyone who set their own mapping keeps it.
        """
        changed = False
        fresh = [dict(m) for m in DEFAULT_CONFIG["mental_mappings"]]

        # A device profile created before this table existed is an empty dict,
        # so it silently inherited the base — which is how an EPOC X ended up
        # steering backwards. Fill in only keys the profile does not already
        # set, so a value someone chose is never overwritten.
        for model, defaults in ConfigManager.DEVICE_DEFAULTS.items():
            profile = (config.get("device_profiles") or {}).get(model)
            if profile is None:
                continue
            for key, value in defaults.items():
                if key not in profile:
                    profile[key] = value
                    changed = True

        if ConfigManager._is_legacy_mapping(config.get("mental_mappings")):
            config["mental_mappings"] = [dict(m) for m in fresh]
            changed = True

        for profile in (config.get("device_profiles") or {}).values():
            if ConfigManager._is_legacy_mapping(profile.get("mental_mappings")):
                profile["mental_mappings"] = [dict(m) for m in fresh]
                changed = True

        # A top-level invert_yaw of True is the old global default, from before
        # inversion became a per-model property. It is a blunt instrument: it
        # flips every headset that has no profile of its own, which is how an
        # Insight ended up steering backwards after someone tuned an MN8. Every
        # model that genuinely needs inverting now says so in DEVICE_DEFAULTS,
        # so the base belongs at False.
        if config.get("invert_yaw") is True:
            config["invert_yaw"] = False
            changed = True
            print("[config] cleared the global yaw inversion; it is per-model now",
                  flush=True)

        if changed:
            print("[config] migrated saved settings forward", flush=True)
        return changed

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
            profile = dict(ConfigManager.DEVICE_DEFAULTS.get(device_type, {}))
            
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
