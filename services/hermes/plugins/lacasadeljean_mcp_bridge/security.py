"""Fail-closed cryptographic helpers for the Hermes -> MCP trusted bridge."""

from __future__ import annotations

import hashlib
import hmac
import json
import time
import uuid
from decimal import Decimal, InvalidOperation
from typing import Any

import jwt

ACTOR_ISSUER = "hermes-telegram-bridge"
APPROVAL_ISSUER = "hermes-telegram-approval"
MCP_AUDIENCE = "lacasadeljean-mcp"

READ_ONLY_TOOLS: frozenset[str] = frozenset(
    {
        "search_products",
        "get_product_detail",
        "get_variant_stock",
    }
)

WRITE_TOOLS: frozenset[str] = frozenset(
    {
        "create_product_draft",
        "create_variant",
        "attach_product_photo",
        "set_product_price",
        "record_stock_movement",
        "set_product_publication_status",
    }
)

ALLOWED_MCP_TOOLS: frozenset[str] = READ_ONLY_TOOLS | WRITE_TOOLS

# Argument names that the LLM must NEVER be allowed to supply (anti-spoofing).
FORBIDDEN_MODEL_ARGUMENTS: frozenset[str] = frozenset(
    {
        "telegram_user_id",
        "user_id",
        "actor_id",
        "actor",
        "role",
        "roles",
        "x_actor_assertion",
        "X-Actor-Assertion",
        "authorization",
        "Authorization",
    }
)


class BridgeSecurityError(Exception):
    """Raised when identity, allowlist, anti-spoofing, or approval verification fails."""

    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code
        self.message = message


def require_secret(secret: str | None, name: str) -> str:
    """Fail closed if a required signing/shared secret is missing or placeholder."""
    cleaned = (secret or "").strip()
    if not cleaned or cleaned.startswith("CHANGE_ME"):
        raise BridgeSecurityError("MISCONFIGURED_SECRET", f"{name} no está configurado.")
    return cleaned


def parse_allowed_telegram_users(raw: str | None) -> frozenset[int]:
    """Parse comma-separated numeric Telegram user IDs; fail closed on invalid entries."""
    if not raw or not raw.strip():
        return frozenset()
    allowed: set[int] = set()
    for part in raw.split(","):
        item = part.strip()
        if not item:
            continue
        if not item.isdigit():
            raise BridgeSecurityError(
                "INVALID_ALLOWLIST",
                f"TELEGRAM_ALLOWED_USERS contiene un ID no numérico: {item!r}",
            )
        uid = int(item)
        if uid <= 0:
            raise BridgeSecurityError(
                "INVALID_ALLOWLIST",
                "TELEGRAM_ALLOWED_USERS solo admite IDs numéricos positivos.",
            )
        allowed.add(uid)
    return frozenset(allowed)


def canonical_payload_hash(payload: dict[str, Any]) -> str:
    """Compute deterministic SHA-256 hex digest matching services/mcp/app/security.py."""
    canonical = json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def build_scoped_payload(tool_name: str, arguments: dict[str, Any]) -> dict[str, Any]:
    """Construct the exact scoped payload expected by services/mcp for approval_proof."""
    if tool_name == "create_product_draft":
        return {
            "category_id": arguments["category_id"],
            "sku": arguments["sku"],
            "name": arguments["name"],
            "slug": arguments["slug"],
            "description": arguments.get("description"),
        }
    if tool_name == "create_variant":
        return {
            "product_id": arguments["product_id"],
            "sku": arguments["sku"],
            "size": arguments["size"],
            "color": arguments["color"],
            "color_hex": arguments.get("color_hex"),
            "barcode": arguments.get("barcode"),
        }
    if tool_name == "attach_product_photo":
        image_b64 = str(arguments["image_base64"])
        return {
            "product_id": arguments["product_id"],
            "variant_id": arguments.get("variant_id"),
            "filename": arguments["filename"],
            "content_type": arguments["content_type"],
            "image_b64_sha256": hashlib.sha256(image_b64.encode("utf-8")).hexdigest(),
            "display_order": int(arguments.get("display_order", 0)),
            "is_primary": bool(arguments.get("is_primary", False)),
        }
    if tool_name == "set_product_price":
        try:
            normalized_amount = f"{Decimal(str(arguments['amount_pab'])):.2f}"
            raw_compare = arguments.get("compare_at_pab")
            normalized_compare = f"{Decimal(str(raw_compare)):.2f}" if raw_compare is not None else None
        except (InvalidOperation, KeyError) as exc:
            raise BridgeSecurityError("INVALID_PRICE", f"Monto PAB inválido: {exc}") from exc
        return {
            "product_id": arguments["product_id"],
            "variant_id": arguments.get("variant_id"),
            "amount_pab": normalized_amount,
            "compare_at_pab": normalized_compare,
            "currency": "PAB",
        }
    if tool_name == "record_stock_movement":
        idem = str(arguments.get("idempotency_key") or "").strip()
        if not idem:
            raise BridgeSecurityError(
                "IDEMPOTENCY_KEY_REQUIRED",
                "idempotency_key es obligatorio para record_stock_movement.",
            )
        return {
            "variant_id": arguments["variant_id"],
            "direction": arguments["direction"],
            "movement_type": arguments["movement_type"],
            "quantity": int(arguments["quantity"]),
            "idempotency_key": idem,
        }
    if tool_name == "set_product_publication_status":
        return {
            "product_id": arguments["product_id"],
            "publication_status": arguments["publication_status"],
        }
    raise BridgeSecurityError("UNSUPPORTED_WRITE_TOOL", f"Herramienta de escritura no reconocida: {tool_name}")


