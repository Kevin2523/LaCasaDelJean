"""Cryptographic verification, anti-replay nonces, idempotency cache, and test signers."""

from __future__ import annotations

import hashlib
import hmac
import json
import threading
import time
import uuid
from dataclasses import dataclass
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


class NonceStore:
    """Thread-safe bounded TTL store for one-use JTI anti-replay enforcement."""

    def __init__(self, max_entries: int = 10_000) -> None:
        self._lock = threading.Lock()
        self._entries: dict[str, float] = {}
        self._max_entries = max_entries

    def consume(self, jti: str, expires_at: float) -> bool:
        """Consume a nonce; returns False if already used (replay)."""
        now = time.time()
        with self._lock:
            if len(self._entries) >= self._max_entries:
                expired = [k for k, exp in self._entries.items() if exp <= now]
                for k in expired:
                    del self._entries[k]
            if jti in self._entries and self._entries[jti] > now:
                return False
            self._entries[jti] = max(expires_at, now + 60.0)
            return True


class IdempotencyStore:
    """Thread-safe bounded TTL store for idempotent MCP catalog draft creations."""

    def __init__(self, ttl_seconds: int = 3600, max_entries: int = 5_000) -> None:
        self._lock = threading.Lock()
        self._ttl_seconds = ttl_seconds
        self._max_entries = max_entries
        self._entries: dict[tuple[int, str, str], tuple[float, dict[str, Any]]] = {}

    def get(self, telegram_user_id: int, action: str, key: str) -> dict[str, Any] | None:
        now = time.time()
        composite = (telegram_user_id, action, key)
        with self._lock:
            item = self._entries.get(composite)
            if item is None:
                return None
            exp, payload = item
            if exp <= now:
                del self._entries[composite]
                return None
            return dict(payload)

    def put(self, telegram_user_id: int, action: str, key: str, payload: dict[str, Any]) -> None:
        now = time.time()
        composite = (telegram_user_id, action, key)
        with self._lock:
            if len(self._entries) >= self._max_entries:
                expired = [k for k, (exp, _) in self._entries.items() if exp <= now]
                for k in expired:
                    del self._entries[k]
            self._entries[composite] = (now + self._ttl_seconds, dict(payload))


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
    nonce_store: NonceStore,
) -> VerifiedActor:
    """Verify signed X-Actor-Assertion JWT with anti-replay JTI enforcement."""
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

    if not nonce_store.consume(f"actor:{jti}", float(exp)):
        raise SecurityError("REPLAYED_ACTOR_ASSERTION", "Aserción de actor ya utilizada (replay denegado).", status_code=401)

    return VerifiedActor(telegram_user_id=raw_tg_id, jti=jti)


def verify_approval_proof(
    proof: str | None,
    *,
    secret: str,
    expected_telegram_user_id: int,
    expected_action: str,
    expected_payload: dict[str, Any],
    max_ttl_seconds: int,
    nonce_store: NonceStore,
) -> dict[str, Any]:
    """Verify signed, scoped, short-lived, one-use approval_proof for sensitive writes."""
    key = _require_configured_secret(secret, "MCP_APPROVAL_SIGNING_SECRET")
    if not proof or not proof.strip():
        raise SecurityError(
            "APPROVAL_REQUIRED",
            f"La acción sensible '{expected_action}' requiere approval_proof firmado.",
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
    if not jti or not nonce_store.consume(f"approval:{jti}", float(exp)):
        raise SecurityError("APPROVAL_REPLAYED", "approval_proof ya fue utilizado (un solo uso).", status_code=403)

    return claims


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
