"""Compatibility entry point; E1A arbitration is owned by CollaborationManager.

Do not reinstall the former lease-only wrapper: grace, FIFO waiting and unknown
queue acknowledgements are all legitimate visible pending request states.
"""


def install_false_waiting_guard(manager_cls) -> None:
    """Legacy import compatibility. The canonical manager requires no wrapper."""
    return None