def sign_actor_assertion(
    *,
    telegram_user_id: int,
    secret: str,
    ttl_seconds: int = 30,
    jti: str | None = None,
    iat: int | None = None,
) -> str:
    """Sign a short-lived, single-use X-Actor-Assertion JWT for services/mcp."""
    key = require_secret(secret, "MCP_ACTOR_ASSERTION_SECRET")
    if not isinstance(telegram_user_id, int) or isinstance(telegram_user_id, bool) or telegram_user_id <= 0:
        raise BridgeSecurityError("INVALID_ACTOR_ID", "telegram_user_id debe ser un entero positivo.")
    if ttl_seconds <= 0 or ttl_seconds > 60:
        raise BridgeSecurityError("INVALID_ACTOR_TTL", "TTL de X-Actor-Assertion debe estar entre 1 y 60 segundos.")

    issued = int(time.time()) if iat is None else iat
    claims = {
        "iss": ACTOR_ISSUER,
        "aud": MCP_AUDIENCE,
        "sub": f"tg:{telegram_user_id}",
        "telegram_user_id": telegram_user_id,
        "jti": jti or str(uuid.uuid4()),
        "iat": issued,
        "exp": issued + ttl_seconds,
    }
    return jwt.encode(claims, key, algorithm="HS256")


def sign_human_approval_proof(
    *,
    telegram_user_id: int,
    action: str,
    arguments: dict[str, Any],
    secret: str,
    ttl_seconds: int = 60,
    jti: str | None = None,
    iat: int | None = None,
) -> str:
    """Issue a scoped, short-lived approval_proof ONLY after explicit human confirmation."""
    key = require_secret(secret, "MCP_APPROVAL_SIGNING_SECRET")
    if action not in WRITE_TOOLS:
        raise BridgeSecurityError("INVALID_APPROVAL_ACTION", f"Acción no aprobable: {action}")
    if ttl_seconds <= 0 or ttl_seconds > 120:
        raise BridgeSecurityError("INVALID_APPROVAL_TTL", "TTL de approval_proof debe estar entre 1 y 120 segundos.")

    scoped_payload = build_scoped_payload(action, arguments)
    issued = int(time.time()) if iat is None else iat
    claims = {
        "iss": APPROVAL_ISSUER,
        "aud": MCP_AUDIENCE,
        "telegram_user_id": telegram_user_id,
        "action": action,
        "payload_sha256": canonical_payload_hash(scoped_payload),
        "jti": jti or str(uuid.uuid4()),
        "iat": issued,
        "exp": issued + ttl_seconds,
    }
    return jwt.encode(claims, key, algorithm="HS256")


def verify_approval_proof_local(
    proof: str | None,
    *,
    secret: str,
    expected_telegram_user_id: int,
    expected_action: str,
    arguments: dict[str, Any],
    max_ttl_seconds: int = 120,
) -> dict[str, Any]:
    """Fail-closed local verification of approval_proof before forwarding to MCP."""
    key = require_secret(secret, "MCP_APPROVAL_SIGNING_SECRET")
    if not proof or not proof.strip():
        raise BridgeSecurityError(
            "APPROVAL_REQUIRED",
            f"La acción '{expected_action}' requiere confirmación explícita del operador (approval_proof).",
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
        raise BridgeSecurityError("INVALID_APPROVAL_PROOF", f"approval_proof inválido o expirado: {exc}") from exc

    iat = int(claims["iat"])
    exp = int(claims["exp"])
    if exp - iat <= 0 or (exp - iat) > max_ttl_seconds:
        raise BridgeSecurityError("INVALID_APPROVAL_TTL", "TTL de approval_proof fuera de rango.")

    if claims["telegram_user_id"] != expected_telegram_user_id:
        raise BridgeSecurityError("APPROVAL_ACTOR_MISMATCH", "approval_proof pertenece a otro operador.")

    if claims["action"] != expected_action:
        raise BridgeSecurityError("APPROVAL_ACTION_MISMATCH", "approval_proof no coincide con la herramienta solicitada.")

    scoped_payload = build_scoped_payload(expected_action, arguments)
    expected_hash = canonical_payload_hash(scoped_payload)
    if not hmac.compare_digest(str(claims["payload_sha256"]), expected_hash):
        raise BridgeSecurityError(
            "APPROVAL_SCOPE_MISMATCH",
            "approval_proof no coincide con los parámetros exactos de la propuesta confirmada.",
        )

    return claims
