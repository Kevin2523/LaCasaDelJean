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
from dataclasses import dataclass
from typing import Literal

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
