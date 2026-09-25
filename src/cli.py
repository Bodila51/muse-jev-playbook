from __future__ import annotations

import json
import sys

from src.router import route_task


def main(argv: list[str] | None = None) -> int:
    argv = argv if argv is not None else sys.argv[1:]
    if not argv:
        print("Usage: python -m src.cli '<json state>'", file=sys.stderr)
        return 2
    try:
        state = json.loads(argv[0])
    except (TypeError, ValueError) as exc:
        print(f"invalid JSON state: {exc}", file=sys.stderr)
        return 2
    if not isinstance(state, dict):
        print("invalid JSON state: expected an object", file=sys.stderr)
        return 2
    try:
        out = route_task(state)
    except Exception as exc:
        out = {
            "action": "proceed_full",
            "reason": "Jev route unavailable",
            "mode": "shadow",
            "jev_used": False,
            "details": {"error_class": type(exc).__name__},
            "policy": {
                "honor_in_active_mode": False,
                "shadow_mode_is_advisory": True,
            },
        }
    print(json.dumps(out, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
