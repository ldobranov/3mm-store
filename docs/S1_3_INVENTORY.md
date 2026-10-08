# S1.3 — Inventory

Status: **implemented on branch; physical acceptance pending**

Version: `0.1.0-dev.7`

Branch: `s1/inventory`

## Goal

Deliver a complete Store-owned inventory slice on top of the accepted product
catalog without changing 3mm Core.

S1.3 adds bounded inventory queries, transactional stock adjustments, durable
adjustment history and a real Inventory compiled UI.

## Operations

S1.3 adds:

```text
inventory_list
inventory_adjust
```

Both are available to `operator` and `administrator` and use the existing
`inventory_manage` permission.

`inventory_list` is a query and therefore forbids idempotency keys.

`inventory_adjust` is a command and requires an idempotency key. Replaying the
same actor/operation/key/request returns the stored response without applying the
stock delta twice.

## Inventory model

The authoritative stock row remains:

```text
inventory
  product_id
  stock_on_hand
  updated_at
```

S1.3 introduces schema revision `0003` with:

```text
inventory_adjustments
  id
  product_id
  delta
  stock_before
  stock_after
  reason
  created_at
```

Adjustment IDs are opaque:

```text
adj_<32 lowercase hex>
```

Migration `0003` also backfills a zero-stock inventory row for any older
product that somehow lacks one. Existing stock values are never overwritten.

## Adjustment rules

An inventory adjustment accepts:

```text
product_id
delta
reason
```

Rules:

- `delta` is a non-zero signed integer;
- the absolute delta is bounded to 1,000,000,000 units;
- `reason` is required and bounded to 240 characters;
- the resulting `stock_on_hand` may never become negative;
- current stock, resulting stock, history row and idempotency response commit in
  one Store SQLite transaction;
- the browser never submits the resulting stock as authoritative truth.

The Store does not persist Core user IDs in the adjustment history, preserving
the current non-personal-data storage classification.

## Availability model

S1.3 keeps product inventory tracking separate from the numeric stock value:

```text
track_inventory = false -> untracked
track_inventory = true and stock_on_hand > 0 -> in_stock
track_inventory = true and stock_on_hand = 0 -> out_of_stock
```

A product may still carry a numeric stock value while tracking is disabled. This
lets an operator preserve the last known quantity if tracking is later enabled.

## Inventory query

`inventory_list` supports bounded:

- localized product name through the S1.1b language model;
- search by localized name, SKU or slug;
- product status filter;
- availability filter;
- page size up to 100;
- deterministic sorting by recent inventory change, name, SKU or stock.

The query never requires `catalog_manage`; Inventory remains independently
protected by `inventory_manage`.

## Inventory UI

`/store/inventory` now provides:

- installed-language discovery through the existing 3mm language API;
- live host-language following until an operator explicitly pins another content
  language;
- localized product names;
- search/status/availability filters;
- stock sorting and pagination;
- current stock and derived availability;
- explicit signed-delta adjustment;
- mandatory adjustment reason;
- projected stock preview;
- light/dark theme compatibility through 3mm theme tokens.

The UI calls only the generic Application Extension operator gateway.

## Storage compatibility

S1.3 upgrades:

```text
0001 -> 0002 -> 0003
```

No existing product, category, translation or inventory row is destructively
rewritten.

## Automated verification

Tests cover:

- localized inventory listing;
- in-stock/out-of-stock/untracked separation;
- atomic stock adjustment;
- replay-safe adjustment;
- durable adjustment history;
- rejection of negative resulting stock;
- bounded delta and reason;
- `0003` backfill behavior;
- package operation/permission contract;
- Inventory compiled UI use of the inventory operation contract.

The deterministic package continues to validate against the current 3mm Core
package validator in CI.

## Physical acceptance target

Before S1.3 is accepted on Raspberry:

1. build and validate `0.1.0-dev.7`;
2. upgrade the existing Store instance;
3. confirm migration journal is exactly `0001, 0002, 0003`;
4. open `/store/inventory` with an operator holding `inventory_manage`;
5. verify localized product names and filters;
6. add stock with a positive delta and reason;
7. subtract stock with a negative delta;
8. verify an adjustment that would make stock negative is rejected;
9. repeat the same command idempotency key and confirm stock is not applied twice;
10. restart the Store service and confirm stock/history persist;
11. verify an operator without `inventory_manage` cannot access the route or
    operations;
12. confirm 3mm Core/Admin remains healthy if the Store service is stopped.

No Store-specific Core change is part of S1.3.
