"""
Tello Drone Controller

Connects to the Emotiv Cortex API, processes head motion via QuaternionProcessor,
and sends RC commands to the Tello drone via DroneAdapter.

Mental commands are mapped to discrete drone actions (TakeOff, Land, etc.).
"""

import os
import sys
import time
import argparse
import threading

# Ensure local directory is used for imports
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from cortex import Cortex
from bci_core.program import ProgramSimulator
from drone_adapter import DroneAdapter


class TelloDroneClient:
    """Neurogaming client that bridges Emotiv → Tello drone."""

    def __init__(self, client_id: str, client_secret: str,
                 tello=None, fix_indices: bool = False,
                 debug: bool = False, config: dict = None,
                 bci_status_callback=None, bci_telemetry_callback=None,
                 profiles_callback=None, headsets_callback=None,
                 training_callback=None, dev_data_callback=None,
                 mc_config_callback=None):
        self.c = Cortex(client_id, client_secret, debug_mode=debug)
        
        self.bci_status_callback = bci_status_callback
        self.bci_telemetry_callback = bci_telemetry_callback
        self.profiles_callback = profiles_callback
        self.headsets_callback = headsets_callback
        self.training_callback = training_callback
        self.dev_data_callback = dev_data_callback
        self.mc_config_callback = mc_config_callback
        
        self.latest_raw_mot = ""
        self.latest_raw_com = ""
        self.q_indices = None
        
        config = config or {}
        mental_mappings = config.get("mental_mappings")
        self.program = ProgramSimulator(mental_mappings=mental_mappings)
        
        # Configure the drone adapter
        self.drone = DroneAdapter(
            tello=tello,
            max_speed=config.get("max_speed", 60),
            yaw_sensitivity=config.get("yaw_sensitivity", 0.5),
            throttle_sensitivity=config.get("throttle_sensitivity", 0.5),
            altitude_hold=config.get("altitude_hold", True)
        )
        
        mental_move_actions = {
            m.get("action") for m in (mental_mappings or [])
            if m.get("action", "").startswith("Move")
        }
        self.drone.set_mental_move_actions(mental_move_actions)
        
        self.fix_indices = fix_indices
        self.debug = debug
        self.running = True

        # Bind Cortex events
        self.c.bind(create_session_done=self.on_create_session_done)
        self.c.bind(new_mot_data=self.on_new_mot_data)
        self.c.bind(new_com_data=self.on_new_com_data)
        self.c.bind(new_data_labels=self.on_new_data_labels)
        self.c.bind(new_dev_data=self.on_new_dev_data)
        self.c.bind(inform_error=self.on_inform_error)
        self.c.bind(headset_connected=self.on_headset_connected)
        self.c.bind(headset_scanning_finished=self.on_headset_scanning_finished)
        self.c.bind(subscribe_done=self.on_subscribe_done)
        self.c.bind(access_right_pending=self.on_access_right_pending)
        self.c.bind(query_headset_done=self.on_query_headset_done)
        self.c.bind(query_profile_done=self.on_query_profile_done)
        self.c.bind(load_unload_profile_done=self.on_load_unload_profile_done)
        self.c.bind(new_sys_data=self.on_new_sys_data)
        
        # MC config bindings
        self.c.bind(get_mc_active_action_done=self.on_mc_active_action_done)
        self.c.bind(mc_training_threshold_done=self.on_mc_training_threshold_done)
        self.c.bind(mc_action_sensitivity_done=self.on_mc_action_sensitivity_done)

    def start(self, headset_id: str = '', profile_name: str = ''):
        if self.bci_status_callback:
            self.bci_status_callback("Connecting to Emotiv Cortex...")
        if headset_id:
            self.c.set_wanted_headset(headset_id)
        if profile_name:
            self.c.set_wanted_profile(profile_name)
        self.c.open()

    def reset_center(self):
        """Forces the quaternion processor to recalibrate on the next motion frame."""
        if hasattr(self, 'program') and self.program.quaternion_processor:
            self.program.quaternion_processor._is_calibrated = False
            msg = "Headset center reset requested"
            print(msg, flush=True)
            if self.bci_status_callback:
                # Give a quick temporary status update, then it will revert to active
                self.bci_status_callback(msg)

    def close(self):
        self.running = False
        self.drone.cleanup()
        if hasattr(self.c, 'auth') and self.c.auth and self.c.session_id:
            try:
                self.c.close_session()
            except Exception:
                pass
        time.sleep(1)
        self.c.close()

    # ──────────────────────────────────────────────
    # Cortex event handlers
    # ──────────────────────────────────────────────
    def on_create_session_done(self, *args, **kwargs):
        msg = "Session created. Subscribing to data streams..."
        print(msg, flush=True)
        if self.bci_status_callback:
            self.bci_status_callback("Session Created (waiting for streams...)")
        
        # Subscribe to device telemetry along with motion and mental
        self.c.sub_request(['mot', 'com', 'dev'])
        
        # Profile loading is now user-initiated via the UI dropdown.
        # We no longer auto-load here.
        
        # We track subscriptions to ensure both mot and com are active
        self._subscribed_streams = set()

    def on_subscribe_done(self, *args, **kwargs):
        streams = kwargs.get('data', [])
        for s in streams:
            self._subscribed_streams.add(s)
            
        if 'com' in self._subscribed_streams or 'mot' in self._subscribed_streams:
            if self.bci_status_callback:
                self.bci_status_callback("Session Active")

    def on_new_dev_data(self, *args, **kwargs):
        data = kwargs.get('data') or {}
        signal = data.get('signal', 0)
        battery = data.get('batteryPercent', 0)
        dev_cq = data.get('dev', [])
        if self.bci_telemetry_callback:
            self.bci_telemetry_callback(battery, signal)
        if self.dev_data_callback:
            self.dev_data_callback(signal, dev_cq)

    def on_headset_connected(self, *args, **kwargs):
        msg = "Headset connected (warning code 104)"
        print(msg, flush=True)
        if self.bci_status_callback:
            self.bci_status_callback(msg)

    def on_headset_scanning_finished(self, *args, **kwargs):
        msg = "Headset scanning finished (warning code 142)"
        print(msg, flush=True)
        if self.bci_status_callback:
            self.bci_status_callback(msg)

    def on_new_data_labels(self, *args, **kwargs):
        data = kwargs.get('data', {})
        stream_name = data.get('streamName')
        labels = data.get('labels')
        if stream_name in ['mot', 'com'] and labels:
            print(f"[{stream_name}] Labels: {labels}")
            if stream_name == 'mot':
                try:
                    self.q_indices = [labels.index('Q0'), labels.index('Q1'), labels.index('Q2'), labels.index('Q3')]
                    print(f"[mot] Found exact Quaternion indices: {self.q_indices}", flush=True)
                except ValueError:
                    self.q_indices = None

    def on_new_mot_data(self, *args, **kwargs):
        data = kwargs.get('data', {})
        mot = data.get('mot')
        if not mot: return
        
        self.latest_raw_mot = str(mot)
        timestamp = data.get('time', time.time())

        # Extract quaternion
        w = x = y = z = None
        found_idx = None

        if self.q_indices and len(mot) > max(self.q_indices):
            try:
                w, x, y, z = [float(mot[i]) for i in self.q_indices]
            except Exception:
                pass
        elif not self.fix_indices:
            if len(mot) >= 7:
                try:
                    w, x, y, z = float(mot[3]), float(mot[4]), float(mot[5]), float(mot[6])
                    found_idx = 3
                except Exception:
                    pass
        else:
            try:
                nums = [float(v) for v in mot]
                for i in range(0, max(0, len(nums) - 3)):
                    qslice = nums[i:i+4]
                    norm = (qslice[0]**2 + qslice[1]**2 + qslice[2]**2 + qslice[3]**2) ** 0.5
                    if abs(norm - 1.0) < 0.1:
                        w, x, y, z = qslice
                        found_idx = i
                        break
            except Exception:
                pass

        if w is None and self.fix_indices:
            if len(mot) >= 4:
                try:
                    w, x, y, z = float(mot[0]), float(mot[1]), float(mot[2]), float(mot[3])
                    found_idx = 0
                except Exception:
                    w = x = y = z = None

        if w is None:
            return

        motion = [timestamp, 0, 0, w, x, y, z]
        dx, dy = self.program.receive_motion(motion)

        if dx != 0 or dy != 0:
            self.drone.move_by(dx, dy)
        else:
            self.drone.stop_movement()

    def on_new_com_data(self, *args, **kwargs):
        data = kwargs.get('data', {})
        action = data.get('action')
        power = data.get('power', 0.0)
        if not action: return
        
        self.latest_raw_com = str(data)
        timestamp = data.get('time', time.time())

        mental = [timestamp, action, power]
        act, auto_release_time, should_execute = self.program.receive_mental(mental)
        if should_execute:
            print(f"Executing mental action: {act}", flush=True)
            self.drone.execute_action(act, auto_release_time)

    def on_inform_error(self, *args, **kwargs):
        error_data = kwargs.get('error_data')
        error_msg = f"Cortex error: {error_data}"
        print(error_msg, flush=True)
        if self.bci_status_callback:
            self.bci_status_callback(error_msg)

    def on_access_right_pending(self, *args, **kwargs):
        """Fired when requestAccess returns accessGranted=false.
        The user needs to open EMOTIV Launcher and approve the application.
        """
        msg = kwargs.get('message',
            'Access not granted. Please open EMOTIV Launcher and approve this application.')
        print(f"[access_right_pending] {msg}", flush=True)
        if self.bci_status_callback:
            self.bci_status_callback(f"PENDING_ACCESS:{msg}")

    def on_query_headset_done(self, *args, **kwargs):
        """Fired when queryHeadset returns the list of available headsets."""
        headsets = kwargs.get('data', [])
        print(f"[query_headset_done] {len(headsets)} headset(s) found", flush=True)
        if self.headsets_callback:
            self.headsets_callback(headsets)

    def connect_headset(self, headset_id: str):
        """Set the desired headset and initiate connection."""
        if not headset_id:
            return
        self.c.set_wanted_headset(headset_id)
        if self.bci_status_callback:
            self.bci_status_callback(f"Connecting to headset '{headset_id}'...")
        self.c.query_headset()

    def on_query_profile_done(self, *args, **kwargs):
        """Fired when queryProfile returns the list of available training profiles.
        Passes the list to the UI so the user can choose which profile to load.
        """
        profiles = kwargs.get('data', [])
        print(f"[query_profile_done] {len(profiles)} profile(s) found", flush=True)
        if self.profiles_callback:
            self.profiles_callback(profiles)

    def load_profile(self, profile_name: str):
        """Load a specific training profile by name (called from the UI)."""
        if not profile_name:
            return
        self.c.set_wanted_profile(profile_name)
        print(f"[load_profile] Loading profile: '{profile_name}'", flush=True)
        if self.bci_status_callback:
            self.bci_status_callback(f"Loading profile '{profile_name}'...")
        try:
            self.c.setup_profile(profile_name, 'load')
        except Exception as e:
            print(f"[load_profile] Error: {e}", flush=True)
            if self.bci_status_callback:
                self.bci_status_callback(f"Profile load error: {e}")

    def on_load_unload_profile_done(self, *args, **kwargs):
        """Fired when setupProfile 'load' completes successfully."""
        is_loaded = kwargs.get('isLoaded', False)
        if is_loaded:
            profile_name = getattr(self.c, 'profile_name', '')
            msg = f"Profile '{profile_name}' loaded. Ready for flight!"
            print(f"[profile] {msg}", flush=True)
            if self.bci_status_callback:
                self.bci_status_callback(f"PROFILE_LOADED:{msg}")
            if self.training_callback:
                self.training_callback(f"PROFILE_LOADED:{profile_name}")

    def on_new_sys_data(self, *args, **kwargs):
        """Handle sys stream data which emits training status."""
        sys_data = kwargs.get('data')
        if sys_data and len(sys_data) > 1:
            event_name = sys_data[1]
            print(f"[sys_data] event: {event_name}")
            if self.training_callback:
                self.training_callback(event_name)

    # ──────────────────────────────────────────────
    # MC Config Callbacks
    # ──────────────────────────────────────────────
    def on_mc_active_action_done(self, *args, **kwargs):
        data = kwargs.get('data')
        if self.mc_config_callback:
            self.mc_config_callback({'type': 'active_actions', 'data': data})

    def on_mc_training_threshold_done(self, *args, **kwargs):
        data = kwargs.get('data')
        if self.mc_config_callback:
            self.mc_config_callback({'type': 'training_threshold', 'data': data})

    def on_mc_action_sensitivity_done(self, *args, **kwargs):
        data = kwargs.get('data')
        if self.mc_config_callback:
            self.mc_config_callback({'type': 'action_sensitivity', 'data': data})

    def get_mc_config(self):
        """Request the current MC configuration from Cortex."""
        profile = getattr(self.c, 'profile_name', '')
        if profile:
            self.c.get_mental_command_active_action(profile)
            self.c.get_mental_command_training_threshold(profile)
            self.c.get_mental_command_action_sensitivity(profile)

    def set_mc_sensitivity(self, values: list):
        """Set the MC action sensitivity values."""
        profile = getattr(self.c, 'profile_name', '')
        if profile and values:
            self.c.set_mental_command_action_sensitivity(profile, values)

    # ──────────────────────────────────────────────
    # Training
    # ──────────────────────────────────────────────
    def create_and_train_profile(self, profile_name: str):
        """Create a new profile. The training process continues once it is loaded."""
        print(f"Requesting creation of profile: {profile_name}")
        self.c.profile_name = profile_name
        self.c.setup_profile(profile_name, 'create')

    def start_training(self, action: str):
        """Start training for a specific action (e.g. 'neutral', 'push')"""
        # Ensure sys stream is subscribed
        self.c.sub_request(['sys'])
        self.c.train_request('mentalCommand', action, 'start')

    def accept_training(self, action: str):
        """Accept the training data for the given action."""
        self.c.train_request('mentalCommand', action, 'accept')

    def reject_training(self, action: str):
        """Reject the training data for the given action."""
        self.c.train_request('mentalCommand', action, 'reject')

    def save_profile(self):
        """Save the profile after training is complete."""
        profile_name = getattr(self.c, 'profile_name', '')
        if profile_name:
            self.c.setup_profile(profile_name, 'save')

    # ──────────────────────────────────────────────
    # Simulation mode
    # ──────────────────────────────────────────────
    def simulate(self):
        """Simulate flow without Cortex or real drone."""
        print("Simulation start (no Cortex, no drone)")
        if self.bci_status_callback:
            self.bci_status_callback("Simulation Active")
        if self.bci_telemetry_callback:
            self.bci_telemetry_callback(100, 4) # 100% battery, 4 bars signal

        self.program.quaternion_processor.calibrate(1.0, 0.0, 0.0, 0.0)

        # Sample quaternion: slight pitch down → drone moves forward
        mot = [0.9962, 0.0872, 0.0, 0.0]  # ~10° pitch
        motion = [0, 1, 2, 3] + mot if not self.fix_indices else [0, 1, 2] + mot

        print("Simulating head motion → drone RC commands...")
        for i in range(20):
            if not self.running:
                break
            dx, dy = self.program.receive_motion(motion)
            lr, fb, ud, yaw = self.drone.get_rc_values()
            if dx != 0 or dy != 0:
                self.drone.move_by(dx, dy)
            print(f"  Iter {i}: dx={dx}, dy={dy} → RC(lr={lr}, fb={fb}, ud={ud}, yaw={yaw})")
            time.sleep(0.1)

        # Simulate mental command
        print("\nSimulating mental command: 'push' → TakeOff...")
        mental = [0, 'push', 0.8]
        act, auto_release_time, should = self.program.receive_mental(mental)
        print(f"  action={act}, should_execute={should}")
        if should:
            self.drone.execute_action(act, auto_release_time)

        print("\nSimulation complete.")
        while self.running:
            time.sleep(0.1)


