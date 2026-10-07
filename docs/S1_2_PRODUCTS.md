# S1.2 — Products

Status: **implemented on branch; physical acceptance pending**

Version: `0.1.0-dev.6`

Branch: `s1/products`

## Goal

Add the first real Store product catalog slice on top of the accepted category
and localization foundation, without changing 3mm Core.

S1.2 deliberately reuses schema revision `0002`; the product tables and
language-keyed product translations were already reserved by S1.1b.

## Operations

S1.2 adds:

```text
catalog_list_products
catalog_get_product
product_create
product_update
product_set_status
```

All product operations are available to `operator` and `administrator` and
use the existing `catalog_manage` permission.

Queries forbid idempotency keys. Mutations require them and use the same
Store-owned replay-safe transaction helper as categories.

## Product identity and shared fields

Products use opaque identifiers:

```text
prd_<32 lowercase hex>
```

Language-independent fields are:

```text
sku
slug
price_minor
track_inventory
status
category_ids
```

SKU is normalized to uppercase and accepts only:

```text
A-Z 0-9 . _ -
```

with a maximum of 80 characters.

The canonical slug remains language-independent in S1 and follows the existing
Store slug contract. Old slugs are retained in `slug_history` and cannot be
silently reassigned to another product.

Prices remain integer minor units. S1.2 does not introduce floating-point money
or multi-currency behavior.

## Localized product content

Product content uses the S1.1b `product_translations` table:

```text
(product_id, language_code)
name
short_description
description
meta_title
meta_description
created_at
updated_at
```

The editor discovers the currently available 3mm content languages dynamically
and preserves translations for language packs that later become unavailable.

Existing legacy `products.name/short_description/description` columns remain a
backward-compatible fallback exactly like category legacy text.

## Category assignments

A product may belong to zero or more Store categories.

Assignments are stored in `product_categories`. Every submitted category ID
must already exist in Store. Updating the category list replaces the assignment
set in the same command transaction.

S1.2 does not invent a primary category because canonical product URLs remain
independent of category hierarchy.

## Inventory initialization

Creating a product also creates its Store inventory row with:

```text
stock_on_hand = 0
```

The product-level `track_inventory` flag is managed in S1.2.

Actual stock adjustment remains S1.3 Inventory work and continues to use the
separate `inventory_manage` permission.

## Product lifecycle

S1.2 uses:

```text
draft
active
archived
```

New products start as `draft`.

Status changes are explicit replay-safe commands. Public rendering is not part of
this increment; later public catalog work must expose only `active` products.

## Catalog UI

The existing `/store/catalog` compiled route now contains product management
in addition to categories.

The product editor supports:

- dynamic installed content languages;
- per-language name, short description, full description and SEO fields;
- unsaved per-language draft preservation while switching tabs;
- SKU and slug;
- integer minor-unit price;
- inventory tracking flag;
- multiple category assignments;
- draft/active/archived status;
- localized list/search;
- bounded pagination and deterministic sorting.

The UI calls only the generic Application Extension operation gateway and does
not introduce `/api/store/*` routes.

## Storage compatibility

S1.2 requires no new migration:

```text
schema_revision = 0002
```

An upgrade from S1.1b therefore must not re-run or modify the accepted migration
journal.

Product creation uses the existing tables:

```text
products
product_translations
product_categories
inventory
slug_history
idempotency_records
```

## Automated verification

Tests cover:

- replay-safe create;
- automatic inventory-row initialization;
- uppercase SKU canonicalization and uniqueness;
- multiple localized product versions;
- localized/SKU/slug search;
- slug-history reservation;
- transactional category replacement;
- invalid category rejection;
- price validation;
- status changes;
- package contract declaration;
- inclusion of the product compiled UI source.

The built package is still validated against the current 3mm package contract in
CI.

## Physical acceptance target

Before S1.2 is accepted on Raspberry:

1. build and validate `0.1.0-dev.6`;
2. upgrade the existing Store instance;
3. confirm the migration journal remains exactly `0001, 0002`;
4. create a draft product with BG content;
5. add EN content without overwriting BG;
6. switch languages with unsaved text and confirm the draft is preserved;
7. assign and replace multiple categories;
8. verify SKU normalization and duplicate rejection;
9. change the slug and confirm the old slug is reserved;
10. change product status draft -> active -> archived;
11. restart the Store service and confirm products/translations survive;
12. confirm no Store-specific Core change is required.

S1.3 begins only after this product slice is accepted.
