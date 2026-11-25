# Copyright (c) 2026 Jon.Shen (Jon.Shen@Foxmail.com)
# 自由复制、修改；禁止商业使用；整合或再分发需注明出处。

from __future__ import annotations

import ctypes
import json
import os
import socket
import threading
import time
from ctypes import wintypes
from typing import Callable

from .config import runtime_dir

MUTEX_NAME = "Local\\ImgConvertToJpg.Background"
ERROR_ALREADY_EXISTS = 183
RUNTIME_FILE = runtime_dir() / "runtime.json"

kernel32 = ctypes.windll.kernel32
kernel32.CreateMutexW.argtypes = [ctypes.c_void_p, wintypes.BOOL, wintypes.LPCWSTR]
kernel32.CreateMutexW.restype = wintypes.HANDLE
kernel32.OpenMutexW.argtypes = [wintypes.DWORD, wintypes.BOOL, wintypes.LPCWSTR]
kernel32.OpenMutexW.restype = wintypes.HANDLE
kernel32.CloseHandle.argtypes = [wintypes.HANDLE]
kernel32.CloseHandle.restype = wintypes.BOOL
kernel32.GetLastError.restype = wintypes.DWORD


def instance_exists() -> bool:
    handle = kernel32.OpenMutexW(0x00100000, False, MUTEX_NAME)
    if handle:
        kernel32.CloseHandle(handle)
        return True
    return False


class InstanceLock:
    def __init__(self) -> None:
        self.handle = kernel32.CreateMutexW(None, False, MUTEX_NAME)
        self.already_running = kernel32.GetLastError() == ERROR_ALREADY_EXISTS

    def release(self) -> None:
        if self.handle:
            kernel32.CloseHandle(self.handle)
            self.handle = None


class IpcServer:
    def __init__(self, handler: Callable[[str, list[str]], None]):
        self.handler = handler
        self.token = os.urandom(16).hex()
        self.port = 0
        self._socket: socket.socket | None = None
        self._stop = threading.Event()
        self._thread: threading.Thread | None = None
        self._rpc_path = RUNTIME_FILE

    def start(self) -> None:
        self._rpc_path.parent.mkdir(parents=True, exist_ok=True)
        server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        server.bind(("127.0.0.1", 0))
        server.listen(32)
        server.settimeout(0.5)
        self._socket = server
        self.port = int(server.getsockname()[1])
        self._write_runtime()
        self._thread = threading.Thread(target=self._accept_loop, daemon=True)
        self._thread.start()

    def _write_runtime(self) -> None:
        payload = {
            "pid": os.getpid(),
            "port": self.port,
            "token": self.token,
        }
        tmp = self._rpc_path.with_suffix(".tmp")
        tmp.write_text(json.dumps(payload), encoding="utf-8")
        os.replace(tmp, self._rpc_path)

    def _accept_loop(self) -> None:
        assert self._socket is not None
        while not self._stop.is_set():
            try:
                conn, _addr = self._socket.accept()
            except socket.timeout:
                continue
            except OSError:
                break
            threading.Thread(target=self._serve, args=(conn,), daemon=True).start()

    def _serve(self, conn: socket.socket) -> None:
        try:
            conn.settimeout(3.0)
            raw = b""
            while b"\n" not in raw and len(raw) < 1024 * 1024:
                chunk = conn.recv(65536)
                if not chunk:
                    break
                raw += chunk
            if not raw:
                return
            request = json.loads(raw.split(b"\n", 1)[0].decode("utf-8"))
            if request.get("token") != self.token:
                conn.sendall(b'{"ok":false,"error":"unauthorized"}\n')
                return
            action = str(request.get("action") or "")
            files = request.get("files") or []
            if not isinstance(files, list):
                files = []
            files = [str(item) for item in files if str(item)]
            self.handler(action, files)
            conn.sendall(b'{"ok":true}\n')
        except Exception:
            try:
                conn.sendall(b'{"ok":false}\n')
            except OSError:
                pass
        finally:
            try:
                conn.close()
            except OSError:
                pass

    def stop(self) -> None:
        self._stop.set()
        if self._socket:
            try:
                self._socket.close()
            except OSError:
                pass
        if self._thread:
            self._thread.join(timeout=1.0)
        try:
            data = json.loads(self._rpc_path.read_text(encoding="utf-8"))
            if int(data.get("pid", -1)) == os.getpid():
                self._rpc_path.unlink(missing_ok=True)
        except (OSError, ValueError):
            pass


def send_request(action: str, files: list[str] | None = None,
                 wait: float = 8.0) -> bool:
    deadline = time.time() + wait
    payload_files = files or []
    while time.time() < deadline:
        try:
            data = json.loads(RUNTIME_FILE.read_text(encoding="utf-8"))
            port = int(data["port"])
            token = str(data["token"])
        except (OSError, ValueError, KeyError):
            time.sleep(0.12)
            continue
        try:
            with socket.create_connection(("127.0.0.1", port), timeout=0.8) as conn:
                conn.settimeout(3.0)
                request = json.dumps(
                    {
                        "token": token,
                        "action": action,
                        "files": payload_files,
                    },
                    ensure_ascii=False,
                ).encode("utf-8") + b"\n"
                conn.sendall(request)
                with conn.makefile("rb") as stream:
                    response = json.loads(stream.readline(4096).decode("utf-8"))
                return bool(response.get("ok"))
        except (OSError, ValueError):
            time.sleep(0.12)
    return False
