"""Operator photo processing choices and external image identity/license verification.

Supports the three operator-selectable photo workflows for Issue #12 (F3-03):
1. `original`: Keep the operator's original product photo (validated with Pillow, EXIF stripped).
2. `pillow_optimize`: Optimize lighting/contrast/size using Pillow and strip EXIF metadata.
3. `exact_model_web_search`: Attach an external image ONLY for exact-model commercial products
   (e.g. sneakers) after verifying exact brand/model identity AND permissible copyright license.
"""

from __future__ import annotations

import base64
import hashlib
import io
import os
import re
import threading
import time
import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Literal

from PIL import Image, ImageEnhance, ImageOps, UnidentifiedImageError

PhotoChoice = Literal["original", "pillow_optimize", "exact_model_web_search"]

ALLOWED_EXTERNAL_LICENSES: frozenset[str] = frozenset(
    {
        "brand_press_kit",
        "authorized_distributor",
        "merchant_owned",
        "cc0",
        "cc_by",
        "cc_by_sa",
        "public_domain",
    }
)

ALLOWED_CONTENT_TYPES: frozenset[str] = frozenset(
    {
        "image/jpeg",
        "image/png",
        "image/webp",
    }
)


class MediaPolicyError(Exception):
    """Raised when image validation, identity matching, or copyright licensing fails."""

    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code
        self.message = message


@dataclass(frozen=True, slots=True)
class PreparedPhoto:
    """Validated photo payload ready for an attach_product_photo proposal."""

    mode: PhotoChoice
    filename: str
    content_type: str
    image_base64: str
    sha256: str
    width: int
    height: int
    size_bytes: int
    license_type: str
    source_attribution: str | None = None


@dataclass(frozen=True, slots=True)
class ExternalImageCandidate:
    """Metadata + bytes of a candidate external product image from exact-model search."""

    brand: str
    model_name: str
    model_code: str | None
    source_url: str
    license_type: str
    attribution: str
    filename: str
    content_type: str
    image_bytes: bytes


def _open_and_validate_image(image_bytes: bytes) -> Image.Image:
    if not image_bytes:
        raise MediaPolicyError("EMPTY_IMAGE", "La imagen proporcionada está vacía.")
    try:
        img = Image.open(io.BytesIO(image_bytes))
        img.load()
    except (UnidentifiedImageError, OSError) as exc:
        raise MediaPolicyError("INVALID_IMAGE", f"Archivo de imagen inválido o corrupto: {exc}") from exc
    return img


def _encode_clean_image(img: Image.Image, *, target_format: str, quality: int = 90) -> tuple[bytes, str]:
    """Re-encode image without EXIF metadata."""
    fmt = target_format.upper()
    out = io.BytesIO()
    if fmt == "JPEG":
        rgb = img.convert("RGB")
        rgb.save(out, format="JPEG", quality=quality, optimize=True)
        return out.getvalue(), "image/jpeg"
    if fmt == "WEBP":
        rgb = img.convert("RGB")
        rgb.save(out, format="WEBP", quality=quality, method=4)
        return out.getvalue(), "image/webp"
    if fmt == "PNG":
        rgba = img.convert("RGBA") if img.mode in ("RGBA", "LA", "P") else img.convert("RGB")
        rgba.save(out, format="PNG", optimize=True)
        return out.getvalue(), "image/png"
    raise MediaPolicyError("UNSUPPORTED_IMAGE_FORMAT", f"Formato de imagen no soportado: {fmt}")


def prepare_original_photo(
    *,
    image_bytes: bytes,
    filename: str,
    content_type: str,
) -> PreparedPhoto:
    """Validate operator's original photo and strip EXIF metadata without altering dimensions."""
    ctype = (content_type or "").strip().lower()
    if ctype not in ALLOWED_CONTENT_TYPES:
        raise MediaPolicyError(
            "UNSUPPORTED_CONTENT_TYPE",
            f"Tipo de imagen no permitido: {ctype}. Usa JPEG, PNG o WebP.",
        )

    img = _open_and_validate_image(image_bytes)
    img = ImageOps.exif_transpose(img)
    fmt_map = {"image/jpeg": "JPEG", "image/png": "PNG", "image/webp": "WEBP"}
    clean_bytes, clean_ctype = _encode_clean_image(img, target_format=fmt_map[ctype], quality=95)
    b64 = base64.b64encode(clean_bytes).decode("ascii")
    return PreparedPhoto(
        mode="original",
        filename=filename.strip() or "original.jpg",
        content_type=clean_ctype,
        image_base64=b64,
        sha256=hashlib.sha256(clean_bytes).hexdigest(),
        width=img.width,
        height=img.height,
        size_bytes=len(clean_bytes),
        license_type="merchant_owned",
        source_attribution="Foto original tomada por operador de tienda",
    )


