"""Store-owned public catalog renderer for the 3mm Public Web Runtime."""

from __future__ import annotations

from html import escape
import json
import re
from urllib.parse import quote


LANGUAGE_CODE = re.compile(r"^[a-z]{2,3}(?:-[a-z0-9]{2,8})*$")
SLUG = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")

MAX_PUBLIC_CATEGORIES = 50
MAX_PUBLIC_PRODUCTS = 100

ZERO_DECIMAL_CURRENCIES = {
    "BIF", "CLP", "DJF", "GNF", "ISK", "JPY", "KMF",
    "KRW", "PYG", "RWF", "UGX", "UYI", "VND", "VUV",
    "XAF", "XOF", "XPF",
}
THREE_DECIMAL_CURRENCIES = {
    "BHD", "IQD", "JOD", "KWD", "LYD", "OMR", "TND",
}


class PublicCatalogRenderer:
    def __init__(self, application) -> None:
        self.application = application

    @staticmethod
    def _read_setting(connection, key: str, default: str) -> str:
        row = connection.execute(
            "SELECT value_json FROM store_settings WHERE key = ?",
            (key,),
        ).fetchone()
        if row is None:
            return default
        try:
            value = json.loads(str(row[0]))
        except (TypeError, ValueError) as exc:
            raise ValueError("Stored Store setting is invalid") from exc
        if not isinstance(value, str):
            raise ValueError("Stored Store setting is invalid")
        return value

    @staticmethod
    def _normalize_language(value: object) -> str | None:
        if not isinstance(value, str):
            return None
        normalized = value.strip().lower().replace("_", "-")
        if LANGUAGE_CODE.fullmatch(normalized) is None:
            return None
        return normalized

    @classmethod
    def _query_language(cls, payload: dict[str, object]) -> str | None:
        query = payload.get("query")
        if not isinstance(query, dict):
            return None
        values = query.get("lang")
        if not isinstance(values, (list, tuple)) or len(values) != 1:
            return None
        return cls._normalize_language(values[0])

    @classmethod
    def _accept_languages(cls, payload: dict[str, object]) -> list[str]:
        headers = payload.get("headers")
        if not isinstance(headers, dict):
            return []
        value = headers.get("accept-language")
        if not isinstance(value, str):
            return []

        weighted: list[tuple[float, int, str]] = []
        for index, item in enumerate(value.split(",")[:32]):
            part = item.strip()
            if not part:
                continue
            pieces = [piece.strip() for piece in part.split(";")]
            code = cls._normalize_language(pieces[0])
            if code is None:
                continue
            quality = 1.0
            for parameter in pieces[1:]:
                if not parameter.lower().startswith("q="):
                    continue
                try:
                    quality = float(parameter[2:])
                except ValueError:
                    quality = 0.0
            if quality <= 0 or quality > 1:
                continue
            weighted.append((quality, index, code))

        weighted.sort(key=lambda item: (-item[0], item[1]))
        return [code for _quality, _index, code in weighted]

    @staticmethod
    def _available_languages(connection) -> list[str]:
        rows = connection.execute(
            """
            SELECT language_code FROM store_translations
            UNION
            SELECT language_code FROM category_translations
            UNION
            SELECT language_code FROM product_translations
            ORDER BY language_code
            """
        ).fetchall()
        return [str(row[0]) for row in rows]

    @classmethod
    def _select_language(
        cls,
        connection,
        payload: dict[str, object],
    ) -> tuple[str, bool]:
        available = cls._available_languages(connection)
        explicit = cls._query_language(payload)
        if explicit is not None:
            if explicit in available or not available:
                return explicit, True
            primary = explicit.split("-", 1)[0]
            if primary in available:
                return primary, True

        for candidate in cls._accept_languages(payload):
            if candidate in available:
                return candidate, False
            primary = candidate.split("-", 1)[0]
            if primary in available:
                return primary, False

        if "en" in available:
            return "en", False
        if available:
            return available[0], False
        return explicit or "en", explicit is not None

    @staticmethod
    def _translation_candidates(
        requested: str,
        legacy_language: str | None,
        available: list[str],
    ) -> list[str]:
        result: list[str] = []
        for value in (
            requested,
            requested.split("-", 1)[0],
            "en",
            legacy_language,
            *available,
        ):
            if value and value not in result:
                result.append(value)
        return result

    @classmethod
    def _store_translation(
        cls,
        connection,
        language: str,
    ) -> dict[str, str]:
        rows = connection.execute(
            """
            SELECT language_code, store_name, home_title,
                   home_description, meta_title, meta_description
            FROM store_translations
            ORDER BY language_code
            """
        ).fetchall()
        by_code = {str(row["language_code"]): row for row in rows}
        candidates = cls._translation_candidates(
            language,
            None,
            list(by_code),
        )

        def value(field: str) -> str:
            for code in candidates:
                row = by_code.get(code)
                if row is None:
                    continue
                item = str(row[field]).strip()
                if item:
                    return item
            return ""

        return {
            "store_name": value("store_name"),
            "home_title": value("home_title"),
            "home_description": value("home_description"),
            "meta_title": value("meta_title"),
            "meta_description": value("meta_description"),
        }

    @classmethod
    def _entity_translation(
        cls,
        connection,
        *,
        table: str,
        id_column: str,
        entity_id: str,
        language: str,
        legacy_language: str | None,
        fields: tuple[str, ...],
        legacy: dict[str, str],
    ) -> dict[str, str]:
        if table not in {"category_translations", "product_translations"}:
            raise ValueError("Public translation table is invalid")
        if id_column not in {"category_id", "product_id"}:
            raise ValueError("Public translation key is invalid")

        columns = ", ".join(("language_code", *fields))
        rows = connection.execute(
            f"""
            SELECT {columns}
            FROM {table}
            WHERE {id_column} = ?
            ORDER BY language_code
            """,
            (entity_id,),
        ).fetchall()
        by_code = {str(row["language_code"]): row for row in rows}
        candidates = cls._translation_candidates(
            language,
            legacy_language,
            list(by_code),
        )

        result: dict[str, str] = {}
        for field in fields:
            selected = ""
            for code in candidates:
                row = by_code.get(code)
                if row is None:
                    continue
                value = str(row[field])
                if value.strip():
                    selected = value
                    break
            if not selected:
                selected = legacy.get(field, "")
            result[field] = selected
        return result

    @staticmethod
    def _money(price_minor: int, currency: str) -> str:
        digits = (
            0
            if currency in ZERO_DECIMAL_CURRENCIES
            else 3
            if currency in THREE_DECIMAL_CURRENCIES
            else 2
        )
        if digits == 0:
            amount = str(price_minor)
        else:
            divisor = 10 ** digits
            amount = f"{price_minor // divisor}.{price_minor % divisor:0{digits}d}"
        return f"{currency} {amount}"

    @staticmethod
    def _language_suffix(language: str, explicit: bool) -> str:
        if not explicit:
            return ""
        return "?lang=" + quote(language, safe="-")

    @classmethod
    def _canonical_url(
        cls,
        base_url: str,
        path: str,
        language: str,
        explicit_language: bool,
    ) -> str:
        if not base_url:
            return ""
        return base_url.rstrip("/") + path + cls._language_suffix(
            language,
            explicit_language,
        )

    @staticmethod
    def _meta_description(value: str) -> str:
        normalized = " ".join(value.split())
        if len(normalized) <= 320:
            return normalized
        return normalized[:317].rstrip() + "..."

    @staticmethod
    def _plain_text(value: str) -> str:
        return escape(value).replace("\n", "<br>")

    @classmethod
    def _document(
        cls,
        *,
        language: str,
        title: str,
        description: str,
        store_name: str,
        body: str,
        canonical: str,
        path: str,
        available_languages: list[str],
    ) -> str:
        safe_language = escape(language, quote=True)
        safe_title = escape(title)
        safe_description = escape(cls._meta_description(description), quote=True)
        safe_store = escape(store_name or "Store")

        canonical_markup = (
            f'<link rel="canonical" href="{escape(canonical, quote=True)}">'
            if canonical
            else ""
        )
        language_links = " ".join(
            (
                f'<a href="{escape(path + "?lang=" + quote(code, safe="-"), quote=True)}" '
                f'hreflang="{escape(code, quote=True)}">'
                f'{escape(code.upper())}</a>'
            )
            for code in available_languages
        )
        language_nav = (
            f'<nav class="languages" aria-label="Languages">{language_links}</nav>'
            if language_links
            else ""
        )

        return (
            '<!doctype html>'
            f'<html lang="{safe_language}"><head>'
            '<meta charset="utf-8">'
            '<meta name="viewport" content="width=device-width,initial-scale=1">'
            f"<title>{safe_title}</title>"
            f'<meta name="description" content="{safe_description}">'
            f"{canonical_markup}"
            "<style>"
            ":root{color-scheme:light dark;font-family:system-ui,-apple-system,sans-serif}"
            "body{max-width:72rem;margin:0 auto;padding:1.5rem;line-height:1.55}"
            "header{display:flex;gap:1rem;justify-content:space-between;align-items:center;"
            "border-bottom:1px solid color-mix(in srgb,currentColor 20%,transparent);padding-bottom:1rem}"
            "a{color:inherit}.brand{text-decoration:none;font-weight:700;font-size:1.2rem}"
            ".languages{display:flex;gap:.65rem;flex-wrap:wrap}"
            "main{padding:1.5rem 0}.grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(15rem,1fr));gap:1rem}"
            ".card{border:1px solid color-mix(in srgb,currentColor 20%,transparent);border-radius:.75rem;padding:1rem}"
            ".price{font-weight:700}.muted{opacity:.72}.description{max-width:52rem}"
            "ul.clean{list-style:none;padding:0}.clean li+li{margin-top:.6rem}"
            "</style>"
            "</head><body>"
            "<header>"
            f'<a class="brand" href="/">{safe_store}</a>'
            f"{language_nav}"
            "</header>"
            f"<main>{body}</main>"
            "</body></html>"
        )

    @classmethod
    def _response(
        cls,
        *,
        body: str,
        language: str,
    ) -> dict[str, object]:
        return {
            "status": 200,
            "content_type": "text/html; charset=utf-8",
            "headers": {
                "Cache-Control": "public, max-age=60",
                "Content-Language": language,
                "Vary": "Accept-Language",
            },
            "body": body,
        }

    @staticmethod
    def _not_found(language: str) -> dict[str, object]:
        body = (
            '<!doctype html><html lang="'
            + escape(language, quote=True)
            + '"><head><meta charset="utf-8"><title>404</title></head>'
            '<body><main><h1>404</h1></main></body></html>'
        )
        return {
            "status": 404,
            "content_type": "text/html; charset=utf-8",
            "headers": {
                "Cache-Control": "no-store",
                "Content-Language": language,
                "Vary": "Accept-Language",
            },
            "body": body,
        }

    @staticmethod
    def _load_active_category(connection, slug: str):
        return connection.execute(
            """
            SELECT id, slug, name, description, legacy_language_code
            FROM categories
            WHERE slug = ? AND status = 'active'
            """,
            (slug,),
        ).fetchone()

    @staticmethod
    def _load_active_product(connection, slug: str):
        return connection.execute(
            """
            SELECT p.id, p.sku, p.slug, p.name, p.short_description,
                   p.description, p.price_minor, p.track_inventory,
                   p.legacy_language_code,
                   COALESCE(i.stock_on_hand, 0) AS stock_on_hand
            FROM products p
            LEFT JOIN inventory i ON i.product_id = p.id
            WHERE p.slug = ? AND p.status = 'active'
            """,
            (slug,),
        ).fetchone()

    @staticmethod
    def _historical_target(connection, entity_type: str, slug: str):
        row = connection.execute(
            """
            SELECT h.entity_id,
                   CASE
                     WHEN h.entity_type = 'product' THEN p.slug
                     ELSE c.slug
                   END AS current_slug,
                   CASE
                     WHEN h.entity_type = 'product' THEN p.status
                     ELSE c.status
                   END AS current_status
            FROM slug_history h
            LEFT JOIN products p
              ON h.entity_type = 'product' AND p.id = h.entity_id
            LEFT JOIN categories c
              ON h.entity_type = 'category' AND c.id = h.entity_id
            WHERE h.entity_type = ? AND h.old_slug = ?
            """,
            (entity_type, slug),
        ).fetchone()
        if row is None or str(row["current_status"]) != "active":
            return None
        current_slug = row["current_slug"]
        return str(current_slug) if current_slug is not None else None

    @classmethod
    def _category_content(
        cls,
        connection,
        row,
        language: str,
    ) -> dict[str, str]:
        return cls._entity_translation(
            connection,
            table="category_translations",
            id_column="category_id",
            entity_id=str(row["id"]),
            language=language,
            legacy_language=(
                str(row["legacy_language_code"])
                if row["legacy_language_code"] is not None
                else None
            ),
            fields=(
                "name",
                "description",
                "meta_title",
                "meta_description",
            ),
            legacy={
                "name": str(row["name"]),
                "description": str(row["description"]),
                "meta_title": "",
                "meta_description": "",
            },
        )

    @classmethod
    def _product_content(
        cls,
        connection,
        row,
        language: str,
    ) -> dict[str, str]:
        return cls._entity_translation(
            connection,
            table="product_translations",
            id_column="product_id",
            entity_id=str(row["id"]),
            language=language,
            legacy_language=(
                str(row["legacy_language_code"])
                if row["legacy_language_code"] is not None
                else None
            ),
            fields=(
                "name",
                "short_description",
                "description",
                "meta_title",
                "meta_description",
            ),
            legacy={
                "name": str(row["name"]),
                "short_description": str(row["short_description"]),
                "description": str(row["description"]),
                "meta_title": "",
                "meta_description": "",
            },
        )

    @classmethod
    def _product_card(
        cls,
        row,
        content: dict[str, str],
        currency: str,
        language: str,
        explicit_language: bool,
    ) -> str:
        href = (
            "/products/"
            + quote(str(row["slug"]), safe="-")
            + cls._language_suffix(language, explicit_language)
        )
        summary = content["short_description"] or content["description"]
        return (
            '<article class="card">'
            f'<h2><a href="{escape(href, quote=True)}">{escape(content["name"])}</a></h2>'
            + (
                f'<p>{cls._plain_text(summary)}</p>'
                if summary
                else ""
            )
            + f'<p class="price">{escape(cls._money(int(row["price_minor"]), currency))}</p>'
            "</article>"
        )

    def _render_home(
        self,
        connection,
        *,
        language: str,
        explicit_language: bool,
    ) -> dict[str, object]:
        store = self._store_translation(connection, language)
        store_name = store["store_name"] or "Store"
        title = store["meta_title"] or store["home_title"] or store_name
        description = store["meta_description"] or store["home_description"]
        currency = self._read_setting(connection, "currency", "EUR")
        public_base_url = self._read_setting(
            connection,
            "public_base_url",
            "",
        )

        categories = connection.execute(
            """
            SELECT id, slug, name, description, legacy_language_code
            FROM categories
            WHERE status = 'active'
            ORDER BY sort_order, name, id
            LIMIT ?
            """,
            (MAX_PUBLIC_CATEGORIES,),
        ).fetchall()
        products = connection.execute(
            """
            SELECT p.id, p.sku, p.slug, p.name, p.short_description,
                   p.description, p.price_minor, p.track_inventory,
                   p.legacy_language_code,
                   COALESCE(i.stock_on_hand, 0) AS stock_on_hand
            FROM products p
            LEFT JOIN inventory i ON i.product_id = p.id
            WHERE p.status = 'active'
            ORDER BY p.updated_at DESC, p.id
            LIMIT ?
            """,
            (20,),
        ).fetchall()

        category_items = []
        for row in categories:
            content = self._category_content(connection, row, language)
            href = (
                "/categories/"
                + quote(str(row["slug"]), safe="-")
                + self._language_suffix(language, explicit_language)
            )
            category_items.append(
                f'<li><a href="{escape(href, quote=True)}">'
                f'{escape(content["name"])}</a></li>'
            )

        product_cards = [
            self._product_card(
                row,
                self._product_content(connection, row, language),
                currency,
                language,
                explicit_language,
            )
            for row in products
        ]

        body = (
            f"<h1>{escape(store['home_title'] or store_name)}</h1>"
            + (
                f'<p class="description">{self._plain_text(store["home_description"])}</p>'
                if store["home_description"]
                else ""
            )
            + (
                '<ul class="clean">' + "".join(category_items) + "</ul>"
                if category_items
                else ""
            )
            + (
                '<section class="grid">' + "".join(product_cards) + "</section>"
                if product_cards
                else ""
            )
        )
        available_languages = self._available_languages(connection)
        document = self._document(
            language=language,
            title=title,
            description=description,
            store_name=store_name,
            body=body,
            canonical=self._canonical_url(
                public_base_url,
                "/",
                language,
                explicit_language,
            ),
            path="/",
            available_languages=available_languages,
        )
        return self._response(body=document, language=language)

    def _render_category(
        self,
        connection,
        *,
        slug: str,
        language: str,
        explicit_language: bool,
    ) -> dict[str, object]:
        category = self._load_active_category(connection, slug)
        if category is None:
            target = self._historical_target(
                connection,
                "category",
                slug,
            )
            if target is not None:
                return {
                    "status": 301,
                    "headers": {},
                    "location": (
                        "/categories/"
                        + quote(target, safe="-")
                        + self._language_suffix(
                            language,
                            explicit_language,
                        )
                    ),
                }
            return self._not_found(language)

        content = self._category_content(
            connection,
            category,
            language,
        )
        store = self._store_translation(connection, language)
        store_name = store["store_name"] or "Store"
        currency = self._read_setting(connection, "currency", "EUR")
        public_base_url = self._read_setting(
            connection,
            "public_base_url",
            "",
        )
        products = connection.execute(
            """
            SELECT p.id, p.sku, p.slug, p.name, p.short_description,
                   p.description, p.price_minor, p.track_inventory,
                   p.legacy_language_code,
                   COALESCE(i.stock_on_hand, 0) AS stock_on_hand
            FROM product_categories pc
            JOIN products p ON p.id = pc.product_id
            LEFT JOIN inventory i ON i.product_id = p.id
            WHERE pc.category_id = ?
              AND p.status = 'active'
            ORDER BY pc.sort_order, p.name, p.id
            LIMIT ?
            """,
            (str(category["id"]), MAX_PUBLIC_PRODUCTS),
        ).fetchall()

        cards = [
            self._product_card(
                row,
                self._product_content(connection, row, language),
                currency,
                language,
                explicit_language,
            )
            for row in products
        ]
        body = (
            f"<h1>{escape(content['name'])}</h1>"
            + (
                f'<p class="description">{self._plain_text(content["description"])}</p>'
                if content["description"]
                else ""
            )
            + (
                '<section class="grid">' + "".join(cards) + "</section>"
                if cards
                else ""
            )
        )
        title = content["meta_title"] or (
            content["name"] + (" — " + store_name if store_name else "")
        )
        description = content["meta_description"] or content["description"]
        path = "/categories/" + quote(str(category["slug"]), safe="-")
        document = self._document(
            language=language,
            title=title,
            description=description,
            store_name=store_name,
            body=body,
            canonical=self._canonical_url(
                public_base_url,
                path,
                language,
                explicit_language,
            ),
            path=path,
            available_languages=self._available_languages(connection),
        )
        return self._response(body=document, language=language)

    def _render_product(
        self,
        connection,
        *,
        slug: str,
        language: str,
        explicit_language: bool,
    ) -> dict[str, object]:
        product = self._load_active_product(connection, slug)
        if product is None:
            target = self._historical_target(
                connection,
                "product",
                slug,
            )
            if target is not None:
                return {
                    "status": 301,
                    "headers": {},
                    "location": (
                        "/products/"
                        + quote(target, safe="-")
                        + self._language_suffix(
                            language,
                            explicit_language,
                        )
                    ),
                }
            return self._not_found(language)

        content = self._product_content(
            connection,
            product,
            language,
        )
        store = self._store_translation(connection, language)
        store_name = store["store_name"] or "Store"
        currency = self._read_setting(connection, "currency", "EUR")
        public_base_url = self._read_setting(
            connection,
            "public_base_url",
            "",
        )
        description = content["description"] or content["short_description"]
        body = (
            f"<article><h1>{escape(content['name'])}</h1>"
            + (
                f'<p class="description">{self._plain_text(content["short_description"])}</p>'
                if content["short_description"]
                else ""
            )
            + f'<p class="price">{escape(self._money(int(product["price_minor"]), currency))}</p>'
            + (
                f'<div class="description">{self._plain_text(description)}</div>'
                if description
                else ""
            )
            + "</article>"
        )
        title = content["meta_title"] or (
            content["name"] + (" — " + store_name if store_name else "")
        )
        meta_description = (
            content["meta_description"]
            or content["short_description"]
            or content["description"]
        )
        path = "/products/" + quote(str(product["slug"]), safe="-")
        document = self._document(
            language=language,
            title=title,
            description=meta_description,
            store_name=store_name,
            body=body,
            canonical=self._canonical_url(
                public_base_url,
                path,
                language,
                explicit_language,
            ),
            path=path,
            available_languages=self._available_languages(connection),
        )
        return self._response(body=document, language=language)

    def render(
        self,
        payload: dict[str, object],
        context,
    ) -> dict[str, object]:
        if getattr(context, "audience", None) != "public":
            raise ValueError("Public catalog requires the public audience")

        method = payload.get("method")
        path = payload.get("path")
        params = payload.get("path_params")
        if method not in {"GET", "HEAD"}:
            return {"status": 405, "headers": {}}
        if not isinstance(path, str) or not isinstance(params, dict):
            return {"status": 400, "headers": {}}

        with self.application.storage.transaction() as connection:
            language, explicit_language = self._select_language(
                connection,
                payload,
            )

            if path == "/":
                return self._render_home(
                    connection,
                    language=language,
                    explicit_language=explicit_language,
                )

            slug = params.get("slug")
            if (
                not isinstance(slug, str)
                or SLUG.fullmatch(slug) is None
            ):
                return self._not_found(language)

            if path.startswith("/products/"):
                return self._render_product(
                    connection,
                    slug=slug,
                    language=language,
                    explicit_language=explicit_language,
                )
            if path.startswith("/categories/"):
                return self._render_category(
                    connection,
                    slug=slug,
                    language=language,
                    explicit_language=explicit_language,
                )

            return self._not_found(language)
