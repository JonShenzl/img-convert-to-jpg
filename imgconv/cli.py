# Copyright (c) 2026 Jon.Shen (Jon.Shen@Foxmail.com)
# 自由复制、修改；禁止商业使用；整合或再分发需注明出处。

from __future__ import annotations

import argparse
import ctypes
import time

from .app import run_service
from .config import APP_DISPLAY_NAME, APP_VERSION, ensure_config_file
from .runtime import InstanceLock, instance_exists, send_request

_MESSAGEBOX = ctypes.windll.user32.MessageBoxW

USAGE_TEXT = f"""{APP_DISPLAY_NAME} v{APP_VERSION}（无界面转换核心）

使用：在图片上右键 →「显示更多选项」→「转换为 JPG」，可一次多选。
输出：与原图同一文件夹，100% 质量 JPG。

注册：双击同目录的 注册.reg
卸载：双击同目录的 卸载.reg
设置：编辑同目录 settings.ini（保留 Exif、透明底色、同名覆盖）"""


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="ImageConverter",
        description=f"{APP_DISPLAY_NAME} {APP_VERSION}",
    )
    parser.add_argument("--convert", nargs="+", metavar="FILE",
                        help="转换指定图片（由右键菜单调用）")
    parser.add_argument("--background", action="store_true",
                        help="常驻后台，等待右键菜单发来的转换请求")
    parser.add_argument("--quit", action="store_true", help="退出常驻后台实例")
    parser.add_argument("--version", action="store_true", help="显示版本")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    ensure_config_file()

    if args.version:
        print(f"{APP_DISPLAY_NAME} {APP_VERSION}")
        return 0

    if args.quit:
        return 0 if instance_exists() and send_request("quit", wait=3.0) else 1

    if args.convert:
        return _route_convert(args.convert)

    if args.background:
        return _run_background()

    if instance_exists():
        return 0
    _MESSAGEBOX(None, USAGE_TEXT, f"{APP_DISPLAY_NAME} v{APP_VERSION}", 0x00000040)
    return 0


def _run_background() -> int:
    if instance_exists():
        return 0
    lock = InstanceLock()
    if lock.already_running:
        lock.release()
        return 0
    try:
        run_service(lock, None, resident=True)
    finally:
        lock.release()
    return 0


def _route_convert(files: list[str]) -> int:
    # 已有实例时把文件交给它，由它合并同一批多选文件后统一转换。
    if instance_exists() and send_request("convert", files, wait=6.0):
        return 0

    lock = InstanceLock()
    if lock.already_running:
        lock.release()
        if send_request("convert", files, wait=6.0):
            return 0
        time.sleep(0.3)
        if send_request("convert", files, wait=6.0):
            return 0
        return 1

    try:
        run_service(lock, files, resident=False)
    finally:
        lock.release()
    return 0
