"""Regression for Unicode-safe Windows console output on the stable baseline."""
import io
import logging

from centermanager.core.logging import EncodingSafeStreamHandler


class Cp1252Stream:
    def __init__(self):
        self.buffer = io.BytesIO()

    def write(self, text):
        self.buffer.write(text.encode("cp1252"))

    def flush(self):
        pass

    def getvalue(self):
        return self.buffer.getvalue().decode("cp1252")


def test_windows_console_escapes_unencodable_unicode():
    stream = Cp1252Stream()
    handler = EncodingSafeStreamHandler(stream)
    handler.setFormatter(logging.Formatter("%(message)s"))
    record = logging.makeLogRecord({
        "name": "center", "levelno": logging.INFO,
        "levelname": "INFO", "msg": "Kiểm tra học phí ✅", "args": (),
    })
    handler.emit(record)
    assert "Ki" in stream.getvalue()
    assert r"\u" in stream.getvalue()


def test_ascii_console_is_not_modified():
    stream = Cp1252Stream()
    handler = EncodingSafeStreamHandler(stream)
    record = logging.makeLogRecord({
        "name": "center", "levelno": logging.INFO,
        "levelname": "INFO", "msg": "Git MAIN ready", "args": (),
    })
    handler.emit(record)
    assert stream.getvalue() == "Git MAIN ready\n"
