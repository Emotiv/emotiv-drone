"""
Tello Drone Controller

Connects to the Emotiv Cortex API, processes head motion via QuaternionProcessor,
and sends RC commands to the Tello drone via DroneAdapter.

Mental commands are mapped to discrete drone actions (TakeOff, Land, etc.).
"""

import os
import sys
import time
import math
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
                 mc_config_callback=None, brainmap_callback=None,
                 profile_admin_callback=None, dev_labels_callback=None):
        self.c = Cortex(client_id, client_secret, debug_mode=debug)

        self.bci_status_callback = bci_status_callback
        self.bci_telemetry_callback = bci_telemetry_callback
        self.profiles_callback = profiles_callback
        self.headsets_callback = headsets_callback
        self.training_callback = training_callback
        self.dev_data_callback = dev_data_callback
        self.mc_config_callback = mc_config_callback
        self.brainmap_callback = brainmap_callback
        self.profile_admin_callback = profile_admin_callback
        self.dev_labels_callback = dev_labels_callback
        # Electrode names for the contact-quality stream, e.g.
        # ['AF3','T7','Pz','T8','AF4']. Cortex reports them per headset, so the
        # head map can only be drawn once this has arrived.
        self.dev_labels = []
        # Filled in by mentalCommandActiveAction; a reset needs to know which
        # actions actually carry training data.
        self.last_active_actions = []

        self.latest_raw_mot = ""
        self.latest_raw_com = ""
        self.q_indices = None

        # Bookkeeping for the once-a-second steering report; see _log_steering.
        self._steer_last_log = 0.0
        self._steer_peak = 0.0
        self._steer_peak_debug = None
        self._steer_moved = False
        self._steer_quiet = False
        self._steer_was_calibrated = False
        # Same, for mental commands that land under their threshold.
        self._mental_last_log = 0.0
        self._mental_peak = 0.0
        
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
        self.c.bind(access_right_rejected=self.on_access_right_rejected)
        self.c.bind(connection_failed=self.on_connection_failed)
        self.c.bind(headset_not_found=self.on_headset_not_found)
        self.c.bind(headset_disconnected=self.on_headset_disconnected)
        self.c.bind(authorize_done=self.on_authorize_done)
        self.c.bind(query_headset_done=self.on_query_headset_done)
        self.c.bind(query_profile_done=self.on_query_profile_done)
        self.c.bind(load_unload_profile_done=self.on_load_unload_profile_done)
        self.c.bind(new_sys_data=self.on_new_sys_data)
        
        # MC config bindings
        self.c.bind(get_mc_active_action_done=self.on_mc_active_action_done)
        self.c.bind(mc_training_threshold_done=self.on_mc_training_threshold_done)
        self.c.bind(mc_action_sensitivity_done=self.on_mc_action_sensitivity_done)
        self.c.bind(mc_brainmap_done=self.on_mc_brainmap_done)
        self.c.bind(delete_profile_done=self.on_delete_profile_done)

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
            # Clear any partial batch as well as the flag, or Recenter averages
            # the new frames together with stale ones from the last attempt.
            self.program.quaternion_processor._calibration_samples.clear()
            self.program.quaternion_processor._is_calibrated = False
            msg = "Headset center reset requested"
            print(msg, flush=True)
            if self.bci_status_callback:
                # Give a quick temporary status update, then it will revert to active
                self.bci_status_callback(msg)

    CALLBACK_ATTRS = (
        'bci_status_callback', 'bci_telemetry_callback', 'profiles_callback',
        'headsets_callback', 'training_callback', 'dev_data_callback',
        'mc_config_callback', 'brainmap_callback', 'profile_admin_callback',
        'dev_labels_callback',
    )

    def detach_callbacks(self):
        """Stop this client from talking to the UI.

        A replaced client keeps its websocket thread alive for a moment, and
        its on_close still fires. Without this, the corpse of a failed
        connection attempt reports "connection failed" over the top of the
        attempt that replaced it — which is what put the credentials screen
        back up in the middle of a successful retry.
        """
        for attr in self.CALLBACK_ATTRS:
            setattr(self, attr, None)

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
        # Cortex reports signal strength as a float (1.0). The Qt signals these
        # values travel on are declared int, and handing PyQt a float there does
        # not round — it produced garbage like -998818480, which read as
        # "Unknown" on the signal check and disabled the Start Training button.
        def _as_int(value, default=0):
            try:
                return int(round(float(value)))
            except (TypeError, ValueError):
                return default

        signal = _as_int(data.get('signal', 0))
        battery = _as_int(data.get('batteryPercent', 0))
        dev_cq = [_as_int(v) for v in (data.get('dev', []) or [])]
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
        if stream_name == 'dev' and labels:
            # The contact-quality columns arrive named; without them the EQ
            # screen can only fall back to S0..Sn and cannot place anything on
            # a scalp map.
            self.dev_labels = list(labels)
            print(f"[dev] Sensor labels: {self.dev_labels}", flush=True)
            if self.dev_labels_callback:
                self.dev_labels_callback(list(self.dev_labels))

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
        self._log_steering(dx)

        if dx != 0 or dy != 0:
            self.drone.move_by(dx, dy)
        else:
            self.drone.stop_movement()

    # Motion frames arrive at 32-64 Hz. One line per frame would bury the log
    # and the on-screen terminal, so the report is a once-a-second summary that
    # carries the peak of the interval rather than whichever frame happened to
    # land on the tick.
    STEER_LOG_INTERVAL = 1.0

    def _log_steering(self, dx: int):
        """Report how a turn of the head became (or failed to become) a turn.

        Steering runs measured yaw through a deadzone, a sensitivity multiplier
        and finally int(), and when it does not work the interesting question
        is which of those swallowed it. Reading them off a live headset is the
        only way to tell, hence the log rather than more guessing.
        """
        qp = self.program.quaternion_processor

        # Calibration first: until it finishes every frame legitimately yields
        # zero, and mistaking that for broken steering wastes the whole hunt.
        calibrated = qp.is_calibrated
        if calibrated != self._steer_was_calibrated:
            self._steer_was_calibrated = calibrated
            print("[steer] calibrated, centre captured" if calibrated
                  else "[steer] calibrating, hold still", flush=True)
            print(f"[steer] config gain={qp.head_gain:.1f} "
                  f"expo={qp.head_expo:.2f} "
                  f"deadzone={qp.head_deadzone_deg:.1f}deg "
                  f"limit={qp.head_limit_deg:.0f}deg "
                  f"invert_yaw={qp.invert_yaw} "
                  f"smoothing={qp.SmoothingWindow}", flush=True)
            self._steer_peak = 0.0
            self._steer_peak_debug = None
            self._steer_last_log = time.time()
            return
        if not calibrated:
            return

        debug = qp.last_yaw_debug
        if not debug:
            return

        measured = math.radians(qp.head_yaw_deg)
        debug = dict(debug, head_deg=qp.head_yaw_deg,
                     heading_deg=qp.head_heading_deg)
        if abs(measured) > abs(self._steer_peak):
            # Keep the whole frame, not just its yaw. Reporting the interval's
            # peak alongside the *latest* frame's arithmetic mixed two
            # different moments, and during a fast head turn the two disagreed
            # on both sign and magnitude -- lines claiming a 14deg turn was
            # eaten by a 4deg deadzone were reading the peak from one frame and
            # the deadzone result from another.
            self._steer_peak = measured
            self._steer_peak_debug = dict(debug)
        if abs(qp.head_heading_deg) > 0.0:
            self._steer_moved = True

        now = time.time()
        if now - self._steer_last_log < self.STEER_LOG_INTERVAL:
            return
        self._steer_last_log = now

        # A dead-still head every second forever is noise. Report only once,
        # then stay quiet until something actually happens.
        interesting = self._steer_moved or abs(self._steer_peak) >= 0.01
        if not interesting:
            if self._steer_quiet:
                self._steer_peak = 0.0
                self._steer_moved = False
                return
            self._steer_quiet = True
        else:
            self._steer_quiet = False

        peak = self._steer_peak_debug or debug
        side = "right" if peak["head_deg"] > 0 else "left"
        gate = "deadzone" if peak["heading_deg"] == 0.0 else "none"
        print(
            f"[steer] head {peak['head_deg']:+.1f}deg {side} "
            f"- deadzone {qp.head_deadzone_deg:.1f} x gain {qp.head_gain:.1f} "
            f"-> heading {peak['heading_deg']:+.1f}deg lost_to={gate}",
            flush=True)

        self._steer_peak = 0.0
        self._steer_peak_debug = None
        self._steer_moved = False

    def on_new_com_data(self, *args, **kwargs):
        data = kwargs.get('data', {})
        action = data.get('action')
        power = data.get('power', 0.0)
        if not action: return
        
        self.latest_raw_com = str(data)
        timestamp = data.get('time', time.time())

        mental = [timestamp, action, power]
        act, auto_release_time, should_execute = self.program.receive_mental(mental)
        self._log_mental(action, power, act, should_execute)
        if should_execute:
            print(f"Executing mental action: {act}", flush=True)
            self.drone.execute_action(act, auto_release_time)

    def _log_mental(self, command: str, power: float, action: str, fired: bool):
        """Report the mental command that did not quite make it.

        A command that fires already announces itself. The interesting case is
        the one that does not: Cortex is classifying the thought but the power
        sits under the mapping's threshold, which from the player's seat is
        indistinguishable from the headset ignoring them. Without the number
        there is no way to tell a weakly trained profile from a broken one.

        Throttled and peak-carrying for the same reason as _log_steering: the
        com stream is far too fast to print per event.
        """
        if fired:
            self._mental_peak = 0.0
            return

        threshold = self.program.mental_processor.mappings
        threshold = next((m.get("threshold", 0.5) for m in threshold
                          if m.get("command", "").lower() == command.lower()), None)
        # 'neutral' has no mapping and is not a command anyone is trying to
        # make; reporting it every second would drown the ones that matter.
        if threshold is None or command.lower() == "neutral":
            return

        if power > self._mental_peak:
            self._mental_peak = power

        now = time.time()
        if now - self._mental_last_log < self.STEER_LOG_INTERVAL:
            return
        self._mental_last_log = now

        if self._mental_peak > 0.0:
            print(f"[mental] '{command}' peaked at {self._mental_peak:.2f}, "
                  f"needs {threshold:.2f} -> not fired", flush=True)
        self._mental_peak = 0.0

    # Cortex codes that mean "these credentials will never work", as opposed to
    # something transient. -32001/-32002 cover an unknown or wrong client id or
    # secret; -32004 is an app that is not authorised for this user.
    CREDENTIAL_ERRORS = {-32001, -32002, -32004, -32012}

    # A profile another application loaded on the headset. -32127 is "a profile
    # is already loaded, unload it first"; -32046 is "this profile was loaded by
    # another application". Neither is something this app can resolve on its own.
    PROFILE_LOCKED_ERRORS = {-32046, -32127}

    def on_inform_error(self, *args, **kwargs):
        error_data = kwargs.get('error_data') or {}
        error_msg = f"Cortex error: {error_data}"
        print(error_msg, flush=True)
        if not self.bci_status_callback:
            return

        code = error_data.get('code') if isinstance(error_data, dict) else None
        message = (error_data.get('message') if isinstance(error_data, dict)
                   else str(error_data))
        # Before authorize has ever succeeded, any error is a failure to get
        # started, and the credentials screen is where the user can act on it.
        if code in self.CREDENTIAL_ERRORS or not getattr(self.c, 'authorized', False):
            self.bci_status_callback(f"AUTH_FAILED:{message or error_data}")
        elif code in self.PROFILE_LOCKED_ERRORS:
            # The app clears the headset before training, so reaching here
            # means Cortex would not let go of the profile. Only EMOTIV
            # Launcher can release it, and the raw message does not say so.
            self.bci_status_callback(
                "Another application is holding a training profile on this "
                "headset. Close the profile in EMOTIV Launcher, then try again.")
        else:
            self.bci_status_callback(error_msg)

    def on_authorize_done(self, *args, **kwargs):
        """Credentials accepted and the app approved in EMOTIV Launcher."""
        print("[auth] credentials accepted", flush=True)
        if self.bci_status_callback:
            self.bci_status_callback("AUTHORIZED:")

    def on_headset_disconnected(self, *args, **kwargs):
        """The headset dropped out while we were using it."""
        headset = kwargs.get('headset', '')
        print(f"[headset] lost '{headset}'", flush=True)
        if self.bci_status_callback:
            self.bci_status_callback(f"HEADSET_LOST:{headset}")

    def reconnect_headset(self, headset_id: str):
        """One attempt at getting a dropped headset back.

        Deliberately not a fresh session: reconnecting the device is enough for
        Cortex to resume the streams the existing session is subscribed to, and
        tearing the session down would lose the loaded profile with it.
        """
        try:
            self.c.set_wanted_headset(headset_id)
            self.c.query_headset()
            return True
        except Exception as e:
            print(f"[headset] reconnect attempt failed: {e}", flush=True)
            return False

    def on_headset_not_found(self, *args, **kwargs):
        """The headset we were asked to connect to is no longer in the list."""
        headset = kwargs.get('headset', '')
        print(f"[headset] '{headset}' is no longer available", flush=True)
        # Forget it, or every later queryHeadset re-runs this same dead end.
        self.c.set_wanted_headset('')
        if self.headsets_callback:
            self.headsets_callback(kwargs.get('data') or [])
        if self.bci_status_callback:
            self.bci_status_callback(f"HEADSET_NOT_FOUND:{headset}")

    def on_connection_failed(self, *args, **kwargs):
        """Cortex could not be reached, or dropped before authorizing.

        Reported through the status channel with a prefix the UI switches on,
        the same way PENDING_ACCESS: is handled. Until this existed the app sat
        on "Connecting..." indefinitely when EMOTIV Launcher was not running.
        """
        reason = kwargs.get('reason', 'unreachable')
        detail = kwargs.get('detail', '')
        print(f"[connection_failed] {reason}: {detail}", flush=True)
        if self.bci_status_callback:
            self.bci_status_callback(f"CONNECTION_FAILED:{detail}")

    def on_access_right_rejected(self, *args, **kwargs):
        """The user declined this application in EMOTIV Launcher."""
        msg = kwargs.get('message', '')
        print(f"[access_right_rejected] {msg}", flush=True)
        if self.bci_status_callback:
            self.bci_status_callback("ACCESS_REJECTED:")

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
        print(f"[load_profile] Loading profile: '{profile_name}'", flush=True)
        if self.bci_status_callback:
            self.bci_status_callback(f"Loading profile '{profile_name}'...")
        try:
            # Via prepare_profile so anything the Launcher or a previous run
            # left loaded on the headset is cleared first.
            self.c.prepare_profile(profile_name, 'load')
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
        if isinstance(data, list):
            self.last_active_actions = data
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

    def on_mc_brainmap_done(self, *args, **kwargs):
        """mentalCommandBrainMap result: one (x, y) per trained action.

        The further apart the points are, the less often Cortex confuses those
        actions with each other — that is the whole reason to show it after
        training instead of just saying "done".
        """
        data = kwargs.get('data') or []
        if self.brainmap_callback:
            self.brainmap_callback(data)

    def on_delete_profile_done(self, *args, **kwargs):
        name = kwargs.get('name', '')
        print(f"[profile] deleted '{name}'", flush=True)
        if self.profile_admin_callback:
            self.profile_admin_callback({'type': 'deleted', 'profile': name})
        # The list the UI is showing still contains it.
        self.c.query_profile()

    def delete_profile(self, profile_name: str):
        """Delete a profile outright.

        Cortex will not touch a profile that is currently loaded on the headset,
        so unload first — same constraint emotiv-brain-light hits when switching
        profiles. The unload reply is asynchronous, hence the short wait rather
        than firing both in the same tick.
        """
        if not profile_name:
            return
        try:
            self.c.setup_profile(profile_name, 'unload')
        except Exception as e:
            print(f"[profile] unload before delete failed (continuing): {e}", flush=True)
        time.sleep(0.6)
        self.c.setup_profile(profile_name, 'delete')

    def reset_profile_training(self, profile_name: str = ""):
        """Erase the trained data but keep the profile.

        Cortex has no single "reset profile" call — training data is erased one
        action at a time, so this walks the profile's active actions. Neutral is
        included: a stale neutral baseline is exactly what makes a retrained
        profile behave worse than a fresh one.
        """
        actions = list(self.last_active_actions) or ['neutral', 'push']
        for action in actions:
            try:
                self.c.train_request('mentalCommand', action, 'erase')
                time.sleep(0.35)
            except Exception as e:
                print(f"[profile] could not erase '{action}': {e}", flush=True)
        name = profile_name or getattr(self.c, 'profile_name', '')
        if name:
            self.c.setup_profile(name, 'save')
        if self.profile_admin_callback:
            self.profile_admin_callback({'type': 'reset', 'profile': name})

    def finish_session(self, profile_name: str = ''):
        """End a player's turn: bin their profile, then hand the headset back.

        The order is the point. setupProfile is addressed to a headset, so
        disconnecting first leaves the profile behind on the account — and these
        used to run as two independent threads, which meant the delete and the
        disconnect raced every time.
        """
        if profile_name:
            self.delete_profile(profile_name)
            time.sleep(0.6)
        self.release_headset()

    def release_headset(self, rescan: bool = True):
        """Hand the headset back so the next player can pick it fresh.

        Finishing a session used to leave the headset connected and the Cortex
        session open, so the device list the next person landed on still showed
        a headset that was in use by the previous run. Close the session, drop
        the Bluetooth/USB link, then rescan so the list is rebuilt from what is
        actually available.
        """
        try:
            if getattr(self.c, 'session_id', ''):
                self.c.close_session()
                time.sleep(0.6)
        except Exception as e:
            print(f"[headset] close session failed: {e}", flush=True)

        try:
            self.c.disconnect_headset()
            time.sleep(1.0)
        except Exception as e:
            print(f"[headset] disconnect failed: {e}", flush=True)

        # A disconnected headset leaves no live streams behind it.
        self.dev_labels = []
        if rescan:
            self.refresh_headsets()

    def refresh_headsets(self):
        """Re-scan for headsets, then ask for the list again.

        controlDevice/refresh makes Cortex rescan Bluetooth/USB; it does not
        return the list, so queryHeadset still has to follow it.
        """
        try:
            self.c.refresh_headset_list()
        except Exception as e:
            print(f"[headset] refresh failed: {e}", flush=True)
        time.sleep(1.2)
        self.c.query_headset()

    def get_brain_map(self):
        """Ask Cortex how well separated the trained actions ended up."""
        profile = getattr(self.c, 'profile_name', '')
        if profile:
            self.c.get_mental_command_brain_map(profile)

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
        """Create a new profile. The training process continues once it is loaded.

        The headset can only hold one profile, and Cortex will not let us train
        against one another application loaded. prepare_profile unloads
        whatever is sitting there before the create goes out.
        """
        print(f"Requesting creation of profile: {profile_name}")
        self.c.prepare_profile(profile_name, 'create')

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
