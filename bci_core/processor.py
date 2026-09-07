from collections import deque
from dataclasses import dataclass
import math
import time
from typing import Tuple, Deque, List, Optional

import numpy as np


@dataclass
class Quaternion:
    w: float
    x: float
    y: float
    z: float

    @staticmethod
    def identity() -> "Quaternion":
        return Quaternion(1.0, 0.0, 0.0, 0.0)

    def normalize(self) -> "Quaternion":
        norm = math.sqrt(self.w * self.w + self.x * self.x + self.y * self.y + self.z * self.z)
        if norm > 0:
            return Quaternion(self.w / norm, self.x / norm, self.y / norm, self.z / norm)
        return Quaternion.identity()

    def conjugate(self) -> "Quaternion":
        return Quaternion(self.w, -self.x, -self.y, -self.z)

    def multiply(self, other: "Quaternion") -> "Quaternion":
        # Quaternion multiplication: self * other
        w = self.w * other.w - self.x * other.x - self.y * other.y - self.z * other.z
        x = self.w * other.x + self.x * other.w + self.y * other.z - self.z * other.y
        y = self.w * other.y - self.x * other.z + self.y * other.w + self.z * other.x
        z = self.w * other.z + self.x * other.y - self.y * other.x + self.z * other.w
        return Quaternion(w, x, y, z)

    def relative_to(self, reference: "Quaternion") -> "Quaternion":
        conj = reference.conjugate()
        return self.multiply(conj)


