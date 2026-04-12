# Ref: docs/features/phase5-dcc-integration.md
"""
FilterEvaluator — condition matching for trigger rules.

Evaluates trigger rule conditions against incoming DCC event data.

Conditions format (stored as JSON dict on TriggerRule.conditions):
    {
        "path": ["*.fbx", "Characters/*"],      # glob match (OR within dimension)
        "name": ["^SM_.*"],                       # regex match
        "type": ["StaticMesh", "SkeletalMesh"]   # exact type match
    }

Different dimensions (path, name, type, …) are ANDed together.
Patterns within the same dimension are ORed.
"""
from __future__ import annotations

import fnmatch
import re
from typing import Any, Dict, List, Optional, Union


class FilterEvaluator:
    """Evaluate trigger rule conditions against event data."""

    def evaluate(
        self,
        conditions: Optional[Dict[str, Any]],
        event_data: Dict[str, Any],
    ) -> bool:
        """Return True if *event_data* satisfies all *conditions*.

        - ``None`` / empty conditions → always match.
        - Each key in conditions is a dimension; its value is a list of
          patterns.  All dimensions must match (AND).  Within a dimension,
          any pattern matching is sufficient (OR).
        """
        if not conditions:
            return True

        for key, patterns in conditions.items():
            if not patterns:
                continue
            # Normalise patterns to a list
            if isinstance(patterns, str):
                patterns = [patterns]
            value = self._extract_value(key, event_data)
            if value is None:
                return False  # Required field missing → fail
            if not self._match_any(key, patterns, value):
                return False
        return True

    # ------------------------------------------------------------------
    # Value extraction
    # ------------------------------------------------------------------

    def _extract_value(self, key: str, event_data: Dict[str, Any]) -> Optional[str]:
        """Extract a string value from *event_data* for the given *key*.

        Lookup order:
        1. ``event_data["data"][key]``  (DCC-specific payload)
        2. ``event_data[key]``          (top-level event fields)
        3. Dot-notation traversal       (e.g. ``data.asset.path``)
        """
        data_sub: Dict[str, Any] = event_data.get("data", {})
        if key in data_sub:
            return str(data_sub[key])
        if key in event_data:
            return str(event_data[key])

        # Dot-notation fallback
        parts = key.split(".")
        current: Any = event_data
        for part in parts:
            if isinstance(current, dict) and part in current:
                current = current[part]
            else:
                return None
        return str(current) if current is not None else None

    # ------------------------------------------------------------------
    # Pattern matching
    # ------------------------------------------------------------------

    def _match_any(self, key: str, patterns: List[str], value: str) -> bool:
        """Return True if *value* matches **any** pattern in the list."""
        for pattern in patterns:
            if self._match_single(key, pattern, value):
                return True
        return False

    @staticmethod
    def _match_single(key: str, pattern: str, value: str) -> bool:
        """Match a single *pattern* against *value* using key-appropriate logic."""
        if key == "path":
            return fnmatch.fnmatch(value, pattern)
        if key == "name":
            try:
                return re.match(pattern, value) is not None
            except re.error:
                return pattern == value
        if key == "type":
            return value == pattern
        # Generic fallback: try glob, then exact
        return fnmatch.fnmatch(value, pattern)
