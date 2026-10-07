# 3mm Store

3mm Store is an e-commerce **Application Extension** for the 3mm platform.

The project is intentionally developed outside 3mm Core. Store owns its catalog,
inventory, carts, orders, checkout, public storefront and provider integrations.
Core changes are reserved for larger reusable platform capabilities with neutral
contracts and tests.

## Status

**S1.1 — category management**

Module identity:

```text
org.3mm.store
```

Current work happens on:

```text
s0/store-foundation
```

## Architecture

The authoritative Store architecture and delivery plan is:

- [Store Application Extension Development Guide](docs/STORE_EXTENSION_GUIDE.md)
- [S0 Generic Platform Gap Audit](docs/S0_GAP_AUDIT.md)
- [S0.1 Catalog Contract](docs/S0_CATALOG_CONTRACT.md)
- [S0.2 Installable Package Foundation](docs/S0_PACKAGE_FOUNDATION.md)
- [S0 Physical Acceptance](docs/S0_PHYSICAL_ACCEPTANCE.md)

3mm Store targets:

- Module Manifest v2;
- Application Extension v1;
- compiled UI for management screens;
- extension-owned SQLite/files and forward migrations;
- generic connector/secret boundaries;
- Milestone 19 Public Web Runtime for public GET/HEAD content.

## Build

```bash
python tools/build_package.py --output dist/3mm-store.zip
```

## Tests

```bash
python -m unittest discover -s tests -v
```

To validate the built package with the real 3mm package validator from a sibling
checkout:

```bash
python tools/validate_against_3mm.py \
  --core-root ../3mm \
  --package dist/3mm-store.zip
```

## Development rule

Normal Store development should be:

```text
change Store -> build Store package -> test -> install/upgrade Store
```

not:

```text
change Store -> patch Core -> patch Store -> release both together
```

A Core change is acceptable only when S0/Sx proves a reusable platform gap that
can be specified and tested without Store semantics.
