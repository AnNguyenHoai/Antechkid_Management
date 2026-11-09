"""Windows console encoding regression for Unicode-heavy recovery stack traces."""
import logging

from centermanager.core.logging import EncodingSafeStreamHandler, RedactingFormatter


class _Cp1252Console:
    def __init__(self):
        self.output = []

    def write(self, message):
        self.output.append(message.encode("cp1252", errors="strict").decode("cp1252"))

    def flush(self):
        pass


def test_unicode_startup_exception_survives_cp1252_console_without_masking():
    console = _Cp1252Console()
    handler = EncodingSafeStreamHandler(console)
    handler.setFormatter(RedactingFormatter("%(levelname)s %(message)s"))
    logger = logging.getLogger("test-rec02-cp1252")
    logger.addHandler(handler)
    logger.setLevel(logging.DEBUG)
    try:
        logger.error("Cannot archive lesson Học về Function, giữ dữ liệu")
        logged = "".join(console.output)
        assert "Cannot archive" in logged
        assert "Unicode" not in logged
        assert "\\u1ecd" in logged or "\\u1ec1" in logged
        assert "Function" in logged
    finally:
        logger.removeHandler(handler)


def test_ascii_log_is_not_escaped_unnecessarily():
    console = _Cp1252Console()
    handler = EncodingSafeStreamHandler(console)
    handler.setFormatter(RedactingFormatter("%(message)s"))
    handler.emit(logging.LogRecord(
        "test", logging.ERROR, __file__, 1, "Backup refused", (), None
    ))
    assert "".join(console.output).strip() == "Backup refused"
