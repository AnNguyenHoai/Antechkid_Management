# -*- coding: utf-8 -*-
"""Windows named-pipe transport for the protected-data broker.

Security properties:
- local clients only (PIPE_REJECT_REMOTE_CLIENTS);
- authenticated Windows users may connect to the pipe but receive only the
  operation-oriented protocol, never raw SQL/key material;
- server impersonates the pipe client to obtain a trustworthy Windows SID;
- bounded one-message request/response framing.
"""
from __future__ import annotations

import logging
import os
from dataclasses import dataclass

from .broker import (
    MAX_REQUEST_BYTES,
    CallerIdentity,
    ProtectedDataBroker,
    ProtectedDataBrokerError,
    ProtectedDataProtocolError,
    decode_request,
    encode_response,
)
from .protocol import SERVICE_PIPE_NAME

logger = logging.getLogger(__name__)


class ProtectedDataTransportUnavailable(RuntimeError):
    pass


def _load_win32():
    if os.name != "nt":
        raise ProtectedDataTransportUnavailable("Named-pipe broker is Windows-only.")
    try:
        import pywintypes  # type: ignore
        import win32api  # type: ignore
        import win32con  # type: ignore
        import win32file  # type: ignore
        import win32pipe  # type: ignore
        import win32security  # type: ignore
    except ImportError as exc:
        raise ProtectedDataTransportUnavailable("pywin32 is required for named-pipe IPC.") from exc
    return pywintypes, win32api, win32con, win32file, win32pipe, win32security


def _pipe_security_attributes():
    pywintypes, _, _, _, _, win32security = _load_win32()
    sddl = "D:P(A;;GA;;;SY)(A;;GA;;;BA)(A;;GRGW;;;AU)"
    descriptor = win32security.ConvertStringSecurityDescriptorToSecurityDescriptor(
        sddl, win32security.SDDL_REVISION_1
    )
    attributes = pywintypes.SECURITY_ATTRIBUTES()
    attributes.SECURITY_DESCRIPTOR = descriptor
    return attributes


def _caller_identity(pipe_handle) -> CallerIdentity:
    _, win32api, win32con, _, win32pipe, win32security = _load_win32()
    win32pipe.ImpersonateNamedPipeClient(pipe_handle)
    try:
        token = win32security.OpenThreadToken(
            win32api.GetCurrentThread(), win32con.TOKEN_QUERY, True
        )
        try:
            sid = win32security.GetTokenInformation(token, win32security.TokenUser)[0]
            sid_text = win32security.ConvertSidToStringSid(sid)
            try:
                account, domain, _ = win32security.LookupAccountSid(None, sid)
                account_text = f"{domain}\\{account}" if domain else account
            except Exception:
                account_text = ""
            return CallerIdentity(sid=sid_text, account=account_text)
        finally:
            token.Close()
    finally:
        win32security.RevertToSelf()


def _create_server_pipe():
    _, _, _, _, win32pipe, _ = _load_win32()
    reject_remote = getattr(win32pipe, "PIPE_REJECT_REMOTE_CLIENTS", 0x00000008)
    return win32pipe.CreateNamedPipe(
        SERVICE_PIPE_NAME,
        win32pipe.PIPE_ACCESS_DUPLEX,
        win32pipe.PIPE_TYPE_MESSAGE
        | win32pipe.PIPE_READMODE_MESSAGE
        | win32pipe.PIPE_WAIT
        | reject_remote,
        win32pipe.PIPE_UNLIMITED_INSTANCES,
        64 * 1024,
        64 * 1024,
        5000,
        _pipe_security_attributes(),
    )


def wake_pipe_server() -> None:
    """Best-effort local connection used to release a blocking service stop."""
    try:
        _, _, _, win32file, _, _ = _load_win32()
        handle = win32file.CreateFile(
            SERVICE_PIPE_NAME,
            win32file.GENERIC_READ | win32file.GENERIC_WRITE,
            0,
            None,
            win32file.OPEN_EXISTING,
            0,
            None,
        )
        handle.Close()
    except Exception:
        pass


@dataclass
class NamedPipeBrokerServer:
    broker: ProtectedDataBroker

    def serve_until(self, stop_requested) -> None:
        _, _, _, win32file, win32pipe, _ = _load_win32()
        while not stop_requested():
            pipe = _create_server_pipe()
            connected = False
            try:
                try:
                    win32pipe.ConnectNamedPipe(pipe, None)
                    connected = True
                except Exception as exc:
                    if getattr(exc, "winerror", None) != 535:  # ERROR_PIPE_CONNECTED
                        raise
                    connected = True
                if stop_requested():
                    break
                request_id = "unknown"
                caller = CallerIdentity(sid="", account="")
                operation = "unknown"
                try:
                    _, raw = win32file.ReadFile(pipe, MAX_REQUEST_BYTES)
                    request = decode_request(bytes(raw))
                    request_id = request.request_id
                    operation = request.operation.value
                    caller = _caller_identity(pipe)
                    logger.info(
                        "Protected-data request id=%s operation=%s caller_sid=%s caller=%s",
                        request_id,
                        operation,
                        caller.sid,
                        caller.account or "unknown",
                    )
                    result = self.broker.dispatch(request, caller)
                    response = encode_response(request_id, result=result)
                    logger.info(
                        "Protected-data success id=%s operation=%s caller_sid=%s",
                        request_id,
                        operation,
                        caller.sid,
                    )
                except (ProtectedDataProtocolError, ProtectedDataBrokerError) as exc:
                    logger.warning(
                        "Protected-data rejected id=%s operation=%s caller_sid=%s error=%s",
                        request_id,
                        operation,
                        caller.sid or "unknown",
                        str(exc),
                    )
                    response = encode_response(request_id, error=str(exc))
                except Exception:
                    logger.exception(
                        "Protected-data failure id=%s operation=%s caller_sid=%s",
                        request_id,
                        operation,
                        caller.sid or "unknown",
                    )
                    response = encode_response(request_id, error="Protected data operation failed.")
                win32file.WriteFile(pipe, response)
                win32file.FlushFileBuffers(pipe)
            finally:
                if connected:
                    try:
                        win32pipe.DisconnectNamedPipe(pipe)
                    except Exception:
                        pass
                win32file.CloseHandle(pipe)
