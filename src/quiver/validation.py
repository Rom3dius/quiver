"""Shared validation constants and helpers for web and bot layers.

Discord API limits (as of 2024):
  - Embed description: 4096 chars
  - Embed field value: 1024 chars
  - Embed footer text: 2048 chars
  - Total embed size: 6000 chars
  - Message content: 2000 chars (non-Nitro)
  - File upload: 25 MB (default, non-boosted server)
  - Modal TextInput max_length: 4000 chars

We set application limits slightly below Discord's hard caps to leave room
for formatting, prefixes, and truncation indicators.
"""

from __future__ import annotations

# --- Text field limits ---

# Inject content — rendered as embed description (Discord max 4096)
MAX_INJECT_CONTENT = 4000

# Operator name — rendered in embed footer
MAX_OPERATOR_NAME = 50

# Intel request content — rendered as embed description (Discord max 4096)
MAX_REQUEST_CONTENT = 4000

# Response text on request resolution — rendered as embed field value (Discord max 1024)
MAX_RESPONSE_TEXT = 1000

# Inter-team message content — rendered as embed description (Discord max 4096)
MAX_MESSAGE_CONTENT = 4000

# --- File upload limits ---

# Per-file size limit.  Discord's default upload cap for non-boosted servers
# is 25 MB, but most wargame attachments are documents/images well under 10 MB.
MAX_FILE_SIZE_BYTES = 10 * 1024 * 1024  # 10 MB

# Total request size (Flask MAX_CONTENT_LENGTH).  Allows a few files per request.
MAX_REQUEST_SIZE_BYTES = 30 * 1024 * 1024  # 30 MB

# Allowed file extensions (lowercase, with leading dot)
ALLOWED_EXTENSIONS: frozenset[str] = frozenset(
    {
        ".pdf",
        ".txt",
        ".csv",
        ".doc",
        ".docx",
        ".xlsx",
        ".xls",
        ".png",
        ".jpg",
        ".jpeg",
        ".gif",
        ".bmp",
        ".webp",
    }
)

# Mapping of extensions to expected MIME type prefixes for validation.
# We check that the client-supplied content_type starts with the expected
# prefix — this catches obvious mismatches (e.g. .exe claiming image/png)
# without requiring libmagic.
EXTENSION_MIME_MAP: dict[str, tuple[str, ...]] = {
    ".pdf": ("application/pdf",),
    ".txt": ("text/plain",),
    ".csv": ("text/csv", "application/csv", "text/plain"),
    ".doc": ("application/msword",),
    ".docx": ("application/vnd.openxmlformats",),
    ".xlsx": ("application/vnd.openxmlformats",),
    ".xls": ("application/vnd.ms-excel",),
    ".png": ("image/png",),
    ".jpg": ("image/jpeg",),
    ".jpeg": ("image/jpeg",),
    ".gif": ("image/gif",),
    ".bmp": ("image/bmp",),
    ".webp": ("image/webp",),
}


def validate_file_extension(filename: str) -> str | None:
    """Return an error message if the extension is not allowed, else None."""
    from pathlib import Path

    suffix = Path(filename).suffix.lower()
    if not suffix:
        return "File has no extension."
    if suffix not in ALLOWED_EXTENSIONS:
        return f"File type '{suffix}' is not permitted."
    return None


def infer_content_type(filename: str, claimed_type: str | None) -> str:
    """Return a validated content type.

    If the claimed type is plausible for the file extension, use it.
    Otherwise, fall back to application/octet-stream.
    """
    from pathlib import Path

    suffix = Path(filename).suffix.lower()
    expected = EXTENSION_MIME_MAP.get(suffix)
    if expected and claimed_type:
        for prefix in expected:
            if claimed_type.startswith(prefix):
                return claimed_type
    # Fallback: use first expected type, or octet-stream
    if expected:
        return expected[0]
    return "application/octet-stream"
