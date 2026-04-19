"""Security module — input validation and safe PowerShell encoding.

All user-provided or disk-read values MUST pass through these validators
before being handed to QProcess / subprocess.  Functions raise
``ValueError`` on invalid input so callers can handle gracefully.

Design rationale
~~~~~~~~~~~~~~~~
- **validate_url**: Allowlists schemes (http, https) and rejects
  argument-injection attempts (values starting with ``-``). Uses
  ``urllib.parse`` from stdlib — no third-party deps.
- **validate_port**: Ensures integer in the unprivileged range 1024-65535.
- **validate_endpoint**: Allows hostnames / IPs with optional port;
  blocks shell metacharacters.
- **validate_dpapi_blob**: DPAPI ``ConvertFrom-SecureString`` output is
  strictly hexadecimal.  Anything else means the on-disk value was
  tampered with.
- **encode_ps_command**: Produces a Base64-encoded UTF-16LE string
  suitable for ``powershell -EncodedCommand``, making the pipeline
  immune to any metacharacter injection (CWE-78).
- **redact_key**: Masks secrets so they never leak into log output.
"""

from __future__ import annotations

import base64
import re
from urllib.parse import urlparse

# ── Compiled Patterns (module-level, compiled once) ──────────────────

_HEX_ONLY = re.compile(r"^[0-9A-Fa-f]+$")
_SAFE_ENDPOINT = re.compile(r"^[a-zA-Z0-9.\-:_]+$")


# ── Validators ───────────────────────────────────────────────────────

def validate_url(url: str) -> str:
    """Validate and return a cleaned URL.

    Raises ``ValueError`` if the URL is invalid or potentially malicious.
    """
    if not url or not isinstance(url, str):
        raise ValueError("URL must be a non-empty string.")

    stripped = url.strip()

    # Block argument-injection (e.g. "--malicious-flag")
    if stripped.startswith("-"):
        raise ValueError(f"URL must not start with a dash: {stripped!r}")

    parsed = urlparse(stripped)

    # Require explicit http or https scheme
    if parsed.scheme not in ("http", "https"):
        raise ValueError(
            f"URL scheme must be 'http' or 'https', got {parsed.scheme!r}."
        )

    # Must have a hostname
    if not parsed.hostname:
        raise ValueError("URL must contain a valid hostname.")

    return stripped


def validate_port(port: int | str) -> int:
    """Validate and return a port number in the safe range 1024-65535.

    Raises ``ValueError`` on invalid input.
    """
    try:
        port_int = int(port)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"Port must be an integer, got {port!r}.") from exc

    if not 1024 <= port_int <= 65535:
        raise ValueError(
            f"Port must be between 1024 and 65535, got {port_int}."
        )
    return port_int


def validate_endpoint(endpoint: str) -> str:
    """Validate a hostname/IP endpoint string (e.g. ``api.example.com:443``).

    Only allows alphanumerics, dots, hyphens, colons, and underscores.
    Raises ``ValueError`` on invalid input.
    """
    if not endpoint or not isinstance(endpoint, str):
        raise ValueError("Endpoint must be a non-empty string.")

    stripped = endpoint.strip()

    if not _SAFE_ENDPOINT.match(stripped):
        raise ValueError(
            f"Endpoint contains forbidden characters: {stripped!r}. "
            f"Allowed: a-z A-Z 0-9 . - : _"
        )

    return stripped


def validate_dpapi_blob(blob: str) -> str:
    """Validate that a DPAPI-encrypted blob is strictly hexadecimal.

    ``ConvertFrom-SecureString`` outputs a hex-encoded string. If it
    contains anything else, the file was tampered with.

    Raises ``ValueError`` on invalid input.
    """
    if not blob or not isinstance(blob, str):
        raise ValueError("DPAPI blob must be a non-empty string.")

    stripped = blob.strip()

    if not _HEX_ONLY.match(stripped):
        raise ValueError(
            "DPAPI blob contains non-hex characters — possible tampering."
        )

    return stripped


# ── Safe PowerShell Encoding ─────────────────────────────────────────

def encode_ps_command(script: str) -> str:
    """Encode a PowerShell script block as a Base64 UTF-16LE string.

    Returns the encoded string ready for ``powershell -EncodedCommand``.
    This approach is immune to all metacharacter injection attacks
    because the entire script is treated as opaque binary data by the
    shell layer.

    Example::

        encoded = encode_ps_command("Write-Host 'hello'")
        # → "VwByAGkAdABlAC0ASABvAHMAdAAgACcAaABlAGwAbABvACcA"
    """
    if not script:
        raise ValueError("PowerShell script must not be empty.")
    raw = script.encode("utf-16-le")
    return base64.b64encode(raw).decode("ascii")


# ── Secret Redaction ─────────────────────────────────────────────────

def redact_key(text: str, key: str) -> str:
    """Replace occurrences of *key* in *text* with a redacted placeholder.

    Returns *text* unchanged if *key* is empty.
    """
    if not key:
        return text
    return text.replace(key, "***REDACTED***")
