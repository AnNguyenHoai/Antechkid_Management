# -*- coding: utf-8 -*-
"""AtomicFileWriter - Atomic file write with temp file and rename."""

import os
import json
import tempfile
from pathlib import Path
from typing import Optional, Callable, Any

from .exceptions import AtomicWriteError
import logging
logger = logging.getLogger(__name__)


class AtomicFileWriter:
    """Atomically write data to a file using temp file + rename."""

    def __init__(self, path: Path):
        self._path = path

    def write(self, data: Any, serializer: Optional[Callable[[Any], str]] = None) -> None:
        """
        Atomically write data to file.
        If serializer is None, data must be str.
        """
        # Ensure parent exists
        self._path.parent.mkdir(parents=True, exist_ok=True)

        # Create temp file in same directory
        temp_fd = None
        temp_path = None
        try:
            temp_fd, temp_path = tempfile.mkstemp(
                dir=self._path.parent,
                prefix=f".{self._path.name}.",
                suffix=".tmp",
            )

            # Write data
            with os.fdopen(temp_fd, 'w', encoding='utf-8') as f:
                if serializer is not None:
                    content = serializer(data)
                elif isinstance(data, str):
                    content = data
                elif isinstance(data, dict):
                    content = json.dumps(data, indent=2, ensure_ascii=False)
                else:
                    content = str(data)

                f.write(content)
                f.flush()
                os.fsync(f.fileno())

            # Atomic rename
            os.replace(temp_path, self._path)

        except Exception as e:
            # Cleanup temp file on error
            if temp_path and temp_path.exists():
                try:
                    temp_path.unlink()
                except Exception:
                    pass
            raise AtomicWriteError(f"Atomic write failed: {e}")

    def write_json(self, data: dict) -> None:
        """Convenience method to write JSON data."""
        self.write(data, lambda d: json.dumps(d, indent=2, ensure_ascii=False))