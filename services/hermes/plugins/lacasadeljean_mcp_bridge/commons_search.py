"""Server-side Wikimedia Commons MediaWiki API licensed image search provider (Issue #12).

Zero-credential, read-only provider for `exact_model_web_search` suitable for 8 GB RAM / Ryzen 3:
- Queries `https://commons.wikimedia.org/w/api.php` (MediaWiki API, File namespace).
- Verifies exact brand + model + model_code in official Commons metadata.
- Verifies permissible commercial-safe licenses (CC0, Public Domain, CC BY, CC BY-SA);
  rejects NC/ND/fair-use/all-rights-reserved/unknown licenses.
- Stores verified candidates server-side under opaque IDs (`ext_...`) bound to
  `(telegram_user_id, dm_session_id)` with TTL.
- Downloads bytes strictly over HTTPS from `upload.wikimedia.org` (`follow_redirects=False`)
  with a strict size cap before EXIF stripping & Pillow validation.
"""

from __future__ import annotations

import re
import threading
import time
import uuid
from dataclasses import dataclass
from typing import Any
from urllib.parse import urlparse

import httpx

from .media import (
    ALLOWED_CONTENT_TYPES,
    ExternalImageCandidate,
    MediaPolicyError,
    PreparedPhoto,
    verify_and_prepare_external_product_image,
)

COMMONS_API_URL = "https://commons.wikimedia.org/w/api.php"
ALLOWED_DOWNLOAD_HOSTS: frozenset[str] = frozenset({"upload.wikimedia.org"})
_HTML_TAG_RE = re.compile(r"<[^>]+>")


def _strip_html(raw: str) -> str:
    return _HTML_TAG_RE.sub("", raw or "").strip()


def _has_exact_token_sequence(haystack: str, needle: str) -> bool:
    """Match needle as an exact alphanumeric token sequence (rejects substrings like Niketown or CW2288-111X)."""
    tokens = [t for t in re.split(r"[\s_]+", (needle or "").strip().lower()) if t]
    if not tokens:
        return False
    pattern = r"(?<![a-z0-9])" + r"[\s_]+".join(re.escape(t) for t in tokens) + r"(?![a-z0-9])"
    return re.search(pattern, (haystack or "").lower()) is not None


def normalize_commons_license(raw_short_name: str) -> str | None:
    """Map Wikimedia Commons LicenseShortName to our commercial-safe allowlist, or None if disallowed."""
    norm = (raw_short_name or "").strip().lower()
    if not norm:
        return None
    # Reject Non-Commercial (NC), No-Derivatives (ND), Fair use, Copyrighted
    if any(bad in norm for bad in ("nc", "nd", "fair use", "copyright", "all rights", "gpl")):
        return None
    if norm.startswith("cc0") or "cc-zero" in norm:
        return "cc0"
    if "public domain" in norm or norm == "pd":
        return "public_domain"
    if norm.startswith("cc by-sa") or norm.startswith("cc-by-sa"):
        return "cc_by_sa"
    if norm.startswith("cc by") or norm.startswith("cc-by"):
        return "cc_by"
    return None


def validate_allowed_download_url(url: str) -> str:
    """Strict SSRF guard: HTTPS only, host strictly in ALLOWED_DOWNLOAD_HOSTS."""
    parsed = urlparse((url or "").strip())
    if parsed.scheme.lower() != "https":
        raise MediaPolicyError("SSRF_BLOCKED", "Solo se permiten descargas de imágenes por HTTPS.")
    host = (parsed.hostname or "").lower()
    if host not in ALLOWED_DOWNLOAD_HOSTS:
        raise MediaPolicyError(
            "SSRF_BLOCKED",
            f"Host de descarga no permitido ({host!r}); solo se permite upload.wikimedia.org.",
        )
    return url.strip()


@dataclass(frozen=True, slots=True)
class StagedExternalCandidate:
    """Server-side verified Wikimedia Commons candidate bound to an operator DM session."""

    candidate_id: str
    telegram_user_id: int
    dm_session_id: str
    brand: str
    model_name: str
    model_code: str
    title: str
    download_url: str
    description_url: str
    license_type: str
    license_raw: str
    attribution: str
    content_type: str
    size_bytes: int
    created_at: float
    expires_at: float


