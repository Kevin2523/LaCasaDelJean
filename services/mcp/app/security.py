"""Cryptographic verification helpers and test signers (stateless; durability lives in FastAPI/PG)."""

from __future__ import annotations

import hashlib
import hmac
import json
import time
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any

import jwt

ACTOR_ISSUER = "hermes-telegram-bridge"
APPROVAL_ISSUER = "hermes-telegram-approval"
MCP_AUDIENCE = "lacasadeljean-mcp"


class SecurityError(Exception):
    """Raised when transport auth, actor assertion, or approval proof fails."""

    def __init__(self, code: str, message: str, status_code: int = 403) -> None:
        super().__init__(message)
        self.code = code
        self.message = message
        self.status_code = status_code


@dataclass(frozen=True, slots=True)
class VerifiedActor:
    """Verified Telegram operator identity extracted from X-Actor-Assertion."""

    telegram_user_id: int
    jti: str
    expires_at: datetime


@dataclass(frozen=True, slots=True)
class VerifiedApproval:
    """Verified approval proof metadata ready for durable one-use consumption."""

    jti: str
    expires_at: datetime


def _require_configured_secret(secret: str, name: str) -> str:
    cleaned = (secret or "").strip()
    if not cleaned or cleaned.startswith("CHANGE_ME"):
        raise SecurityError("MISCONFIGURED", f"{name} no está configurado.", status_code=500)
    return cleaned


def canonical_payload_hash(payload: dict[str, Any]) -> str:
    """Compute deterministic SHA-256 hex digest of a normalized JSON payload."""
    canonical = json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def verify_bearer_token(authorization_header: str | None, expected_secret: str) -> None:
    """Verify Authorization: Bearer <HERMES_MCP_SHARED_SECRET> in constant time."""
    expected = _require_configured_secret(expected_secret, "HERMES_MCP_SHARED_SECRET")
    if not authorization_header:
        raise SecurityError("UNAUTHORIZED", "Se requiere token Bearer MCP.", status_code=401)
    scheme, _, token = authorization_header.partition(" ")
    if scheme.lower() != "bearer" or not token.strip():
        raise SecurityError("UNAUTHORIZED", "Cabecera Authorization inválida.", status_code=401)
    if not hmac.compare_digest(token.strip(), expected):
        raise SecurityError("UNAUTHORIZED", "Token Bearer MCP inválido.", status_code=401)


def verify_actor_assertion(
    token: str | None,
    *,
    secret: str,
    max_ttl_seconds: int,
) -> VerifiedActor:
    """Verify signed X-Actor-Assertion JWT structure, signature, claims, and TTL."""
    key = _require_configured_secret(secret, "MCP_ACTOR_ASSERTION_SECRET")
    if not token or not token.strip():
        raise SecurityError("UNAUTHENTICATED_ACTOR", "Falta cabecera X-Actor-Assertion.", status_code=401)

    try:
        claims = jwt.decode(
            token.strip(),
            key,
            algorithms=["HS256"],
            audience=MCP_AUDIENCE,
            issuer=ACTOR_ISSUER,
            options={"require": ["sub", "telegram_user_id", "jti", "iat", "exp", "iss", "aud"]},
        )
    except jwt.PyJWTError as exc:
        raise SecurityError("INVALID_ACTOR_ASSERTION", f"Aserción de actor inválida: {exc}", status_code=401) from exc

    iat = int(claims["iat"])
    exp = int(claims["exp"])
    if exp - iat <= 0 or (exp - iat) > max_ttl_seconds:
        raise SecurityError("INVALID_ACTOR_TTL", "TTL de X-Actor-Assertion fuera de rango permitido.", status_code=401)

    raw_tg_id = claims["telegram_user_id"]
    if not isinstance(raw_tg_id, int) or isinstance(raw_tg_id, bool) or raw_tg_id <= 0:
        raise SecurityError("INVALID_ACTOR_ID", "telegram_user_id inválido en aserción.", status_code=401)

    if claims["sub"] != f"tg:{raw_tg_id}":
        raise SecurityError("INVALID_ACTOR_SUB", "Claim sub no coincide con telegram_user_id.", status_code=401)

    jti = str(claims["jti"]).strip()
    if not jti:
        raise SecurityError("INVALID_ACTOR_JTI", "jti vacío en X-Actor-Assertion.", status_code=401)

    return VerifiedActor(
        telegram_user_id=raw_tg_id,
        jti=jti,
        expires_at=datetime.fromtimestamp(exp, tz=timezone.utc),
    )


