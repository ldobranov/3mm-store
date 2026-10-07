# 3mm Store

3mm Store is an e-commerce **Application Extension** for the 3mm platform.

The project is intentionally developed outside 3mm Core. Store owns its catalog,
inventory, carts, orders, checkout, public storefront and provider integrations.
Core changes are reserved for larger reusable platform capabilities with neutral
contracts and tests.

## Status

**S0 — architecture and generic platform gap audit**

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

3mm Store targets:

- Module Manifest v2;
- Application Extension v1;
- compiled UI for management screens;
- extension-owned SQLite/files and forward migrations;
- generic connector/secret boundaries;
- Milestone 19 Public Web Runtime for public GET/HEAD content.

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