class CommonsImageSearchProvider:
    """Read-only Wikimedia Commons search + server-side opaque candidate registry."""

    def __init__(
        self,
        *,
        transport: httpx.BaseTransport | None = None,
        max_bytes: int = 10 * 1024 * 1024,
        default_ttl_seconds: int = 300,
        timeout_seconds: float = 10.0,
    ) -> None:
        self._transport = transport
        self._max_bytes = max_bytes
        self._default_ttl_seconds = default_ttl_seconds
        self._timeout_seconds = timeout_seconds
        self._lock = threading.Lock()
        self._candidates: dict[str, StagedExternalCandidate] = {}

    def search_and_stage(
        self,
        *,
        brand: str,
        model_name: str,
        model_code: str,
        telegram_user_id: int,
        dm_session_id: str,
        limit: int = 5,
        now: float | None = None,
    ) -> list[dict[str, Any]]:
        """Query Wikimedia Commons API, filter by exact brand+model+code & commercial-safe license, and stage."""
        b = (brand or "").strip()
        m = (model_name or "").strip()
        c = (model_code or "").strip()
        if not b or not m or not c:
            raise MediaPolicyError(
                "EXACT_MODEL_QUERY_REQUIRED",
                "Se requieren brand, model_name y model_code exactos para buscar imágenes externas.",
            )

        params = {
            "action": "query",
            "format": "json",
            "generator": "search",
            "gsrnamespace": "6",
            "gsrsearch": f"{b} {m} {c}",
            "gsrlimit": str(min(max(limit, 1), 10)),
            "prop": "imageinfo",
            "iiprop": "url|mime|size|extmetadata",
        }
        headers = {"User-Agent": "LaCasaDelJeanV2-InventoryBot/1.0 (https://commons.wikimedia.org)"}

        try:
            with httpx.Client(
                transport=self._transport,
                timeout=self._timeout_seconds,
                follow_redirects=False,
            ) as client:
                resp = client.get(COMMONS_API_URL, params=params, headers=headers)
        except httpx.HTTPError as exc:
            raise MediaPolicyError("COMMONS_UNREACHABLE", f"No se pudo consultar Wikimedia Commons: {exc}") from exc

        if resp.status_code != 200:
            raise MediaPolicyError("COMMONS_HTTP_ERROR", f"Wikimedia Commons devolvió HTTP {resp.status_code}.")

        try:
            payload = resp.json()
        except ValueError as exc:
            raise MediaPolicyError("COMMONS_INVALID_RESPONSE", "Respuesta JSON inválida de Wikimedia Commons.") from exc

        pages = (payload.get("query") or {}).get("pages") or {}
        created = time.time() if now is None else now
        results: list[dict[str, Any]] = []

        for page in pages.values():
            title = str(page.get("title") or "")
            infos = page.get("imageinfo") or []
            if not infos:
                continue
            info = infos[0]
            mime = str(info.get("mime") or "").strip().lower()
            size = int(info.get("size") or 0)
            url = str(info.get("url") or "").strip()
            desc_url = str(info.get("descriptionurl") or url).strip()
            if mime not in ALLOWED_CONTENT_TYPES or size <= 0 or size > self._max_bytes:
                continue

            try:
                validate_allowed_download_url(url)
            except MediaPolicyError:
                continue

            extmeta = info.get("extmetadata") or {}
            raw_lic = _strip_html(str((extmeta.get("LicenseShortName") or {}).get("value") or ""))
            lic_norm = normalize_commons_license(raw_lic)
            if not lic_norm:
                continue

            artist = _strip_html(str((extmeta.get("Artist") or {}).get("value") or ""))
            credit = _strip_html(str((extmeta.get("Credit") or {}).get("value") or ""))
            obj_name = _strip_html(str((extmeta.get("ObjectName") or {}).get("value") or ""))
            img_desc = _strip_html(str((extmeta.get("ImageDescription") or {}).get("value") or ""))
            combined_meta = f"{title} {obj_name} {img_desc}".lower()

            # Require exact token-boundary match for brand, model_name, and model_code
            if (
                not _has_exact_token_sequence(combined_meta, b)
                or not _has_exact_token_sequence(combined_meta, m)
                or not _has_exact_token_sequence(combined_meta, c)
            ):
                continue

            attribution = artist or credit or "Wikimedia Commons contributor"
            cand_id = f"ext_{uuid.uuid4().hex[:10]}"
            record = StagedExternalCandidate(
                candidate_id=cand_id,
                telegram_user_id=telegram_user_id,
                dm_session_id=dm_session_id,
                brand=b,
                model_name=m,
                model_code=c,
                title=title,
                download_url=url,
                description_url=desc_url,
                license_type=lic_norm,
                license_raw=raw_lic,
                attribution=attribution,
                content_type=mime,
                size_bytes=size,
                created_at=created,
                expires_at=created + self._default_ttl_seconds,
            )
            with self._lock:
                self._candidates[cand_id] = record
            results.append(
                {
                    "candidate_id": cand_id,
                    "title": title,
                    "url": desc_url,
                    "license_type": lic_norm,
                    "license_raw": raw_lic,
                    "attribution": attribution,
                    "content_type": mime,
                    "size_bytes": size,
                }
            )

        return results

    def fetch_and_prepare_candidate(
        self,
        *,
        candidate_id: str,
        telegram_user_id: int,
        dm_session_id: str,
        now: float | None = None,
    ) -> PreparedPhoto:
        """Re-validate ownership, TTL, license, and SSRF host; download bytes and strip EXIF."""
        current = time.time() if now is None else now
        with self._lock:
            rec = self._candidates.get(candidate_id)
        if rec is None:
            raise MediaPolicyError("CANDIDATE_NOT_FOUND", f"Candidato externo '{candidate_id}' no encontrado.")
        if rec.telegram_user_id != telegram_user_id:
            raise MediaPolicyError("UNAUTHORIZED_CANDIDATE", "No puedes usar un candidato buscado por otro operador.")
        if rec.dm_session_id != dm_session_id:
            raise MediaPolicyError("CANDIDATE_SESSION_MISMATCH", "El candidato pertenece a otra conversación.")
        if current >= rec.expires_at:
            raise MediaPolicyError("CANDIDATE_EXPIRED", "El candidato externo expiró; vuelve a ejecutar la búsqueda.")

        safe_url = validate_allowed_download_url(rec.download_url)
        headers = {"User-Agent": "LaCasaDelJeanV2-InventoryBot/1.0 (https://commons.wikimedia.org)"}
        buf = bytearray()
        try:
            with httpx.Client(
                transport=self._transport,
                timeout=self._timeout_seconds,
                follow_redirects=False,
            ) as client:
                with client.stream("GET", safe_url, headers=headers) as resp:
                    if resp.status_code != 200:
                        raise MediaPolicyError(
                            "COMMONS_DOWNLOAD_ERROR",
                            f"Descarga rechazada por Wikimedia Commons (HTTP {resp.status_code}).",
                        )
                    resp_mime = (resp.headers.get("content-type") or "").split(";", 1)[0].strip().lower()
                    if resp_mime not in ALLOWED_CONTENT_TYPES:
                        raise MediaPolicyError(
                            "UNSUPPORTED_CONTENT_TYPE",
                            f"Tipo MIME de descarga no permitido: {resp_mime!r}.",
                        )
                    raw_cl = resp.headers.get("content-length")
                    if raw_cl is not None:
                        try:
                            if int(raw_cl) > self._max_bytes:
                                raise MediaPolicyError(
                                    "IMAGE_TOO_LARGE",
                                    "La imagen excede el límite de tamaño permitido (Content-Length).",
                                )
                        except ValueError:
                            pass
                    for chunk in resp.iter_bytes(chunk_size=65536):
                        buf.extend(chunk)
                        if len(buf) > self._max_bytes:
                            raise MediaPolicyError(
                                "IMAGE_TOO_LARGE",
                                "La imagen descargada excede el límite de tamaño permitido.",
                            )
        except MediaPolicyError:
            raise
        except httpx.HTTPError as exc:
            raise MediaPolicyError("COMMONS_DOWNLOAD_ERROR", f"Error al descargar imagen de Wikimedia Commons: {exc}") from exc

        raw_bytes = bytes(buf)

        filename = rec.title.removeprefix("File:").strip().replace(" ", "_") or "commons_product.jpg"
        return verify_and_prepare_external_product_image(
            candidate=ExternalImageCandidate(
                brand=rec.brand,
                model_name=rec.model_name,
                model_code=rec.model_code,
                source_url=rec.description_url,
                license_type=rec.license_type,
                attribution=rec.attribution,
                filename=filename,
                content_type=rec.content_type,
                image_bytes=raw_bytes,
            ),
            expected_brand=rec.brand,
            expected_model=rec.model_name,
            expected_model_code=rec.model_code,
        )

    def clear(self) -> None:
        with self._lock:
            self._candidates.clear()
