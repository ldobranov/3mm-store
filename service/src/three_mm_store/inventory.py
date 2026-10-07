"""Store-owned inventory queries and transactional adjustments."""

from __future__ import annotations

import re
import secrets

from .idempotency import run_idempotent


PRODUCT_ID = re.compile(r"^prd_[0-9a-f]{32}$")
LANGUAGE_CODE = re.compile(r"^[a-z]{2,3}(?:-[a-z0-9]{2,8})*$")

MAX_SEARCH = 120
MAX_REASON = 240
MAX_OFFSET = 1_000_000
MAX_DELTA = 1_000_000_000


class InventoryService:
    def __init__(self, application) -> None:
        self.application = application

    @staticmethod
    def _known_fields(
        payload: dict[str, object],
        allowed: set[str],
    ) -> None:
        if set(payload) - allowed:
            raise ValueError("Inventory request contains unknown fields")

    @staticmethod
    def _text(
        value: object,
        label: str,
        *,
        maximum: int,
        allow_empty: bool = False,
    ) -> str:
        if not isinstance(value, str):
            raise ValueError(f"{label} must be text")
        normalized = value.strip()
        if not allow_empty and not normalized:
            raise ValueError(f"{label} is required")
        if len(normalized) > maximum:
            raise ValueError(f"{label} is too long")
        return normalized

    @classmethod
    def _product_id(cls, value: object) -> str:
        if not isinstance(value, str) or PRODUCT_ID.fullmatch(value) is None:
            raise ValueError("Product ID is invalid")
        return value

    @classmethod
    def _language_code(cls, value: object) -> str:
        code = cls._text(value, "Language code", maximum=35).lower()
        if LANGUAGE_CODE.fullmatch(code) is None:
            raise ValueError("Language code is invalid")
        return code

    @staticmethod
    def _delta(value: object) -> int:
        if (
            not isinstance(value, int)
            or isinstance(value, bool)
            or value == 0
            or not -MAX_DELTA <= value <= MAX_DELTA
        ):
            raise ValueError("Inventory delta is invalid")
        return value

    @staticmethod
    def _availability(track_inventory: bool, stock_on_hand: int) -> str:
        if not track_inventory:
            return "untracked"
        return "in_stock" if stock_on_hand > 0 else "out_of_stock"

    @classmethod
    def _row_to_item(cls, row) -> dict[str, object]:
        stock = int(row["stock_on_hand"])
        tracked = bool(row["track_inventory"])
        return {
            "product_id": str(row["id"]),
            "sku": str(row["sku"]),
            "slug": str(row["slug"]),
            "name": str(row["name"]),
            "product_status": str(row["product_status"]),
            "track_inventory": tracked,
            "stock_on_hand": stock,
            "availability": cls._availability(tracked, stock),
            "updated_at": str(row["inventory_updated_at"]),
        }

    def list_inventory(
        self,
        payload: dict[str, object],
        _context,
    ) -> dict[str, object]:
        self._known_fields(
            payload,
            {
                "search",
                "status",
                "availability",
                "sort",
                "limit",
                "offset",
                "language_code",
            },
        )

        search = self._text(
            payload.get("search", ""),
            "Inventory search",
            maximum=MAX_SEARCH,
            allow_empty=True,
        )
        status = payload.get("status")
        if status is not None and status not in {
            "draft",
            "active",
            "archived",
        }:
            raise ValueError("Product status filter is invalid")

        availability = payload.get("availability")
        if availability is not None and availability not in {
            "in_stock",
            "out_of_stock",
            "untracked",
        }:
            raise ValueError("Inventory availability filter is invalid")

        language_code = (
            self._language_code(payload["language_code"])
            if "language_code" in payload
            else None
        )

        sort = payload.get("sort", "updated_desc")
        sort_sql = {
            "updated_desc": "inventory_updated_at DESC, p.id ASC",
            "name_asc": "name_value ASC, p.id ASC",
            "sku_asc": "p.sku ASC, p.id ASC",
            "stock_asc": "stock_on_hand ASC, p.id ASC",
            "stock_desc": "stock_on_hand DESC, p.id ASC",
        }.get(sort)
        if sort_sql is None:
            raise ValueError("Inventory sort is invalid")

        limit_value = payload.get("limit", 20)
        offset_value = payload.get("offset", 0)
        if (
            not isinstance(limit_value, int)
            or isinstance(limit_value, bool)
            or not 1 <= limit_value <= 100
        ):
            raise ValueError("Inventory list limit is invalid")
        if (
            not isinstance(offset_value, int)
            or isinstance(offset_value, bool)
            or not 0 <= offset_value <= MAX_OFFSET
        ):
            raise ValueError("Inventory list offset is invalid")

        join_translation = ""
        select_name = "p.name"
        parameters: list[object] = []
        if language_code is not None:
            join_translation = """
                LEFT JOIN product_translations t
                  ON t.product_id = p.id
                 AND t.language_code = ?
            """
            select_name = "COALESCE(t.name, p.name)"
            parameters.append(language_code)

        where: list[str] = []
        where_parameters: list[object] = []
        if status is not None:
            where.append("p.status = ?")
            where_parameters.append(status)
        if availability == "untracked":
            where.append("p.track_inventory = 0")
        elif availability == "in_stock":
            where.append("p.track_inventory = 1 AND COALESCE(i.stock_on_hand, 0) > 0")
        elif availability == "out_of_stock":
            where.append("p.track_inventory = 1 AND COALESCE(i.stock_on_hand, 0) = 0")
        if search:
            where.append(
                f"(store_casefold({select_name}) LIKE ? "
                "OR store_casefold(p.sku) LIKE ? "
                "OR store_casefold(p.slug) LIKE ?)"
            )
            pattern = f"%{search.casefold()}%"
            where_parameters.extend((pattern, pattern, pattern))

        where_sql = f" WHERE {' AND '.join(where)}" if where else ""
        query_parameters = [*parameters, *where_parameters]

        select_sql = f"""
            SELECT
                p.id,
                p.sku,
                p.slug,
                {select_name} AS name_value,
                {select_name} AS name,
                p.status AS product_status,
                p.track_inventory,
                COALESCE(i.stock_on_hand, 0) AS stock_on_hand,
                COALESCE(i.updated_at, p.updated_at) AS inventory_updated_at
            FROM products p
            LEFT JOIN inventory i ON i.product_id = p.id
            {join_translation}
            {where_sql}
            ORDER BY {sort_sql}
            LIMIT ? OFFSET ?
        """
        count_sql = f"""
            SELECT COUNT(*)
            FROM products p
            LEFT JOIN inventory i ON i.product_id = p.id
            {join_translation}
            {where_sql}
        """

        with self.application.storage.transaction() as connection:
            connection.create_function(
                "store_casefold",
                1,
                lambda value: str(value).casefold(),
                deterministic=True,
            )
            total = int(
                connection.execute(
                    count_sql,
                    query_parameters,
                ).fetchone()[0]
            )
            rows = connection.execute(
                select_sql,
                [
                    *query_parameters,
                    limit_value,
                    offset_value,
                ],
            ).fetchall()

        return {
            "items": [self._row_to_item(row) for row in rows],
            "total": total,
            "limit": limit_value,
            "offset": offset_value,
        }

    def adjust(
        self,
        payload: dict[str, object],
        context,
    ) -> dict[str, object]:
        self._known_fields(payload, {"product_id", "delta", "reason"})
        product_id = self._product_id(payload.get("product_id"))
        delta = self._delta(payload.get("delta"))
        reason = self._text(
            payload.get("reason"),
            "Inventory adjustment reason",
            maximum=MAX_REASON,
        )

        normalized_payload = {
            "product_id": product_id,
            "delta": delta,
            "reason": reason,
        }

        def mutation(connection):
            product = connection.execute(
                """
                SELECT id, updated_at
                FROM products
                WHERE id = ?
                """,
                (product_id,),
            ).fetchone()
            if product is None:
                raise ValueError("Product was not found")

            connection.execute(
                """
                INSERT OR IGNORE INTO inventory(
                    product_id, stock_on_hand, updated_at
                ) VALUES (?, 0, ?)
                """,
                (product_id, str(product["updated_at"])),
            )

            inventory = connection.execute(
                """
                SELECT stock_on_hand
                FROM inventory
                WHERE product_id = ?
                """,
                (product_id,),
            ).fetchone()
            if inventory is None:
                raise ValueError("Inventory row is unavailable")

            stock_before = int(inventory["stock_on_hand"])
            stock_after = stock_before + delta
            if stock_after < 0:
                raise ValueError("Inventory adjustment would make stock negative")

            now = self.application.clock.now().isoformat()
            adjustment_id = f"adj_{secrets.token_hex(16)}"

            connection.execute(
                """
                UPDATE inventory
                SET stock_on_hand = ?, updated_at = ?
                WHERE product_id = ?
                """,
                (stock_after, now, product_id),
            )
            connection.execute(
                """
                INSERT INTO inventory_adjustments(
                    id,
                    product_id,
                    delta,
                    stock_before,
                    stock_after,
                    reason,
                    created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    adjustment_id,
                    product_id,
                    delta,
                    stock_before,
                    stock_after,
                    reason,
                    now,
                ),
            )

            return {
                "adjustment": {
                    "adjustment_id": adjustment_id,
                    "product_id": product_id,
                    "delta": delta,
                    "stock_before": stock_before,
                    "stock_after": stock_after,
                    "reason": reason,
                    "created_at": now,
                }
            }

        return run_idempotent(
            self.application,
            "inventory_adjust",
            normalized_payload,
            context,
            mutation,
        )
