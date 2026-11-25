# Copyright (c) 2026 Jon.Shen (Jon.Shen@Foxmail.com)
# 自由复制、修改；禁止商业使用；整合或再分发需注明出处。

from __future__ import annotations

import os
from pathlib import Path
from typing import Any

from PIL import Image, ImageColor, ImageOps

from .config import OUTPUT_EXT


class ConversionError(Exception):
    pass


def _unique_path(candidate: Path) -> Path:
    if not candidate.exists():
        return candidate
    for index in range(1, 10000):
        test = candidate.with_name(f"{candidate.stem} ({index}){candidate.suffix}")
        if not test.exists():
            return test
    raise ConversionError("同名文件过多，无法生成新文件名")


def _output_path(src: Path, overwrite: bool) -> Path:
    candidate = src.with_name(src.stem + OUTPUT_EXT)
    try:
        same_as_source = (
            os.path.normcase(str(candidate.resolve()))
            == os.path.normcase(str(src.resolve()))
        )
    except OSError:
        same_as_source = False
    # 源文件本身就是同名 JPG 时绝不覆盖原图。
    if same_as_source or not overwrite:
        return _unique_path(candidate)
    return candidate


def convert_file(src: str | Path, keep_exif: bool = True,
                 background: str = "#FFFFFF", overwrite: bool = False) -> Path:
    """把图片转换为 100% 质量 JPG，输出到原图所在文件夹。"""
    src_path = Path(src)
    if not src_path.is_file():
        raise ConversionError("文件不存在")
    out_path = _output_path(src_path, overwrite)
    bg = _parse_color(background)

    try:
        with Image.open(src_path) as source:
            source.load()
            if int(getattr(source, "n_frames", 1)) > 1:
                # JPG 不支持动画，统一转换首帧。
                source.seek(0)
            image = _prepare_static(source, bg)

            save_kwargs: dict[str, Any] = {
                "quality": 100,
                "subsampling": 0,
                "optimize": True,
            }
            if keep_exif:
                exif = image.info.get("exif")
                if exif:
                    save_kwargs["exif"] = exif
            icc = image.info.get("icc_profile") or source.info.get("icc_profile")
            if icc:
                save_kwargs["icc_profile"] = icc

            _save_jpeg(image, out_path, save_kwargs)
    except ConversionError:
        raise
    except PermissionError as exc:
        raise ConversionError(f"没有写入权限：{exc}") from exc
    except Exception as exc:
        raise ConversionError(f"转换失败：{exc}") from exc

    return out_path


def _prepare_static(source: Image.Image, bg: tuple[int, int, int]) -> Image.Image:
    image = source
    if not getattr(source, "is_animated", False):
        try:
            image = ImageOps.exif_transpose(source)
        except Exception:
            image = source
    return _flatten(image, bg)


def _has_alpha(image: Image.Image) -> bool:
    return image.mode in ("RGBA", "LA", "PA") or (
        image.mode == "P" and "transparency" in image.info
    ) or "transparency" in image.info


def _flatten(image: Image.Image, bg: tuple[int, int, int]) -> Image.Image:
    if _has_alpha(image):
        rgba = image.convert("RGBA")
        canvas = Image.new("RGB", rgba.size, bg)
        canvas.paste(rgba, mask=rgba.getchannel("A"))
        return canvas
    if image.mode != "RGB":
        return image.convert("RGB")
    return image


def _save_jpeg(image: Image.Image, out_path: Path,
               save_kwargs: dict[str, Any]) -> None:
    kwargs = dict(save_kwargs)
    try:
        image.save(out_path, format="JPEG", **kwargs)
        return
    except TypeError:
        # 某些 Pillow 版本不接受 EXIF/ICC 参数，去掉可选参数后重试。
        for key in ("exif", "icc_profile"):
            kwargs.pop(key, None)
        image.save(out_path, format="JPEG", **kwargs)


def _parse_color(value: str) -> tuple[int, int, int]:
    try:
        rgb = ImageColor.getrgb((value or "#FFFFFF").strip())
        return int(rgb[0]), int(rgb[1]), int(rgb[2])
    except Exception:
        return 255, 255, 255
