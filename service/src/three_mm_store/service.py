"""Supervised 3mm Store application service."""

from __future__ import annotations

from three_mm_application_sdk import ApplicationContext, OperationContext

from .categories import CategoryService
from .products import ProductService


class StoreService:
    def __init__(self, context: ApplicationContext) -> None:
        self.context = context
        self.categories = CategoryService(context)
        self.products = ProductService(context)

    def handle(
        self,
        operation_id: str,
        payload: dict[str, object],
        context: OperationContext,
    ) -> dict[str, object]:
        if operation_id == "health":
            return {"status": "ready"}

        handlers = {
            "catalog_list_categories": self.categories.list_categories,
            "catalog_get_category": self.categories.get_category,
            "category_create": self.categories.create,
            "category_update": self.categories.update,
            "category_set_status": self.categories.set_status,
            "catalog_list_products": self.products.list_products,
            "catalog_get_product": self.products.get_product,
            "product_create": self.products.create,
            "product_update": self.products.update,
            "product_set_status": self.products.set_status,
        }
        handler = handlers.get(operation_id)
        if handler is None:
            raise ValueError("Store operation is not implemented")
        return handler(payload, context)


def create_service(context: ApplicationContext) -> StoreService:
    return StoreService(context)