def optimize_photo_with_pillow(
    *,
    image_bytes: bytes,
    filename: str,
    max_dimension: int = 1600,
    quality: int = 85,
) -> PreparedPhoto:
    """Optimize product photo with Pillow (auto-orient, resize, subtle contrast/sharpness, WebP, no EXIF)."""
    img = _open_and_validate_image(image_bytes)
    img = ImageOps.exif_transpose(img).convert("RGB")
    img.thumbnail((max_dimension, max_dimension), Image.Resampling.LANCZOS)
    img = ImageEnhance.Contrast(img).enhance(1.06)
    img = ImageEnhance.Sharpness(img).enhance(1.08)

    clean_bytes, clean_ctype = _encode_clean_image(img, target_format="WEBP", quality=quality)
    stem = (filename.strip() or "product").rsplit(".", 1)[0]
    out_filename = f"{stem}_opt.webp"
    b64 = base64.b64encode(clean_bytes).decode("ascii")
    return PreparedPhoto(
        mode="pillow_optimize",
        filename=out_filename,
        content_type=clean_ctype,
        image_base64=b64,
        sha256=hashlib.sha256(clean_bytes).hexdigest(),
        width=img.width,
        height=img.height,
        size_bytes=len(clean_bytes),
        license_type="merchant_owned",
        source_attribution="Foto original optimizada con Pillow",
    )


def verify_and_prepare_external_product_image(
    *,
    candidate: ExternalImageCandidate,
    expected_brand: str,
    expected_model: str,
    expected_model_code: str | None = None,
) -> PreparedPhoto:
    """Verify exact-model identity AND permissible copyright license before attaching an external image.

    Fails closed on brand/model mismatch or non-permitted/unknown copyright licenses.
    """
    license_norm = (candidate.license_type or "").strip().lower()
    if license_norm not in ALLOWED_EXTERNAL_LICENSES:
        raise MediaPolicyError(
            "COPYRIGHT_LICENSE_REJECTED",
            f"Licencia externa no permitida ({candidate.license_type!r}). "
            "No se permite adjuntar imágenes con derechos reservados o licencia desconocida.",
        )

    if not (candidate.attribution or "").strip() or not (candidate.source_url or "").strip():
        raise MediaPolicyError(
            "MISSING_ATTRIBUTION",
            "Toda imagen externa debe incluir fuente verificable y atribución de licencia.",
        )

    exp_brand = (expected_brand or "").strip().lower()
    cand_brand = (candidate.brand or "").strip().lower()
    if not exp_brand or exp_brand != cand_brand:
        raise MediaPolicyError(
            "MODEL_IDENTITY_MISMATCH",
            f"La marca de la imagen externa ({candidate.brand!r}) no coincide con {expected_brand!r}.",
        )

    exp_model = (expected_model or "").strip().lower()
    cand_model = (candidate.model_name or "").strip().lower()
    if not exp_model or exp_model not in cand_model:
        raise MediaPolicyError(
            "MODEL_IDENTITY_MISMATCH",
            f"El modelo de la imagen externa ({candidate.model_name!r}) no coincide con {expected_model!r}.",
        )

    if expected_model_code:
        exp_code = expected_model_code.strip().lower()
        cand_code = (candidate.model_code or "").strip().lower()
        if exp_code != cand_code:
            raise MediaPolicyError(
                "MODEL_CODE_MISMATCH",
                f"El código de modelo ({candidate.model_code!r}) no coincide exactamente con {expected_model_code!r}.",
            )

    ctype = (candidate.content_type or "").strip().lower()
    if ctype not in ALLOWED_CONTENT_TYPES:
        raise MediaPolicyError(
            "UNSUPPORTED_CONTENT_TYPE",
            f"Tipo de imagen externa no permitido: {ctype}.",
        )

    img = _open_and_validate_image(candidate.image_bytes)
    img = ImageOps.exif_transpose(img)
    fmt_map = {"image/jpeg": "JPEG", "image/png": "PNG", "image/webp": "WEBP"}
    clean_bytes, clean_ctype = _encode_clean_image(img, target_format=fmt_map[ctype], quality=92)
    b64 = base64.b64encode(clean_bytes).decode("ascii")
    return PreparedPhoto(
        mode="exact_model_web_search",
        filename=candidate.filename.strip() or "verified_external.jpg",
        content_type=clean_ctype,
        image_base64=b64,
        sha256=hashlib.sha256(clean_bytes).hexdigest(),
        width=img.width,
        height=img.height,
        size_bytes=len(clean_bytes),
        license_type=license_norm,
        source_attribution=f"{candidate.attribution.strip()} ({candidate.source_url.strip()})",
    )


