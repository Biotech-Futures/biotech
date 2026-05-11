from __future__ import annotations

from pathlib import Path

from rest_framework import serializers


def _normalized_extensions(values) -> set[str]:
    return {
        str(value).strip().lower().lstrip(".")
        for value in (values or [])
        if str(value).strip()
    }


def _normalized_mime_types(values) -> set[str]:
    return {
        str(value).strip().lower()
        for value in (values or [])
        if str(value).strip()
    }


def _format_bytes(size: int) -> str:
    if size >= 1024 * 1024:
        return f"{size // (1024 * 1024)} MB"
    if size >= 1024:
        return f"{size // 1024} KB"
    return f"{size} bytes"


# Filename segments that must never appear anywhere in the dotted name, not
# just the trailing suffix. Catches the `invoice.exe.pdf` shape where the
# real type is the inner segment and the trailing one is cosmetic.
_DANGEROUS_INNER_EXTENSIONS = frozenset({
    "exe", "dll", "so", "dylib", "bat", "cmd", "com", "scr", "msi",
    "ps1", "vbs", "vbe", "sh", "jar", "msp", "mst", "cpl", "lnk",
    "reg", "hta", "jse", "wsf", "wsh", "app",
})

# Magic-byte prefixes for native executables. We refuse any upload whose
# content starts with one of these regardless of the declared MIME or the
# trailing extension — there is no benign reason to ship these through a
# resource/chat attachment endpoint.
_EXECUTABLE_MAGIC_PREFIXES: tuple[bytes, ...] = (
    b"MZ",                  # DOS/Windows PE (.exe, .dll, .sys)
    b"\x7fELF",             # Linux/BSD/Android ELF
    b"\xfe\xed\xfa\xce",    # Mach-O 32-bit BE
    b"\xfe\xed\xfa\xcf",    # Mach-O 64-bit BE
    b"\xce\xfa\xed\xfe",    # Mach-O 32-bit LE
    b"\xcf\xfa\xed\xfe",    # Mach-O 64-bit LE
    b"\xca\xfe\xba\xbe",    # Java class / Mach-O fat
    b"dex\n",               # Android DEX
)


def _has_executable_signature(uploaded_file) -> bool:
    read = getattr(uploaded_file, "read", None)
    seek = getattr(uploaded_file, "seek", None)
    if read is None or seek is None:
        return False
    try:
        seek(0)
        head = read(8)
    except Exception:
        return False
    finally:
        try:
            seek(0)
        except Exception:
            pass
    if not head:
        return False
    return any(head.startswith(prefix) for prefix in _EXECUTABLE_MAGIC_PREFIXES)


def validate_uploaded_file(
    uploaded_file,
    *,
    max_size: int,
    allowed_extensions,
    allowed_mime_types,
    field_label: str,
):
    if uploaded_file is None:
        return uploaded_file

    file_size = getattr(uploaded_file, "size", None)
    if file_size is not None and file_size > max_size:
        raise serializers.ValidationError(
            f"{field_label} exceeds the maximum allowed size of {_format_bytes(max_size)}."
        )

    name = getattr(uploaded_file, "name", "") or ""
    suffixes = [s.lower().lstrip(".") for s in Path(name).suffixes]
    extension = suffixes[-1] if suffixes else ""
    inner_segments = suffixes[:-1]

    normalized_extensions = _normalized_extensions(allowed_extensions)
    if not extension or extension not in normalized_extensions:
        raise serializers.ValidationError(
            f"{field_label} must use an allowed file extension."
        )

    if any(seg in _DANGEROUS_INNER_EXTENSIONS for seg in inner_segments):
        raise serializers.ValidationError(
            f"{field_label} filename contains a disallowed extension."
        )

    content_type = (getattr(uploaded_file, "content_type", "") or "").strip().lower()
    normalized_mime_types = _normalized_mime_types(allowed_mime_types)
    if not content_type or content_type not in normalized_mime_types:
        raise serializers.ValidationError(
            f"{field_label} must use an allowed content type."
        )

    if _has_executable_signature(uploaded_file):
        raise serializers.ValidationError(
            f"{field_label} content matches an executable signature."
        )

    return uploaded_file
