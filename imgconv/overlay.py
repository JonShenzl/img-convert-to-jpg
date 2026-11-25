# Copyright (c) 2026 Jon.Shen (Jon.Shen@Foxmail.com)
# 自由复制、修改；禁止商业使用；整合或再分发需注明出处。

from __future__ import annotations

import tkinter as tk
from typing import Callable

KEY = "#010203"
TEXT = "#F8FAFC"
MUTED = "#E2E8F0"
ACCENT = "#3B82F6"
GREEN = "#10B981"
RED = "#EF4444"


class ConversionOverlay:
    WIDTH = 300
    HEIGHT = 300
    CENTER_X = 150
    CENTER_Y = 128

    def __init__(self, root: tk.Misc) -> None:
        self.root = root
        self.window = tk.Toplevel(root)
        self.window.overrideredirect(True)
        self.window.configure(bg=KEY, bd=0, highlightthickness=0)
        self.window.attributes("-topmost", True)
        try:
            self.window.attributes("-transparentcolor", KEY)
        except tk.TclError:
            pass
        self.window.withdraw()

        self.canvas = tk.Canvas(
            self.window, width=self.WIDTH, height=self.HEIGHT,
            bg=KEY, highlightthickness=0, bd=0,
        )
        self.canvas.pack(fill="both", expand=True)
        self.canvas.bind("<Button-1>", self._on_click)

        self._angle = 0
        self._running = False
        self._after_id = None
        self._close_callback = None
        self._closed = False
        self._state = "work"
        self._done = 0
        self._total = 0
        self._target = ""
        self._close_box = None

    def show(self, target_label: str, count: int = 0) -> None:
        if self._closed:
            return
        self.window.deiconify()
        self.window.lift()
        self.window.attributes("-topmost", True)
        self._position()
        self._target = target_label
        self._done = 0
        self._total = count
        self._state = "work"
        self._close_box = None
        self._angle = 0
        if not self._running:
            self._running = True
            self._draw_working()
            self._animate()

    def update_progress(self, done: int, total: int) -> None:
        if self._closed:
            return
        self._done = done
        self._total = total
        if self._state == "work":
            self._draw_working()

    def set_stage(self, total: int, target_label: str) -> None:
        if self._closed:
            return
        self._total = total
        self._target = target_label
        if self._state == "work":
            self._draw_working()

    def success(self, ok: int, failed: int, on_closed: Callable[[], None]) -> None:
        if self._closed:
            on_closed()
            return
        self._running = False
        self._cancel_animation()
        self._state = "success"
        self._close_callback = on_closed
        self._draw_success(ok, failed)
        self.window.after(1100, self._auto_close)

    def error(self, message: str, on_closed: Callable[[], None] | None = None) -> None:
        if self._closed:
            if on_closed:
                on_closed()
            return
        self._running = False
        self._cancel_animation()
        self._state = "error"
        self._close_callback = on_closed
        self._draw_error(message)

    def close(self) -> None:
        if self._closed:
            return
        self._closed = True
        self._running = False
        self._cancel_animation()
        try:
            self.window.destroy()
        except tk.TclError:
            pass

    def _position(self) -> None:
        screen_w = self.window.winfo_screenwidth()
        screen_h = self.window.winfo_screenheight()
        x = max(0, (screen_w - self.WIDTH) // 2)
        y = max(0, (screen_h - self.HEIGHT) // 2 - 20)
        self.window.geometry(f"{self.WIDTH}x{self.HEIGHT}+{x}+{y}")

    def _cancel_animation(self) -> None:
        if self._after_id:
            try:
                self.window.after_cancel(self._after_id)
            except tk.TclError:
                pass
            self._after_id = None

    def _auto_close(self) -> None:
        if self._closed:
            return
        callback = self._close_callback
        self.close()
        if callback:
            callback()

    def _on_click(self, event: tk.Event) -> None:
        if self._state != "error" or not self._close_box:
            return
        x1, y1, x2, y2 = self._close_box
        if x1 <= event.x <= x2 and y1 <= event.y <= y2:
            callback = self._close_callback
            self.close()
            if callback:
                callback()

    def _animate(self) -> None:
        if not self._running or self._closed:
            return
        self._angle = (self._angle + 9) % 360
        self._draw_working()
        self._after_id = self.window.after(33, self._animate)

    def _shadow_text(self, x: float, y: float, text: str,
                     fill: str, font: tuple, **kwargs) -> None:
        for dx, dy in ((-1, -1), (0, -1), (1, -1), (-1, 0),
                       (1, 0), (-1, 1), (0, 1), (1, 1)):
            self.canvas.create_text(
                x + dx, y + dy, text=text, fill="#000000", font=font,
                **kwargs,
            )
        self.canvas.create_text(x, y, text=text, fill=fill, font=font,
                                **kwargs)

    def _draw_working(self) -> None:
        self.canvas.delete("all")
        self._draw_spinner()
        self._shadow_text(
            self.CENTER_X, 214, "正在转换", TEXT,
            ("Microsoft YaHei UI", 12, "bold"),
        )
        self._shadow_text(
            self.CENTER_X, 232, self._count_text(), MUTED,
            ("Microsoft YaHei UI", 7),
        )

    def _draw_success(self, ok: int, failed: int) -> None:
        self.canvas.delete("all")
        cx, cy = self.CENTER_X, 104
        self.canvas.create_oval(
            cx - 46, cy - 46, cx + 46, cy + 46,
            outline=GREEN, width=3,
        )
        self.canvas.create_line(
            cx - 22, cy + 1, cx - 5, cy + 18,
            fill=GREEN, width=6, capstyle="round",
        )
        self.canvas.create_line(
            cx - 5, cy + 18, cx + 25, cy - 17,
            fill=GREEN, width=6, capstyle="round",
        )
        self._shadow_text(
            self.CENTER_X, 176, "转换完成", GREEN,
            ("Microsoft YaHei UI", 13, "bold"),
        )
        detail = f"成功 {ok} 张" + (f" · 失败 {failed} 张" if failed else "")
        self._shadow_text(
            self.CENTER_X, 196, detail, TEXT,
            ("Microsoft YaHei UI", 8),
        )
        self._shadow_text(
            self.CENTER_X, 214, "输出文件已保存在原文件夹", MUTED,
            ("Microsoft YaHei UI", 7),
        )

    def _draw_error(self, message: str) -> None:
        self.canvas.delete("all")
        cx, cy = self.CENTER_X, 102
        self.canvas.create_oval(
            cx - 38, cy - 38, cx + 38, cy + 38,
            outline=RED, width=3,
        )
        self.canvas.create_line(
            cx - 15, cy - 15, cx + 15, cy + 15,
            fill=RED, width=6, capstyle="round",
        )
        self.canvas.create_line(
            cx + 15, cy - 15, cx - 15, cy + 15,
            fill=RED, width=6, capstyle="round",
        )
        self._shadow_text(
            self.CENTER_X, 164, "转换失败", RED,
            ("Microsoft YaHei UI", 13, "bold"),
        )
        self._shadow_text(
            self.CENTER_X, 184, message[:160], "#FCA5A5",
            ("Microsoft YaHei UI", 7), width=200, justify="center",
        )

        x1, y1, x2, y2 = 120, 212, 180, 236
        self._close_box = (x1, y1, x2, y2)
        self._round_rect(x1, y1, x2, y2, 12, "#1E293B")
        self.canvas.create_text(
            (x1 + x2) / 2, (y1 + y2) / 2, text="关闭",
            fill="#E2E8F0", font=("Microsoft YaHei UI", 8),
        )

    def _round_rect(self, x1: float, y1: float, x2: float, y2: float,
                    radius: float, fill: str) -> None:
        r = radius
        self.canvas.create_oval(
            x1, y1, x1 + 2 * r, y1 + 2 * r, fill=fill, outline="",
        )
        self.canvas.create_oval(
            x2 - 2 * r, y1, x2, y1 + 2 * r, fill=fill, outline="",
        )
        self.canvas.create_oval(
            x1, y2 - 2 * r, x1 + 2 * r, y2, fill=fill, outline="",
        )
        self.canvas.create_oval(
            x2 - 2 * r, y2 - 2 * r, x2, y2, fill=fill, outline="",
        )
        self.canvas.create_rectangle(
            x1 + r, y1, x2 - r, y2, fill=fill, outline="",
        )
        self.canvas.create_rectangle(
            x1, y1 + r, x2, y2 - r, fill=fill, outline="",
        )

    def _draw_spinner(self) -> None:
        cx, cy, radius = self.CENTER_X, 116, 64
        self.canvas.create_oval(
            cx - radius, cy - radius, cx + radius, cy + radius,
            outline="#475569", width=6,
        )
        start = -self._angle
        for offset, extent, color in (
            (0, 110, ACCENT),
            (118, 52, "#60A5FA"),
            (178, 18, "#93C5FD"),
        ):
            self.canvas.create_arc(
                cx - radius, cy - radius, cx + radius, cy + radius,
                start=(start + offset) % 360, extent=extent,
                style="arc", outline=color, width=5,
            )
        self._shadow_text(
            cx, cy - 5, self._target or "准备转换", TEXT,
            ("Microsoft YaHei UI", 9, "bold"),
        )
        self._shadow_text(
            cx, cy + 12, "请稍候", MUTED,
            ("Microsoft YaHei UI", 7),
        )

    def _count_text(self) -> str:
        if self._total <= 0:
            return "正在收集图片…"
        return f"{self._done} / {self._total}"


class ProgressOverlay:
    """为无主窗口的转换核心提供隐藏 Tk 根窗口，复用旧版提示。"""

    def __init__(self) -> None:
        self.root = tk.Tk()
        self.root.withdraw()
        self.inner = ConversionOverlay(self.root)

    def show(self, total: int) -> None:
        if self.inner._closed:
            self.inner = ConversionOverlay(self.root)
        label = f"共 {total} 张图片" if total > 1 else ""
        self.inner.show(label, total)

    def progress(self, done: int, total: int) -> None:
        self.inner.update_progress(done, total)

    def finish(self, success: int, failed: int) -> None:
        self.inner.success(success, failed, lambda: None)

    def pump(self) -> None:
        try:
            self.root.update()
        except tk.TclError:
            pass

    def close(self) -> None:
        self.inner.close()
        try:
            self.root.destroy()
        except tk.TclError:
            pass
