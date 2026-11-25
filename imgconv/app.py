from __future__ import annotations

import ctypes
import os
import queue
import threading
import time
from pathlib import Path
from typing import Any

from .config import APP_DISPLAY_NAME, load_config, runtime_dir
from .converter import convert_file
from .formats import is_image_file
from .overlay import ProgressOverlay
from .runtime import InstanceLock, IpcServer

# 资源管理器多选时会为每张图片启动一次进程，这里留出收集窗口合并成同一批。
DEBOUNCE_SECONDS = 0.65
MAX_COLLECT_SECONDS = 2.5
IDLE_EXIT_SECONDS = 2.5
LOG_PATH = runtime_dir() / "conversion.log"
_MESSAGEBOX = ctypes.windll.user32.MessageBoxW


class ConversionService:
    """无界面的转换核心：接收右键菜单传入的文件，批量转换后自行退出。"""

    def __init__(self, lock: InstanceLock, resident: bool):
        self.lock = lock
        self.resident = resident
        self.quitting = False
        self.events: queue.Queue[tuple[Any, ...]] = queue.Queue()

        self.server: IpcServer | None = None
        try:
            self.server = IpcServer(self._on_ipc)
            self.server.start()
        except OSError:
            self.server = None

        self.pending: list[Path] = []
        self.pending_norms: set[str] = set()
        self.seen: set[str] = set()
        self.busy = False
        self.first_pending_at = 0.0
        self.collect_deadline = 0.0
        self.last_activity = time.time()

        self.overlay: ProgressOverlay | None = None
        self.ui_total = 0
        self.ui_done = 0
        self.ui_failed = 0

    # ------------------------------------------------------------------ public
    def run(self, initial_files: list[str] | None = None) -> None:
        if initial_files:
            self._ingest(initial_files)
        try:
            while not self.quitting:
                self._drain_events()
                if self.quitting:
                    break
                if self.pending and not self.busy and time.time() >= self.collect_deadline:
                    self._start_batch()
                if (
                    not self.resident
                    and not self.busy
                    and not self.pending
                    and time.time() - self.last_activity >= IDLE_EXIT_SECONDS
                ):
                    break
                if self.overlay:
                    self.overlay.pump()
                time.sleep(0.02)
        finally:
            if self.overlay:
                self.overlay.close()
            if self.server:
                self.server.stop()

    # ------------------------------------------------------------------- events
    def _on_ipc(self, action: str, files: list[str]) -> None:
        self.events.put((action, files))

    def _drain_events(self) -> None:
        try:
            while True:
                action, payload = self.events.get_nowait()
                if action == "convert":
                    self._ingest(payload)
                elif action == "progress":
                    self.ui_done += int(payload)
                    if self.overlay:
                        self.overlay.progress(self.ui_done, self.ui_total)
                elif action == "done":
                    self._on_batch_done(payload)
                elif action == "quit":
                    self.quitting = True
                    return
                # ping / show 等动作不需要界面，直接忽略。
        except queue.Empty:
            pass

    # ---------------------------------------------------------------- ingestion
    def _ingest(self, raw_paths: list[str]) -> None:
        had_pending = bool(self.pending)
        added = 0
        now = time.time()
        for raw in raw_paths:
            try:
                path = Path(raw).expanduser().resolve()
            except OSError:
                continue
            if not is_image_file(path):
                continue
            norm = os.path.normcase(str(path))
            if norm in self.pending_norms or norm in self.seen:
                continue
            self.pending.append(path)
            self.pending_norms.add(norm)
            self.seen.add(norm)
            added += 1

        if not added:
            return
        self.last_activity = now
        if self.busy:
            # 当前批次不收打断，新文件在下一批继续。
            self.ui_total += added
            if self.overlay:
                self.overlay.progress(self.ui_done, self.ui_total)
            return
        if not had_pending:
            self.ui_total = 0
            self.ui_done = 0
            self.ui_failed = 0
        self.ui_total += added
        self._show_overlay()
        if self.first_pending_at <= 0.0:
            self.first_pending_at = now
        self.collect_deadline = min(
            now + DEBOUNCE_SECONDS,
            self.first_pending_at + MAX_COLLECT_SECONDS,
        )

    def _show_overlay(self) -> None:
        if self.overlay is None:
            try:
                self.overlay = ProgressOverlay()
            except Exception:
                self.overlay = None
                return
        self.overlay.show(self.ui_total)
        self.overlay.progress(self.ui_done, self.ui_total)

    # --------------------------------------------------------------- conversion
    def _start_batch(self) -> None:
        if self.busy or not self.pending:
            return
        batch = self.pending
        self.pending = []
        self.pending_norms.clear()
        self.first_pending_at = 0.0
        self.collect_deadline = 0.0
        self.busy = True
        cfg = load_config()
        threading.Thread(
            target=self._convert_worker,
            args=(batch, cfg),
            daemon=True,
        ).start()

    def _convert_worker(self, batch: list[Path], cfg: dict[str, Any]) -> None:
        errors: list[tuple[Path, str]] = []
        for path in batch:
            try:
                convert_file(
                    path,
                    keep_exif=bool(cfg.get("keep_exif", True)),
                    background=str(cfg.get("background", "#FFFFFF")),
                    overwrite=bool(cfg.get("overwrite", False)),
                )
            except Exception as exc:
                errors.append((path, str(exc)))
                self._append_log(path, str(exc))
            self.events.put(("progress", 1))
        self.events.put(("done", errors))

    def _on_batch_done(self, errors: list[tuple[Path, str]]) -> None:
        self.busy = False
        self.last_activity = time.time()
        self.seen.clear()
        self.ui_failed += len(errors)
        if errors:
            self._notify_failures(errors)
        if self.pending:
            now = time.time()
            self.first_pending_at = now
            self.collect_deadline = min(
                now + DEBOUNCE_SECONDS,
                now + MAX_COLLECT_SECONDS,
            )
            return
        if self.overlay:
            success = self.ui_done - self.ui_failed
            self.overlay.finish(success, self.ui_failed)

    # ------------------------------------------------------------------ helpers
    def _notify_failures(self, errors: list[tuple[Path, str]]) -> None:
        lines = [f"{path.name}：{message}" for path, message in errors[:6]]
        if len(errors) > 6:
            lines.append(f"……其余 {len(errors) - 6} 张见日志")
        text = (
            "以下图片未能转换：\n\n"
            + "\n".join(lines)
            + f"\n\n详细日志：{LOG_PATH}"
        )
        threading.Thread(
            target=lambda: _MESSAGEBOX(
                None, text, f"{APP_DISPLAY_NAME} · 转换失败",
                0x00000010 | 0x00010000,
            ),
            daemon=True,
        ).start()

    def _append_log(self, path: Path, message: str) -> None:
        try:
            LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
            with LOG_PATH.open("a", encoding="utf-8") as handle:
                stamp = time.strftime("%Y-%m-%d %H:%M:%S")
                handle.write(f"[{stamp}] {path}\n  {message}\n")
        except OSError:
            pass


def run_service(lock: InstanceLock, files: list[str] | None,
                resident: bool) -> None:
    ConversionService(lock, resident).run(files)
