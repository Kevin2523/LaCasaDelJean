"""Export all ORM models so Alembic and SQLAlchemy metadata discover them."""

from app.models.audit import AuditEvent
from app.models.auth import Role, User
from app.models.catalog import Category, Image, Price, Product, Variant
from app.models.enums import PublicationStatus, StockDirection, StockMovementType
from app.models.inventory import StockBalance, StockMovement

__all__ = [
    "AuditEvent",
    "Category",
    "Image",
    "Price",
    "Product",
    "PublicationStatus",
    "Role",
    "StockBalance",
    "StockDirection",
    "StockMovement",
    "StockMovementType",
    "User",
    "Variant",
]
