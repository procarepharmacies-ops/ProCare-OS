"""Branch management — code-to-ID mapping and branch operations."""
from __future__ import annotations

from app.db import get_db

_BRANCH_CACHE = {}  # code -> branch_id


def get_branch_id(branch_code: str) -> int:
    """
    Get branch_id from branch code ('main', 'elsanta', 'mshala').

    Cached after first query.

    Args:
      branch_code: 'main' | 'elsanta' | 'mshala'

    Returns:
      branch_id (integer PK)

    Raises:
      ValueError if branch not found
    """
    code = branch_code.lower().strip()

    if code in _BRANCH_CACHE:
        return _BRANCH_CACHE[code]

    db = get_db()
    branch = db.query_one(
        "SELECT branch_id FROM branches WHERE LOWER(code) = ?", [code]
    )

    if not branch:
        raise ValueError(f"Branch '{branch_code}' not found")

    branch_id = branch["branch_id"]
    _BRANCH_CACHE[code] = branch_id

    return branch_id


def get_branch_code(branch_id: int) -> str:
    """Get branch code from branch_id."""
    db = get_db()
    branch = db.query_one("SELECT code FROM branches WHERE branch_id = ?", [branch_id])

    if not branch:
        raise ValueError(f"Branch ID {branch_id} not found")

    return branch["code"].lower()


def normalize_branch(branch_identifier: str | int) -> int:
    """
    Normalize branch identifier to branch_id (integer).

    Args:
      branch_identifier: branch code (str) or branch_id (int)

    Returns:
      branch_id (integer PK)
    """
    if isinstance(branch_identifier, int):
        return branch_identifier
    return get_branch_id(branch_identifier)
