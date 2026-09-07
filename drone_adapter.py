"""
Drone Adapter – translates head motion deltas and mental commands into Tello RC commands.

Maps:
  - Head yaw  (dx) → yaw_velocity  (rotation in place)
  - Head pitch (dy) → forward_backward_velocity (pitch / forward-backward)
  - Mental commands → discrete drone actions:
      TakeOff, Land, EmergencyStop,
      FlipForward/Back/Left/Right,
      MoveForward/Back/Left/Right/Up/Down
"""

import threading
import time


class DroneAdapter:
    """Bridges the gap between bci_core motion output and Tello SDK calls."""

    def __init__(self, tello=None, max_speed: int = 60,
                 yaw_sensitivity: float = 0.5,
                 throttle_sensitivity: float = 0.5,
                 altitude_hold: bool = True):
        self.tello = tello  # djitellopy.Tello instance or None for simulation
        self.max_speed = max_speed
        self.yaw_sensitivity = yaw_sensitivity
        self.throttle_sensitivity = throttle_sensitivity
        self.altitude_hold = altitude_hold

        self.is_flying = False
        self.lock = threading.Lock()

        # Current RC values (continuously sent at ~20Hz)
        self._lr = 0    # left-right velocity
        self._fb = 0    # forward-backward velocity
        self._ud = 0    # up-down velocity
        self._yaw = 0   # yaw (rotation)

        self._rc_thread = None
        self._running = False
        
        self.mental_move_actions = set()
        
        # State for smoothly ramping mental movements
        self._mental_move_action = None
        self._mental_move_speed = 0.0
        self._mental_move_expiry = 0.0
        
        # UI Feedback Tracking
        self.last_executed_action = None
        self.last_action_time = 0.0

    # ──────────────────────────────────────────────
    # RC command loop – Tello needs constant updates
    # ──────────────────────────────────────────────
    def start_rc_loop(self):
        """Begin sending RC commands at ~20Hz."""
        if self._rc_thread is not None:
            return
        self._running = True
        self._rc_thread = threading.Thread(target=self._rc_loop, daemon=True)
        self._rc_thread.start()

    def stop_rc_loop(self):
        self._running = False
        if self._rc_thread:
            self._rc_thread.join(timeout=2)
            self._rc_thread = None

    def _rc_loop(self):
        while self._running:
            # Let get_rc_values handle the combination of mental + motion
            lr, fb, ud, yaw = self.get_rc_values()

            if self.tello and self.is_flying:
                try:
                    self.tello.send_rc_control(lr, fb, ud, yaw)
                except Exception as e:
                    print(f"[DroneAdapter] RC send error: {e}")
            time.sleep(0.05)  # 20 Hz

    # ──────────────────────────────────────────────
    # Head motion → RC translation
    # ──────────────────────────────────────────────
    def set_mental_move_actions(self, actions: set):
        with self.lock:
            self.mental_move_actions = set(actions)

    def move_by(self, dx: int, dy: int):
        """Called by the bci_core loop with cursor-like deltas.

        Head motion no longer produces any RC velocity. Steering is absolute:
        the head's angle is the drone's heading, read straight off
        QuaternionProcessor.head_heading_deg by the simulator. Turning that
        angle into a yaw *rate* here was the whole problem — a rate has memory,
        so a head parked a few degrees off centre span the drone forever, and
        int() quantised what was left into six coarse steps.

        Tilt never did anything either: forward comes from the trained mental
        command. So all four channels are held at zero and both arguments are
        accepted only because the bci_core loop supplies them.
        """
        with self.lock:
            self._lr = 0
            self._fb = 0
            self._yaw = 0
            if self.altitude_hold:
                self._ud = 0

    def set_yaw(self, yaw_value: int):
        """Set yaw rotation independently (e.g., from a separate input)."""
        with self.lock:
            self._yaw = self._clamp(yaw_value)

    def set_throttle(self, throttle_value: int):
        """Set up/down independently."""
        with self.lock:
            self._ud = self._clamp(throttle_value)

    def stop_movement(self):
        """Zero out all RC channels."""
        with self.lock:
            self._lr = self._fb = self._ud = self._yaw = 0

    # ──────────────────────────────────────────────
    # Mental command → Discrete drone actions
    # ──────────────────────────────────────────────
    def execute_action(self, action: str, auto_release_time: float = 0.0):
        """Execute a discrete drone action from a mental command."""
        action = action.strip()
        if action == "None":
            return

        self.last_executed_action = action
        self.last_action_time = time.time()

        # Duration to hold mental movements
        move_duration = auto_release_time if auto_release_time > 0 else 1.0

        try:
            if action == "TakeOff":
                if not self.is_flying:
                    print("[DroneAdapter] Taking off...")
                    if self.tello: 
                        self.tello.takeoff()
                        self.tello.move_up(40)  # Ascend to ~1.6m
                    self.is_flying = True
                    self.start_rc_loop()
                else:
                    print("[DroneAdapter] Ignored TakeOff (already flying)")

            elif action == "Land":
                if self.is_flying:
                    print("[DroneAdapter] Landing...")
                    self.stop_movement()
                    if self.tello: self.tello.land()
                    self.is_flying = False
                else:
                    print("[DroneAdapter] Ignored Land (already landed)")

            elif action == "EmergencyStop":
                print("[DroneAdapter] EMERGENCY STOP!")
                self.stop_movement()
                if self.tello: self.tello.emergency()
                self.is_flying = False

            elif action.startswith("Flip"):
                if self.is_flying:
                    direction = action.replace("Flip", "").lower()[0]  # f, b, l, r
                    if direction in ('f', 'b', 'l', 'r'):
                        print(f"[DroneAdapter] Flipping {direction}...")
                        if self.tello: self.tello.flip(direction)
                else:
                    print(f"[DroneAdapter] Ignored Flip (not flying)")

            elif action.startswith("Move"):
                # Delegate movement to _rc_loop
                with self.lock:
                    if self._mental_move_action == action and time.time() < self._mental_move_expiry:
                        # Action is already running: refresh the timer without resetting velocity
                        self._mental_move_expiry = time.time() + move_duration
                        print(f"[DroneAdapter] {action} time refreshed (+{move_duration}s)")
                    else:
                        # New action: start from speed 1
                        self._mental_move_action = action
                        self._mental_move_speed = 1.0
                        self._mental_move_expiry = time.time() + move_duration
                        print(f"[DroneAdapter] {action} started (ramping to 30 over {move_duration}s)")
                
            else:
                print(f"[DroneAdapter] Unknown action: {action}")

        except Exception as e:
            print(f"[DroneAdapter] Action error ({action}): {e}")

    # ──────────────────────────────────────────────
    # Helpers
    # ──────────────────────────────────────────────
    def _clamp(self, value: int) -> int:
        return max(-self.max_speed, min(self.max_speed, value))

    def get_rc_values(self):
        """Returns the final combined RC values (motion + active mental movement)."""
        with self.lock:
            # Process mental movement progression
            now = time.time()
            m_lr = m_fb = m_ud = m_yaw = 0
            if self._mental_move_action and now < self._mental_move_expiry:
                # Increase speed gradually up to 30
                if self._mental_move_speed < 30.0:
                    # Called at ~20Hz if rc_loop is running, or slightly different by UI
                    # so 1.5 per tick is roughly 1 second to 30.
                    self._mental_move_speed = min(30.0, self._mental_move_speed + 1.5)
                
                speed = int(self._mental_move_speed)
                if self._mental_move_action == "MoveForward": m_fb = speed
                elif self._mental_move_action == "MoveBack": m_fb = -speed
                elif self._mental_move_action == "MoveLeft": m_lr = -speed
                elif self._mental_move_action == "MoveRight": m_lr = speed
                elif self._mental_move_action == "MoveUp": m_ud = speed
                elif self._mental_move_action == "MoveDown": m_ud = -speed
            else:
                self._mental_move_action = None
                self._mental_move_speed = 0.0

            # Combine: mental motion overrides head motion on active axes
            lr = m_lr if m_lr != 0 else self._lr
            fb = m_fb if m_fb != 0 else self._fb
            ud = m_ud if m_ud != 0 else self._ud
            yaw = m_yaw if m_yaw != 0 else self._yaw
            
            return lr, fb, ud, yaw

    def cleanup(self):
        """Safely stop everything."""
        self.stop_rc_loop()
        self.stop_movement()
        if self.tello and self.is_flying:
            try:
                self.tello.land()
            except Exception:
                pass
            self.is_flying = False
