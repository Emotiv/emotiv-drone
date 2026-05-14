# BCI Core Module

The `bci_core` module is the computational heart of the Emotiv Drone project. It handles the transformation of raw EEG and motion data into actionable flight commands.

## 📂 Component Breakdown

### 1. `processor.py` (Motion Processing)
Contains the `QuaternionProcessor` class. 
- **Responsibility**: Processes raw quaternion data from the Emotiv headset's IMU.
- **Logic**: 
  - Converts Quaternions to Euler angles (Pitch, Roll, Yaw).
  - Normalizes angles based on calibrated "neutral" head positions.
  - Applies a configurable deadzone to prevent drone drift from minor head movements.
  - Provides a smoothing window to eliminate jitter.

### 2. `mental.py` (Mental Command Processing)
Contains the `MentalCommandProcessor`.
- **Responsibility**: Manages the state and thresholds for mental commands.
- **Logic**:
  - Monitors the power levels of trained mental commands (e.g., Push, Pull).
  - Implements an "activation threshold" (default 0.5 - 0.7).
  - Handles "auto-release" logic to ensure a single mental trigger doesn't loop a command indefinitely.

### 3. `program.py` (State Management)
Contains the `ProgramSimulator`.
- **Responsibility**: Acts as a state machine for the entire application.
- **Logic**:
  - Orchestrates the transition between "Connected", "TakeOff", "InFlight", and "Landing" states.
  - Merges motion commands and mental commands into a single `RC_Command` packet for the drone.

### 4. `ai_helpers.py` (Future/Auxiliary Logic)
Contains helper utilities for advanced signal processing or potential integration with machine learning models for improved command classification.

## 🛠 Usage in the Project

This module is imported by `drone_controller.py` to create the processing pipeline:

```python
from bci_core.processor import QuaternionProcessor
from bci_core.mental import MentalCommandProcessor

# Initialize processors
motion = QuaternionProcessor(sensitivity=0.8)
mental = MentalCommandProcessor()
```

---

*Note: This module is designed to be hardware-agnostic where possible, allowing for future expansion to other EEG devices or drone SDKs.*