class QuaternionProcessor:
    SmoothingWindow = 6

    def __init__(self):
        # Defaults copied from C# implementation
        self.base_sensitivity: float = 0.24
        self.sens_left: float = 70.0
        self.sens_right: float = 70.0
        self.sens_fwd: float = 50.0  # head down (forward)
        self.sens_back: float = 50.0 # head up (backward)
        
        self.movement_deadzone: float = 0.02
        # Steering is absolute: the head's angle sets the drone's heading
        # rather than how fast it spins. head_gain multiplies a comfortable
        # head turn up into a useful one -- 3.0 turns a 30 degree look into a
        # 90 degree heading. head_deadzone_deg is subtracted rather than
        # zeroed, so there is no jump at its edge; it only suppresses sensor
        # noise and a small calibration error around centre.
        self.head_gain: float = 3.0
        self.head_deadzone_deg: float = 2.0
        self.head_limit_deg: float = 120.0
        # How much of the response is pushed away from centre. 0 is a straight
        # line, where a small head movement steers as hard per degree as a
        # large one and the drone feels twitchy. 1 is fully cubic. In between,
        # small movements are gentle and big ones still reach the full range,
        # which is what "less sensitive" almost always means -- calmer around
        # centre, not a smaller turning circle.
        self.head_expo: float = 0.6

        # Drift correction. The headset's yaw estimate is a gyro integration
        # with nothing pulling it back, so it ramps: measured at 1.81 deg/min
        # on an INSIGHT2 over a recorded minute of the wearer sitting still,
        # monotonic and never reversing. One run hides it inside the deadzone;
        # a session left open across a queue of people does not, and position
        # steering reads the accumulated ramp as a head turned off centre.
        #
        # A plain leak toward the current angle cannot cancel a ramp -- it
        # settles at an offset proportional to the drift rate. This tracks the
        # rate as well as the offset, so the error goes to zero rather than to
        # a constant, and once the rate is learned the correction keeps working
        # through head movement rather than only when still.
        self.drift_correction: bool = True
        # Adaptation stops past this much error, so a deliberate turn is never
        # mistaken for drift and quietly eaten. Drift is held well inside it,
        # so in practice the gate only trips when the wearer means it.
        self.drift_gate_deg: float = 5.0
        self.drift_rate_limit_deg_s: float = 3.0
        # Roughly the time the correction takes to converge, in seconds.
        self.drift_settle_s: float = 10.0

        self._zero_deg: float = 0.0
        self._drift_rate: float = 0.0
        self._last_update: float = 0.0
        # Injectable so drift correction can be replayed against recorded data
        # at whatever speed, instead of only ever being testable in real time.
        self.time_source = time.monotonic
        # Where the drone should be pointing, degrees off the calibrated
        # centre. Read by the simulator every frame.
        self.head_heading_deg: float = 0.0
        # The head's own angle, before gain. Logged, not steered by.
        self.head_yaw_deg: float = 0.0
        # The same angle before smoothing, so a capture can separate sensor
        # noise from the smoothing window's lag.
        self.head_yaw_raw_deg: float = 0.0
        self.invert_yaw: bool = False
        # Forward/back, separately from left/right: a headset can disagree with
        # the base orientation on one axis without disagreeing on both.
        self.invert_pitch: bool = False
        self.current_sensitivity: float = self.base_sensitivity

        self._calibration_quaternion: Quaternion = Quaternion.identity()
        self._is_calibrated: bool = False

        self._movement_buffer: Deque[Tuple[float, float]] = deque(maxlen=self.SmoothingWindow)
        # Smoothing for the absolute heading, kept separate from the buffer
        # above: that one holds rate values scaled by sensitivity, and an angle
        # averaged after scaling is not the same as the average angle.
        self._angle_buffer: Deque[float] = deque(maxlen=self.SmoothingWindow)

        # Every intermediate value from the most recent left/right calculation,
        # so a machine where steering does not work can be diagnosed from the
        # log instead of by guessing. Written on every frame, read and printed
        # at about 1 Hz by the caller. See last_yaw_debug.
        self.last_yaw_debug: Optional[dict] = None

        # For calibration aggregation
        self._calibration_samples: List[Quaternion] = []
        self._calibration_sample_count: int = 60

    @property
    def is_calibrated(self) -> bool:
        return self._is_calibrated

    def calibrate(self, w: float, x: float, y: float, z: float) -> None:
        q = Quaternion(w, x, y, z).normalize()
        self._calibration_quaternion = q
        self._is_calibrated = True
        self._movement_buffer.clear()
        self._angle_buffer.clear()
        self.head_heading_deg = 0.0
        self.head_yaw_deg = 0.0
        self._zero_deg = 0.0
        self._drift_rate = 0.0
        self._last_update = 0.0

    def accumulate_calibration_sample(self, w: float, x: float, y: float, z: float) -> None:
        self._calibration_samples.append(Quaternion(w, x, y, z))
        if len(self._calibration_samples) >= self._calibration_sample_count:
            self.complete_calibration()

    def complete_calibration(self) -> None:
        if len(self._calibration_samples) == 0:
            return
        # Average components then normalize (match Program.cs behavior)
        ws = [q.w for q in self._calibration_samples]
        xs = [q.x for q in self._calibration_samples]
        ys = [q.y for q in self._calibration_samples]
        zs = [q.z for q in self._calibration_samples]

        w_avg = float(np.mean(ws))
        x_avg = float(np.mean(xs))
        y_avg = float(np.mean(ys))
        z_avg = float(np.mean(zs))

        # Normalize
        norm = math.sqrt(w_avg * w_avg + x_avg * x_avg + y_avg * y_avg + z_avg * z_avg)
        if norm > 0:
            w_avg /= norm
            x_avg /= norm
            y_avg /= norm
            z_avg /= norm
        else:
            w_avg, x_avg, y_avg, z_avg = 1.0, 0.0, 0.0, 0.0

        self._calibration_samples.clear()
        self.calibrate(w_avg, x_avg, y_avg, z_avg)

    def reset(self) -> None:
        self._calibration_quaternion = Quaternion.identity()
        self._is_calibrated = False
        # Recenter re-runs the averaging, so any half-collected batch from a
        # previous attempt must not carry into it.
        self._movement_buffer.clear()
        self._angle_buffer.clear()
        self.head_heading_deg = 0.0
        self.head_yaw_deg = 0.0
        self._zero_deg = 0.0
        self._drift_rate = 0.0
        self._last_update = 0.0
        self._calibration_samples.clear()

    def _correct_drift(self, angle: float) -> float:
        """Subtract the headset's own slow rotation from the head's angle.

        An alpha-beta tracker: the offset chases the error, and the rate
        chases it too, one integration further out. Chasing the offset alone
        would leave a standing error proportional to the drift rate, which is
        the whole problem restated; carrying a rate term drives it to zero and
        keeps cancelling drift during head movement, not just at rest.

        Past drift_gate_deg the tracker stops learning but keeps applying what
        it has already learned. That way a deliberate turn is not absorbed as
        drift, while drift does not silently accumulate behind it.
        """
        if not self.drift_correction:
            return angle

        now = self.time_source()
        if self._last_update == 0.0:
            self._last_update = now
            return angle
        # Cap dt so a stall -- a paused debugger, a stream hiccup -- cannot
        # slam the estimate with one enormous step.
        dt = min(0.25, max(0.0, now - self._last_update))
        self._last_update = now
        if dt <= 0.0:
            return angle - self._zero_deg

        # Critically damped for the configured settling time.
        tau = max(1.0, self.drift_settle_s)
        k_offset = 2.0 / tau
        k_rate = 1.0 / (tau * tau)

        error = angle - self._zero_deg
        if abs(error) < self.drift_gate_deg:
            self._drift_rate += k_rate * error * dt
            limit = self.drift_rate_limit_deg_s
            self._drift_rate = max(-limit, min(limit, self._drift_rate))
            self._zero_deg += (self._drift_rate + k_offset * error) * dt
        else:
            self._zero_deg += self._drift_rate * dt

        return angle - self._zero_deg

    def _update_heading(self, relative_q: "Quaternion") -> None:
        """Turn the head's angle into the heading the drone should hold.

        This replaces rate steering, where the head set how fast the drone
        span and holding it a few degrees off centre span it forever. Position
        steering has no memory: whatever angle the head is at right now is the
        angle the drone points at, so a small calibration error is a small
        fixed aim error instead of an endless rotation, and letting the head
        return to centre returns the drone to centre.

        asin rather than the small-angle 2*z used above, so a 40 degree look
        reads as 40 degrees instead of being quietly compressed.
        """
        angle = math.degrees(2.0 * math.asin(max(-1.0, min(1.0, relative_q.z))))
        if self.invert_yaw:
            angle = -angle

        self.head_yaw_raw_deg = angle
        self._angle_buffer.append(angle)
        smoothed = sum(self._angle_buffer) / len(self._angle_buffer)
        smoothed = self._correct_drift(smoothed)
        self.head_yaw_deg = smoothed

        # Subtracting the deadzone instead of zeroing inside it keeps the
        # response continuous: at the edge the output is 0 either way, so
        # there is no step to fall off.
        if abs(smoothed) <= self.head_deadzone_deg:
            centred = 0.0
        else:
            centred = math.copysign(
                abs(smoothed) - self.head_deadzone_deg, smoothed)

        # Shape the response before clamping. Working in normalised units
        # keeps expo independent of gain: full head deflection still reaches
        # full heading whatever the curve, only the path there changes.
        limit = self.head_limit_deg
        u = max(-1.0, min(1.0, (centred * self.head_gain) / limit))
        expo = max(0.0, min(1.0, self.head_expo))
        shaped = expo * (u ** 3) + (1.0 - expo) * u

        self.head_heading_deg = shaped * limit

    def calculate_cursor_movement(self, current_w: float, current_x: float, current_y: float, current_z: float) -> Tuple[int, int]:
        if not self._is_calibrated:
            return 0, 0

        current_q = Quaternion(current_w, current_x, current_y, current_z)
        relative_q = current_q.relative_to(self._calibration_quaternion)

        relative_pitch = 2 * relative_q.x
        relative_yaw = 2 * relative_q.z

        self._update_heading(relative_q)

        # Kept for the diagnostics below: once the deadzone has zeroed it there
        # is no way to tell "head was still" from "head moved but not enough".
        measured_yaw = relative_yaw

        # Deadzone
        if abs(relative_yaw) < self.movement_deadzone:
            relative_yaw = 0.0
        if abs(relative_pitch) < self.movement_deadzone:
            relative_pitch = 0.0

        if self.invert_yaw:
            relative_yaw = -relative_yaw
        if self.invert_pitch:
            relative_pitch = -relative_pitch

        # Apply independent directional sensitivity
        h_sens = self.sens_right if relative_yaw > 0 else self.sens_left
        v_sens = self.sens_fwd if relative_pitch < 0 else self.sens_back

        raw_x = relative_yaw * h_sens * self.current_sensitivity
        raw_y = -relative_pitch * v_sens * self.current_sensitivity

        # Enqueue float values and smooth
        self._movement_buffer.append((raw_x, raw_y))
        if len(self._movement_buffer) == 0:
            return 0, 0

        avg_x = float(np.mean([p[0] for p in self._movement_buffer]))
        avg_y = float(np.mean([p[1] for p in self._movement_buffer]))

        # Truncate toward zero same as C# (int())
        dx, dy = int(avg_x), int(avg_y)

        # Where a turn of the head is lost, if it is lost. Two separate gates
        # can swallow it and they need different fixes: the deadzone is a
        # config value, while truncation is the int() above discarding
        # everything under one whole unit, which no amount of deadzone
        # tuning helps with.
        if dx != 0:
            gate = "none"
        elif measured_yaw == 0.0:
            gate = "still"
        elif relative_yaw == 0.0:
            gate = "deadzone"
        else:
            gate = "truncated"

        self.last_yaw_debug = {
            "measured": measured_yaw,   # 2*qz, before deadzone; ~radians
            "gated": relative_yaw,      # after deadzone and inversion
            "deadzone": self.movement_deadzone,
            "sens": h_sens,
            "base": self.current_sensitivity,
            "scaled": raw_x,            # after sensitivity, before smoothing
            "smoothed": avg_x,
            "dx": dx,
            "invert_yaw": self.invert_yaw,
            "gate": gate,
        }

        return dx, dy