def verify_approval_proof(
    proof: str | None,
    *,
    secret: str,
    expected_telegram_user_id: int,
    expected_action: str,
    expected_payload: dict[str, Any],
    max_ttl_seconds: int,
) -> VerifiedApproval:
    """Verify signed, scoped, short-lived approval_proof (one-use enforced durably in FastAPI/PG)."""
    key = _require_configured_secret(secret, "MCP_APPROVAL_SIGNING_SECRET")
    if not proof or not proof.strip():
        raise SecurityError(
            "APPROVAL_REQUIRED",
            f"La acción de escritura '{expected_action}' requiere approval_proof firmado.",
            status_code=403,
        )

    try:
        claims = jwt.decode(
            proof.strip(),
            key,
            algorithms=["HS256"],
            audience=MCP_AUDIENCE,
            issuer=APPROVAL_ISSUER,
            options={
                "require": [
                    "telegram_user_id",
                    "action",
                    "payload_sha256",
                    "jti",
                    "iat",
                    "exp",
                    "iss",
                    "aud",
                ]
            },
        )
    except jwt.PyJWTError as exc:
        raise SecurityError("INVALID_APPROVAL_PROOF", f"approval_proof inválido o expirado: {exc}", status_code=403) from exc

    iat = int(claims["iat"])
    exp = int(claims["exp"])
    if exp - iat <= 0 or (exp - iat) > max_ttl_seconds:
        raise SecurityError("INVALID_APPROVAL_TTL", "TTL de approval_proof excede el máximo permitido.", status_code=403)

    if claims["telegram_user_id"] != expected_telegram_user_id:
        raise SecurityError("APPROVAL_ACTOR_MISMATCH", "approval_proof no corresponde al operador autenticado.", status_code=403)

    if claims["action"] != expected_action:
        raise SecurityError("APPROVAL_ACTION_MISMATCH", "approval_proof no corresponde a la acción solicitada.", status_code=403)

    expected_hash = canonical_payload_hash(expected_payload)
    if not hmac.compare_digest(str(claims["payload_sha256"]), expected_hash):
        raise SecurityError("APPROVAL_SCOPE_MISMATCH", "approval_proof no coincide con los parámetros exactos de la operación.", status_code=403)

    jti = str(claims["jti"]).strip()
    if not jti:
        raise SecurityError("INVALID_APPROVAL_PROOF", "jti vacío en approval_proof.", status_code=403)

    return VerifiedApproval(
        jti=jti,
        expires_at=datetime.fromtimestamp(exp, tz=timezone.utc),
    )


# ---------------------------------------------------------------------------
# Test signers (used by automated tests until Issue #12 Telegram plugin exists)
# ---------------------------------------------------------------------------


def sign_actor_assertion(
    *,
    telegram_user_id: int,
    secret: str,
    ttl_seconds: int = 30,
    jti: str | None = None,
    iat: int | None = None,
) -> str:
    """Sign a short-lived X-Actor-Assertion JWT for testing or bridge integration."""
    issued = int(time.time()) if iat is None else iat
    payload = {
        "iss": ACTOR_ISSUER,
        "aud": MCP_AUDIENCE,
        "sub": f"tg:{telegram_user_id}",
        "telegram_user_id": telegram_user_id,
        "jti": jti or str(uuid.uuid4()),
        "iat": issued,
        "exp": issued + ttl_seconds,
    }
    return jwt.encode(payload, secret, algorithm="HS256")


def sign_approval_proof(
    *,
    telegram_user_id: int,
    action: str,
    payload: dict[str, Any],
    secret: str,
    ttl_seconds: int = 60,
    jti: str | None = None,
    iat: int | None = None,
) -> str:
    """Sign a scoped, short-lived, one-use approval_proof JWT (test signer until #12)."""
    issued = int(time.time()) if iat is None else iat
    claims = {
        "iss": APPROVAL_ISSUER,
        "aud": MCP_AUDIENCE,
        "telegram_user_id": telegram_user_id,
        "action": action,
        "payload_sha256": canonical_payload_hash(payload),
        "jti": jti or str(uuid.uuid4()),
        "iat": issued,
        "exp": issued + ttl_seconds,
    }
    return jwt.encode(claims, secret, algorithm="HS256")
