from enum import Enum

class CollaborationMode(Enum):
    READ = "READ"
    WRITE = "WRITE"
    # Future modes: SYNCING, RECOVERY, OFFLINE, MAINTENANCE

class ModeManager:
    def __init__(self):
        self._mode = CollaborationMode.READ

    def current_mode(self) -> CollaborationMode:
        return self._mode

    def set_mode(self, mode: CollaborationMode) -> None:
        self._mode = mode

    def can_edit(self) -> bool:
        return self._mode == CollaborationMode.WRITE

    def can_save(self) -> bool:
        return self._mode == CollaborationMode.WRITE

    def can_delete(self) -> bool:
        return self._mode == CollaborationMode.WRITE

    def can_import(self) -> bool:
        return self._mode == CollaborationMode.WRITE

    def can_export(self) -> bool:
        # Export allowed in both READ and WRITE
        return self._mode in (CollaborationMode.READ, CollaborationMode.WRITE)

    def is_read_mode(self) -> bool:
        return self._mode == CollaborationMode.READ

    def is_write_mode(self) -> bool:
        return self._mode == CollaborationMode.WRITE