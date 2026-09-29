"""Line writer for managing indented output."""

from typing import List, Tuple

from .constants import LIST_ITEM_PREFIX
from .types import Depth


class LineWriter:
    """Manages indented text output."""

    def __init__(self, indent_size: int) -> None:
        """Initialize the line writer.

        Args:
            indent_size: Number of spaces per indentation level
        """
        self._lines: List[Tuple[Depth, str]] = []
        self._indentation_string = " " * indent_size

    def push(self, depth: Depth, content: str) -> None:
        """Add a line at the given depth.

        Args:
            depth: Indentation depth level
            content: Content to add
        """
        self._lines.append((depth, content))

    def mark(self) -> int:
        """Return a position marker for the next line to be pushed."""
        return len(self._lines)

    def hoist_to_list_item(self, marker: int, depth: Depth) -> None:
        """Move the line at ``marker`` onto a list-item hyphen line at ``depth``.

        Used for the first field of a list-item object (spec §10), which is encoded
        one level deeper and then carried on the hyphen line.
        """
        _, content = self._lines[marker]
        self._lines[marker] = (depth, f"{LIST_ITEM_PREFIX}{content}")

    def to_string(self) -> str:
        """Return all lines joined with LF, without a trailing newline.

        Returns:
            Complete output string
        """
        return "\n".join(
            f"{self._indentation_string * depth}{content}" for depth, content in self._lines
        )
