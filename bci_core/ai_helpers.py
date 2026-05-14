# Constants and test vectors copied from C# AI_helpers blueprint

IDENTITY_QUAT = (1.0, 0.0, 0.0, 0.0)
PITCH_90_DOWN = (0.7071, 0.7071, 0.0, 0.0)
PITCH_90_UP = (0.7071, -0.7071, 0.0, 0.0)
YAW_90_LEFT = (0.7071, 0.0, 0.0, 0.7071)
YAW_90_RIGHT = (0.7071, 0.0, 0.0, -0.7071)
FORTY_FIVE_COMBINED = (0.9239, 0.3827, 0.0, 0.3827)

# Program constants
BASE_SENSITIVITY = 0.24
HORIZONTAL_SENSITIVITY = 70.0
VERTICAL_SENSITIVITY = 50.0
MOVEMENT_DEADZONE = 0.03
SMOOTHING_WINDOW = 6
CALIBRATION_SAMPLE_COUNT = 60

# Mental command vectors
MENTAL_VECTORS = [
    ("push", 0.6, "MouseDown", True),
    ("push", 0.5, "MouseDown", True),
    ("push", 0.4, "None", False),
    ("lift", 0.6, "MouseDown", True),
    ("drop", 0.4, "MouseUp", True),
    ("drop", 0.3, "MouseUp", True),
    ("drop", 0.2, "None", False),
    ("pull", 0.4, "MouseUp", True),
    ("click", 0.6, "Click", True),
    ("neutral", 1.0, "None", False),
    ("unknown", 1.0, "None", False),
]
