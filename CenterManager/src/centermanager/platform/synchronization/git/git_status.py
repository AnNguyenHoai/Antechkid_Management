# -*- coding: utf-8 -*-
from enum import Enum

class GitStatus(Enum):
    CONNECTED = "connected"
    OFFLINE = "offline"
    SYNCING = "syncing"
    PUBLISHING = "publishing"
    ERROR = "error"

    def __str__(self):
        return self.value