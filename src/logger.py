from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


def log_run(log_path: Path, record: dict[str, Any]) -> None:
    """Append one JSONL decision record. Never pass secrets in `record`."""
    entry = {"ts": datetime.now(timezone.utc).isoformat(), **record}
    with log_path.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(entry, ensure_ascii=False) + "\n")