# ---------------------------------------------------------------------------
# Trusted Telegram Photo Staging (Hermes v0.23.4 [Image attached at: <path>])
# ---------------------------------------------------------------------------

_IMAGE_ATTACHED_RE = re.compile(r"\[Image attached at:\s*([^\]]+)\]")
_PILLOW_FORMAT_TO_CTYPE = {"JPEG": "image/jpeg", "PNG": "image/png", "WEBP": "image/webp"}


def default_allowed_image_cache_dirs(env: dict[str, str] | None = None) -> tuple[Path, ...]:
    """Return allowed Hermes image cache directories (default under HERMES_HOME=/opt/data)."""
    src = env if env is not None else os.environ
    raw_override = (src.get("HERMES_ALLOWED_IMAGE_CACHE_DIRS") or "").strip()
    if raw_override:
        return tuple(Path(p.strip()) for p in raw_override.split(os.pathsep) if p.strip())
    hermes_home = Path((src.get("HERMES_HOME") or "/opt/data").strip())
    return (
        hermes_home / "cache" / "images",
        hermes_home / "image_cache",
        hermes_home / "native-inputs",
    )


def extract_attached_image_paths(user_message: Any) -> list[str]:
    """Extract `[Image attached at: <path>]` markers from Hermes pre_llm_call user_message."""
    texts: list[str] = []
    if isinstance(user_message, str):
        texts.append(user_message)
    elif isinstance(user_message, list):
        for part in user_message:
            if isinstance(part, str):
                texts.append(part)
            elif isinstance(part, dict) and isinstance(part.get("text"), str):
                texts.append(part["text"])
    paths: list[str] = []
    for txt in texts:
        for match in _IMAGE_ATTACHED_RE.finditer(txt):
            candidate = match.group(1).strip()
            if candidate:
                paths.append(candidate)
    return paths


@dataclass(frozen=True, slots=True)
class StagedPhoto:
    """Trusted server-side record of a Telegram photo cached by Hermes."""

    attachment_id: str
    telegram_user_id: int
    dm_session_id: str
    real_path: str
    filename: str
    content_type: str
    size_bytes: int
    created_at: float
    expires_at: float