from config_manager import ConfigManager

app_config = ConfigManager.load_config()


def main():
    p = argparse.ArgumentParser(description="Tello Drone Controller via Emotiv BCI")
    default_id = app_config.get("client_id") if app_config.get("client_id") else os.environ.get('CORTEX_CLIENT_ID', '')
    default_secret = app_config.get("client_secret") if app_config.get("client_secret") else os.environ.get('CORTEX_CLIENT_SECRET', '')

    p.add_argument('--client-id', default=default_id)
    p.add_argument('--client-secret', default=default_secret)
    p.add_argument('--fix-indices', action='store_true')
    p.add_argument('--simulate', action='store_true')
    p.add_argument('--debug', action='store_true')
    p.add_argument('--sensitivity', type=float, default=app_config.get("sensitivity"))
    p.add_argument('--deadzone', type=float, default=app_config.get("deadzone"))
    p.add_argument('--smoothing-window', type=int, default=app_config.get("smoothing_window"))

    args = p.parse_args()

    final_simulate = args.simulate or app_config.get("simulate", False)
    final_fix_indices = args.fix_indices or app_config.get("fix_indices", False)

    # Connect to real Tello or None for simulation
    tello = None
    if not final_simulate:
        try:
            from djitellopy import Tello
            tello = Tello()
            tello.connect()
            print(f"Battery: {tello.get_battery()}%")
        except Exception as e:
            print(f"Failed to connect to Tello: {e}")
            print("Run with --simulate to test without a drone.")
            return

    client_id = args.client_id if not final_simulate else 'SIM'
    client_secret = args.client_secret if not final_simulate else 'SIM'

    client = TelloDroneClient(
        client_id, client_secret,
        tello=tello,
        fix_indices=final_fix_indices,
        debug=args.debug,
        config=app_config
    )

    # Apply overrides
    qp = client.program.quaternion_processor
    if args.deadzone is not None:
        qp.movement_deadzone = args.deadzone
    if args.smoothing_window is not None:
        qp.SmoothingWindow = args.smoothing_window
        qp._movement_buffer = __import__('collections').deque(maxlen=args.smoothing_window)
    if args.sensitivity is not None:
        qp.current_sensitivity = args.sensitivity

    # Start in thread
    client_thread = threading.Thread(
        target=lambda: client.simulate() if final_simulate else client.start(
            headset_id=app_config.get("device_id", ""),
            profile_name=app_config.get("profile_name", "")
        )
    )
    client_thread.daemon = True
    client_thread.start()

    print("=== Tello Drone BCI Controller ===")
    print("Press Ctrl+C to exit")
    print("==================================")

    try:
        client_thread.join()
    except KeyboardInterrupt:
        print("\nShutting down...")
    finally:
        client.close()
        if tello:
            try:
                tello.end()
            except Exception:
                pass
        print("Application terminated.")


if __name__ == '__main__':
    main()
