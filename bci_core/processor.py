from collections import deque
from dataclasses import dataclass
import math
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
        
        self.movement_deadzone: float = 0.03
        self.current_sensitivity: float = self.base_sensitivity

        self._calibration_quaternion: Quaternion = Quaternion.identity()
        self._is_calibrated: bool = False

        self._movement_buffer: Deque[Tuple[float, float]] = deque(maxlen=self.SmoothingWindow)

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
        self._movement_buffer.clear()
        self._calibration_samples.clear()

    def calculate_cursor_movement(self, current_w: float, current_x: float, current_y: float, current_z: float) -> Tuple[int, int]:
        if not self._is_calibrated:
            return 0, 0

        current_q = Quaternion(current_w, current_x, current_y, current_z)
        relative_q = current_q.relative_to(self._calibration_quaternion)

        relative_pitch = 2 * relative_q.x
        relative_yaw = 2 * relative_q.z

        # Deadzone
        if abs(relative_yaw) < self.movement_deadzone:
            relative_yaw = 0.0
        if abs(relative_pitch) < self.movement_deadzone:
            relative_pitch = 0.0

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
        return int(avg_x), int(avg_y)
