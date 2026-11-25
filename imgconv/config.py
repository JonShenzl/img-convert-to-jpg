from __future__ import annotations

import os
import sys
from pathlib import Path
from typing import Any

APP_DISPLAY_NAME = "ImgConvertToJpg"
APP_VERSION = "2.7.5"
APP_DIR_NAME = "ImgConvertToJpg"

# 配置与 exe 同目录，双击 settings.ini 修改后保存即可，无需设置界面。
SETTINGS_FILE = "settings.ini"

# 转换功能固定输出 JPG，并且始终使用 100% 质量、4:4:4 无色度抽样。
OUTPUT_EXT = ".jpg"

DEFAULT_CONFIG: dict[str, Any] = {
    "keep_exif": True,
    "background": "#FFFFFF",
    "overwrite": False,
}

SETTINGS_TEMPLATE = f"""# {APP_DISPLAY_NAME} v{APP_VERSION} 设置（修改后保存，下一次转换自动生效）
# 保留 Exif：1 保留；0 丢弃
KeepExif=1
# 透明图片填充的背景色（#RRGGBB）
Background=#FFFFFF
# 目标 JPG 已存在时：1 直接覆盖（绝不覆盖源图片）；0 自动加序号
Overwrite=0
"""


def app_dir() -> Path:
    if getattr(sys, "frozen", False):
        return Path(sys.executable).resolve().parent
    return Path(__file__).resolve().parent.parent


def config_path() -> Path:
    return app_dir() / SETTINGS_FILE


def runtime_dir() -> Path:
    base = os.environ.get("LOCALAPPDATA") or str(Path.home() / "AppData" / "Local")
    return Path(base) / APP_DIR_NAME


def ensure_config_file() -> bool:
    path = config_path()
    if path.exists():
        return False
    try:
        path.write_text(SETTINGS_TEMPLATE, encoding="utf-8-sig", newline="\r\n")
        return True
    except OSError:
        return False


def _as_bool(value: Any) -> bool:
    return str(value).strip().lower() in {
        "1", "true", "yes", "on", "enable", "enabled", "是", "开启",
    }


def load_config() -> dict[str, Any]:
    cfg = dict(DEFAULT_CONFIG)
    ensure_config_file()
    try:
        text = config_path().read_text(encoding="utf-8-sig")
    except OSError:
        return cfg

    for raw in text.splitlines():
        line = raw.strip()
        if not line or line[0] in "#;[":
            continue
        if "=" not in line:
            continue
        key, _, value = line.partition("=")
        key = key.strip().replace("_", "").replace(" ", "").lower()
        value = value.strip()
        if key == "keepexif":
            cfg["keep_exif"] = _as_bool(value)
        elif key == "background":
            color = value.upper()
            if len(color) == 7 and color.startswith("#"):
                cfg["background"] = color
        elif key == "overwrite":
            cfg["overwrite"] = _as_bool(value)

    return cfg
