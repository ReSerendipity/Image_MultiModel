# SPDX-FileCopyrightText: Copyright (c) 2024-2026 ReSerendipity
# SPDX-License-Identifier: Apache-2.0
"""上传图片魔数（Magic Number）校验模块，对齐 SeedVR2 的 magic_check。

Image_MultiModel 的图片输入以 Base64 传递（无扩展名声明），因此魔数校验的
意义在于：解码后显式验证字节头确为合法图片格式（PNG/JPEG/GIF/BMP/WebP/TIFF），
阻断伪装/非图片数据被当作图片处理。

配合 PIL 的 ``verify()`` 可同时校验图片头部与内容完整性，避免"伪图片头但损坏内容"。

使用方式::

    from app.integrated_app.security.magic_check import validate_image_magic

    is_valid, detected_type, error = validate_image_magic(image_bytes)
    if not is_valid:
        raise HTTPException(status_code=400, detail=error)
"""

# 图片魔数白名单: {魔数前缀: 对应格式名}
_IMG_MAGICS: list[tuple[bytes, str]] = [
    (b"\xff\xd8\xff", "jpeg"),
    (b"\x89PNG\r\n\x1a\n", "png"),
    (b"GIF87a", "gif"),
    (b"GIF89a", "gif"),
    (b"BM", "bmp"),
    (b"II*\x00", "tiff"),  # TIFF little-endian
    (b"MM\x00*", "tiff"),  # TIFF big-endian
]

# 读取的魔数字节数
_MAGIC_READ_SIZE = 16


def _check_webp(header: bytes) -> bool:
    """校验 RIFF 文件是否确实为 WebP（偏移 8-11 字节为 'WEBP'）。"""
    return len(header) >= 12 and header[8:12] == b"WEBP"


def validate_image_magic(content: bytes) -> tuple[bool, str | None, str | None]:
    """校验图片字节内容是否为合法图片格式。

    Args:
        content: 图片二进制内容（至少前 ``_MAGIC_READ_SIZE`` 字节）。

    Returns:
        tuple[bool, str | None, str | None]:
            - is_valid: 校验是否通过
            - detected_type: 检测到的图片格式名（成功时为格式名）
            - error_msg: 校验失败时的错误信息，成功时为 None
    """
    if not content:
        return False, None, "图片内容为空"

    header = content[:_MAGIC_READ_SIZE]
    if len(header) < 4:
        return False, None, "图片数据过短，无法验证魔数签名"

    # WebP 特殊处理：以 RIFF 开头，需检查偏移 8 是否为 WEBP
    if header[:4] == b"RIFF":
        if _check_webp(header):
            return True, "webp", None
        return False, "webp", "检测到 RIFF 容器但非 WebP 格式，图片可能已伪装或损坏"

    for magic, fmt in _IMG_MAGICS:
        if header[: len(magic)] == magic:
            return True, fmt, None

    return (
        False,
        None,
        "无法识别的图片格式（魔数校验失败），该数据可能已伪装或损坏",
    )