class StagedPhotoRegistry:
    """Fail-closed registry binding Hermes-cached Telegram photos to `(uid, dm_session)` via opaque IDs."""

    def __init__(
        self,
        *,
        allowed_roots: tuple[Path, ...] | None = None,
        max_bytes: int = 10 * 1024 * 1024,
        default_ttl_seconds: int = 300,
    ) -> None:
        self._allowed_roots = allowed_roots
        self._max_bytes = max_bytes
        self._default_ttl_seconds = default_ttl_seconds
        self._lock = threading.Lock()
        self._staged: dict[str, StagedPhoto] = {}

    def _roots(self) -> tuple[str, ...]:
        roots = self._allowed_roots if self._allowed_roots is not None else default_allowed_image_cache_dirs()
        return tuple(os.path.realpath(str(r)) for r in roots)

    def _validate_path(self, raw_path: str) -> str:
        p = Path(raw_path)
        # Reject symlinks anywhere along the path (fail-closed)
        if os.path.islink(raw_path) or p.is_symlink():
            raise MediaPolicyError("SYMLINK_NOT_ALLOWED", "No se permiten enlaces simbólicos en adjuntos de imagen.")

        real_path = os.path.realpath(raw_path)
        allowed = self._roots()
        inside = False
        for root in allowed:
            try:
                if os.path.commonpath([root, real_path]) == root and real_path != root:
                    inside = True
                    break
            except ValueError:
                continue
        if not inside:
            raise MediaPolicyError(
                "PATH_OUTSIDE_ALLOWED_CACHE",
                "La ruta de imagen está fuera del directorio de caché permitido de Hermes.",
            )

        if not os.path.isfile(real_path):
            raise MediaPolicyError("FILE_NOT_FOUND", "El archivo de imagen en caché no existe o no es un archivo regular.")

        # Re-check symlink after resolution
        if os.path.islink(real_path):
            raise MediaPolicyError("SYMLINK_NOT_ALLOWED", "No se permiten enlaces simbólicos en adjuntos de imagen.")
        return real_path

    def stage_from_gateway_path(
        self,
        *,
        raw_path: str,
        telegram_user_id: int,
        dm_session_id: str,
        ttl_seconds: int | None = None,
        now: float | None = None,
    ) -> StagedPhoto:
        """Validate a Hermes-cached image path and register an opaque attachment_id."""
        real_path = self._validate_path(raw_path)
        size = os.path.getsize(real_path)
        if size <= 0:
            raise MediaPolicyError("EMPTY_IMAGE", "El archivo de imagen en caché está vacío.")
        if size > self._max_bytes:
            raise MediaPolicyError("IMAGE_TOO_LARGE", f"La imagen excede el límite permitido ({self._max_bytes} bytes).")

        with open(real_path, "rb") as fh:
            raw_bytes = fh.read()
        img = _open_and_validate_image(raw_bytes)
        fmt = (img.format or "").upper()
        ctype = _PILLOW_FORMAT_TO_CTYPE.get(fmt)
        if not ctype:
            raise MediaPolicyError("UNSUPPORTED_IMAGE_FORMAT", f"Formato de imagen no soportado: {fmt!r}")

        created = time.time() if now is None else now
        ttl = self._default_ttl_seconds if ttl_seconds is None else ttl_seconds
        att_id = f"att_{uuid.uuid4().hex[:10]}"
        record = StagedPhoto(
            attachment_id=att_id,
            telegram_user_id=telegram_user_id,
            dm_session_id=dm_session_id,
            real_path=real_path,
            filename=os.path.basename(real_path),
            content_type=ctype,
            size_bytes=size,
            created_at=created,
            expires_at=created + ttl,
        )
        with self._lock:
            self._staged[att_id] = record
        return record

    def resolve_staged_bytes(
        self,
        *,
        attachment_id: str,
        telegram_user_id: int,
        dm_session_id: str,
        now: float | None = None,
    ) -> tuple[bytes, str, str]:
        """Resolve an opaque attachment_id (or 'latest') to verified bytes for the owning operator."""
        current = time.time() if now is None else now
        with self._lock:
            if attachment_id == "latest":
                candidates = [
                    r
                    for r in self._staged.values()
                    if r.telegram_user_id == telegram_user_id
                    and r.dm_session_id == dm_session_id
                    and current < r.expires_at
                ]
                if not candidates:
                    raise MediaPolicyError(
                        "ATTACHMENT_NOT_FOUND",
                        "No hay ninguna foto vigente adjunta en esta conversación.",
                    )
                rec = max(candidates, key=lambda r: r.created_at)
            else:
                rec = self._staged.get(attachment_id)
                if rec is None:
                    raise MediaPolicyError("ATTACHMENT_NOT_FOUND", f"Adjunto '{attachment_id}' no encontrado.")

        if rec.telegram_user_id != telegram_user_id:
            raise MediaPolicyError("UNAUTHORIZED_ATTACHMENT", "No puedes usar una foto adjunta por otro operador.")
        if rec.dm_session_id != dm_session_id:
            raise MediaPolicyError("ATTACHMENT_SESSION_MISMATCH", "La foto pertenece a otra conversación.")
        if current >= rec.expires_at:
            raise MediaPolicyError("ATTACHMENT_EXPIRED", "La foto adjunta expiró; vuelve a enviarla por Telegram.")

        real_path = self._validate_path(rec.real_path)
        with open(real_path, "rb") as fh:
            raw_bytes = fh.read()
        return raw_bytes, rec.filename, rec.content_type

    def clear(self) -> None:
        with self._lock:
            self._staged.clear()
