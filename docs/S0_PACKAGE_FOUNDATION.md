# S0.2 — Installable Package Foundation

Status: **implemented on `s0/store-foundation`**

S0.2 adds the first real Store package skeleton without implementing catalog
business operations.

## Included contract

The package now contains:

- Module Manifest v2 identity `org.3mm.store`;
- Application Extension v1;
- SDK 1.3 service declaration;
- the required internal `health` query;
- S1 Store permissions;
- compiled UI route declarations for catalog, inventory and settings;
- migration revision `0001`;
- the S0.1 catalog schema;
- deterministic wheel/package builder;
- pure-stdlib package tests;
- helper for validation against a local 3mm checkout.

No catalog CRUD operation is implemented yet.

## Repository source vs installable ZIP

Repository source includes build tools, tests and documentation.

The deterministic builder emits only files allowed by the current 3mm
Application Extension package validator:

```text
manifest.json
application-extension.json
compiled-ui.json
service/three_mm_store-<wheel-version>-py3-none-any.whl
source/frontend/Catalog.vue
source/frontend/Inventory.vue
source/frontend/Settings.vue
```

The wheel contains:

```text
three_mm_store/__init__.py
three_mm_store/service.py
three_mm_store/migrations.py
three_mm_store-<wheel-version>.dist-info/...
```

## Build

```bash
python tools/build_package.py --output dist/3mm-store.zip
```

The builder uses fixed ZIP timestamps and sorted files, so identical source and
version produce identical package bytes and SHA-256.

## Local tests

```bash
python -m unittest discover -s tests -v
```

The tests verify:

- deterministic build;
- module/version identity consistency;
- service wheel checksum binding;
- exact minimal manifest permission set;
- health-only S0.2 operation inventory;
- UI route source inclusion;
- absence of repository-only files from the installable ZIP.

## Validation against 3mm

With sibling checkouts:

```text
parent/
  3mm/
  3mm-store/
```

activate the Python environment used for 3mm, then run:

```bash
python tools/validate_against_3mm.py \
  --core-root ../3mm \
  --package dist/3mm-store.zip
```

The helper invokes the real
`backend.services.module_packages.validate_module_package` from that checkout.
It does not copy the Core validator into Store.

## Migration 0001

The migration creates the S0.1 frozen schema:

- `store_settings`;
- `categories`;
- `products`;
- `product_categories`;
- `inventory`;
- `product_media`;
- `slug_history`;
- `idempotency_records`.

The migration uses individual `connection.execute(...)` calls rather than
`executescript()` so the host's `ApplicationStorage.migrate()` transaction
remains authoritative.

## UI state

The three Vue routes are deliberate placeholders. They prove package/UI route
wiring only.

They do not call fake Store endpoints and do not rely on legacy
`/api/store/*` behavior.

S1 replaces the placeholders incrementally as the real catalog operations are
implemented.

## S0.2 boundary

S0.2 changes no 3mm Core code and introduces no Store-specific platform
contract.

The next step is S0.3 validation of this package against the real current 3mm
validator and then S1 catalog service operations.
