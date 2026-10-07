"""Minimal supervised service for the S0.2 Store package foundation."""

from __future__ import annotations

from three_mm_application_sdk import ApplicationContext, OperationContext


class StoreService:
    def __init__(self, context: ApplicationContext) -> None:
        self.context = context

    def handle(
        self,
        operation_id: str,
        payload: dict[str, object],
        context: OperationContext,
    ) -> dict[str, object]:
        if operation_id == "health":
            return {"status": "ready"}
        raise ValueError("Store operation is not implemented")


def create_service(context: ApplicationContext) -> StoreService:
    return StoreService(context)
