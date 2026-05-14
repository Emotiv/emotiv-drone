from typing import List, Any, Tuple
from .processor import QuaternionProcessor
from .mental import MentalCommandProcessor


class ProgramSimulator:
    """Simulates the Program wiring and calibration behaviour from C# Program.cs

    Important: replicates the original motion data indexing mismatch for parity:
    w = motion[3], x = motion[4], y = motion[5], z = motion[6]
    """

    def __init__(self, mental_mappings=None):
        self.quaternion_processor = QuaternionProcessor()
        self.mental_processor = MentalCommandProcessor(mappings=mental_mappings)

        self.calibration_in_progress = False
        self.calibration_samples = 0
        self.calibration_sample_count = 60

    def start_calibration(self):
        self.calibration_in_progress = True
        self.calibration_samples = 0
        # internally processed in accumulate_calibration_sample

    def receive_motion(self, motion: List[Any]) -> Tuple[int, int]:
        # Expecting a list-like object where indices 3..6 are w,x,y,z
        if len(motion) < 7:
            return 0, 0

        try:
            w = float(motion[3])
            x = float(motion[4])
            y = float(motion[5])
            z = float(motion[6])
        except Exception:
            return 0, 0

        if self.calibration_in_progress:
            self.quaternion_processor.accumulate_calibration_sample(w, x, y, z)
            self.calibration_samples += 1
            if self.calibration_samples >= self.calibration_sample_count:
                self.calibration_in_progress = False
            return 0, 0

        if not self.quaternion_processor.is_calibrated:
            # Auto-calibrate on first sample, as C# does
            self.quaternion_processor.calibrate(w, x, y, z)
            return 0, 0

        movement = self.quaternion_processor.calculate_cursor_movement(w, x, y, z)
        return movement

    def receive_mental(self, mental: List[Any]):
        # Expected structure: [timestamp?, command, force]
        if len(mental) < 3:
            return "None", 0.0, False
        command = str(mental[1])
        try:
            force = float(mental[2])
        except Exception:
            force = 0.0
        return self.mental_processor.process_command(command, force)
