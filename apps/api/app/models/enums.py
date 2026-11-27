"""Domain enumerations shared across models and services."""

from enum import StrEnum


class PublicationStatus(StrEnum):
    """Explicit publication lifecycle status for products and variants."""

    DRAFT = "draft"
    PUBLISHED = "published"
    ARCHIVED = "archived"


class StockDirection(StrEnum):
    """Direction of an inventory movement."""

    IN = "in"
    OUT = "out"


class StockMovementType(StrEnum):
    """Business reason for an inventory movement."""

    INITIAL_LOAD = "initial_load"
    RESTOCK = "restock"
    SALE = "sale"
    RETURN = "return"
    ADJUSTMENT = "adjustment"
    DAMAGE = "damage"
