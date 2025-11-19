from typing import Literal


def convert_file_locking(
    locking: Literal["true", "false", "best-effort"] | bool,
) -> tuple[bool, bool]:
    """Convert high-level API file locking argument to H5Pset_file_locking arguments"""
    if locking in ("false", False):
        return False, False
    elif locking in ("true", True):
        return True, False
    elif locking == "best-effort":
        return True, True

    raise ValueError(f"Unsupported locking value: {locking}")
