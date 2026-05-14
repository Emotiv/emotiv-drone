class MentalCommandProcessor:
    def __init__(self, mappings=None):
        # mappings format is now a list: [{"command": "push", "action": "LeftPress", "threshold": 0.5, "auto_release": 0}]
        if mappings is None:
            self.mappings = [
                {"command": "push", "action": "LeftPress", "threshold": 0.5, "auto_release": 0},
                {"command": "lift", "action": "RightPress", "threshold": 0.5, "auto_release": 0},
                {"command": "drop", "action": "LeftRelease", "threshold": 0.3, "auto_release": 0},
                {"command": "pull", "action": "RightRelease", "threshold": 0.3, "auto_release": 0}
            ]
        else:
            self.mappings = mappings

    def process_command(self, command: str, force: float):
        cmd = command.lower()
        for mapping in self.mappings:
            if mapping.get("command", "").lower() == cmd:
                if force >= mapping.get("threshold", 0.5):
                    return mapping.get("action", "None"), mapping.get("auto_release", 0.0), True
        return "None", 0.0, False

    def is_above_threshold(self, command: str, force: float) -> bool:
        cmd = command.lower()
        for mapping in self.mappings:
            if mapping.get("command", "").lower() == cmd:
                return force >= mapping.get("threshold", 0.5)
        return False
