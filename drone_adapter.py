"""
Drone Adapter – translates head motion deltas and mental commands into Tello RC commands.

Maps:
  - Head yaw  (dx) → yaw_velocity  (rotation in place)
  - Head pitch (dy) → forward_backward_velocity (pitch / forward-backward)
  - Mental commands → discrete drone actions (TakeOff, Land, Flip, EmergencyStop)
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
            if self.tello and self.is_flying:
                with self.lock:
                    lr, fb, ud, yaw = self._lr, self._fb, self._ud, self._yaw
                try:
                    self.tello.send_rc_control(lr, fb, ud, yaw)
                except Exception as e:
                    print(f"[DroneAdapter] RC send error: {e}")
            time.sleep(0.05)  # 20 Hz

    # ──────────────────────────────────────────────
    # Head motion → RC translation
    # ──────────────────────────────────────────────
    def move_by(self, dx: int, dy: int):
        """Called by the bci_core loop with cursor-like deltas.
        
        dx > 0 → head turned right → drone rotates right
        dy > 0 → head tilted down  → drone moves forward
        """
        with self.lock:
            # Scale deltas to RC range (-100..100)
            self._lr = 0                             # left-right (disabled)
            self._yaw = self._clamp(int(dx * 2.5))   # rotate left-right
            self._fb = self._clamp(int(dy * 2.5))    # forward-backward (head down = forward)
            # ud is left at 0 unless explicitly set
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
            
        try:
            if action == "TakeOff":
                if not self.is_flying:
                    print("[DroneAdapter] Taking off...")
                    if self.tello: self.tello.takeoff()
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
        with self.lock:
            return self._lr, self._fb, self._ud, self._yaw

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
