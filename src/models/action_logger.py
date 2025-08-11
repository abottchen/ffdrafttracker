from pathlib import Path
from typing import Any

from .action_log import ActionLog


class ActionLogger:
    """Utility for logging draft actions to file"""

    def __init__(self, log_file_path: Path):
        self.log_file_path = log_file_path

    def log_action(self, action_type: str, owner_id: int, data: dict[str, Any]) -> None:
        """Log an action to the action log file"""
        action = ActionLog(action_type=action_type, owner_id=owner_id, data=data)

        # Load existing logs or create empty list
        logs = self._load_logs()

        # Add new action
        logs.append(action)

        # Save back to file using atomic operations
        self._save_logs(logs)

    def _load_logs(self) -> list[ActionLog]:
        """Load existing action logs from file"""
        if not self.log_file_path.exists():
            return []

        try:
            logs_data = self.log_file_path.read_text()
            if not logs_data.strip():
                return []

            # Parse as list of ActionLog objects
            import json

            logs_json = json.loads(logs_data)
            return [ActionLog(**log_data) for log_data in logs_json]
        except Exception:
            return []  # If file is corrupted, start fresh

    def _save_logs(self, logs: list[ActionLog]) -> None:
        """Save action logs to file using atomic operations"""
        # Write to temporary file first
        temp_filepath = self.log_file_path.with_suffix(".tmp")

        import json

        logs_json = [log.model_dump() for log in logs]
        temp_filepath.write_text(json.dumps(logs_json, indent=2, default=str))

        # Atomically replace the original
        temp_filepath.replace(self.log_file_path)
