# Copyright (c) 2026 Jon.Shen (Jon.Shen@Foxmail.com)
# 自由复制、修改；禁止商业使用；整合或再分发需注明出处。

from __future__ import annotations

from functools import lru_cache
from pathlib import Path

from PIL import Image

# 兜底列表：即使 Pillow 插件枚举失败，也保证常见图片格式可用。
FALLBACK_EXTENSIONS = [
    ".jpg", ".jpeg", ".jpe", ".jfif", ".jif", ".png", ".apng",
    ".webp", ".bmp", ".dib", ".gif", ".tif", ".tiff", ".ico",
    ".cur", ".icns", ".tga", ".pcx", ".ppm", ".pgm", ".pbm",
    ".pnm", ".psd", ".jp2", ".j2k", ".jpc", ".jpx", ".dds", ".qoi",
]

# Pillow 能打开但并不是图片的文档/科学数据格式，注册右键会造成误判。
NON_IMAGE_EXTENSIONS = {
    ".pdf", ".ps", ".eps", ".h5", ".hdf",
    ".grib", ".bufr", ".mpeg", ".mpg",
}


@lru_cache(maxsize=1)
def image_extensions() -> tuple[str, ...]:
    """返回当前环境能转换的全部图片扩展名（含 Windows 已安装的 Pillow 插件）。"""
    exts: set[str] = set()
    try:
        Image.init()
        exts = {str(ext).lower() for ext in Image.registered_extensions()}
    except Exception:
        exts = set()
    if not exts:
        exts = set(FALLBACK_EXTENSIONS)
    return tuple(sorted(exts - NON_IMAGE_EXTENSIONS))


def is_image_file(path: str | Path) -> bool:
    """判断文件是否为可转换图片；未知扩展名时尝试读取文件头。"""
    file_path = Path(path)
    if not file_path.is_file():
        return False
    if file_path.suffix.lower() in image_extensions():
        return True
    try:
        with Image.open(file_path) as image:
            image.verify()
        return True
    except Exception:
        return False
