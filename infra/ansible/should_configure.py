"""Decide whether a push needs server configuration before deployment."""

import sys


def should_configure(event: str, paths: list[str]) -> bool:
    if event == "workflow_dispatch":
        return True
    if event != "push":
        raise ValueError(f"Unsupported deployment event: {event}")
    return any(path.startswith("infra/ansible/") for path in paths)


if __name__ == "__main__":
    try:
        result = should_configure(sys.argv[1], [line.strip() for line in sys.stdin])
    except (IndexError, ValueError) as error:
        raise SystemExit(str(error)) from error
    print("true" if result else "false")
