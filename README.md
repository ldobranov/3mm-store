# 3mm Store

3mm Store is an e-commerce Application Extension for the 3mm platform.

The project is intentionally developed outside 3mm Core. Store owns its catalog,
inventory, carts, orders, checkout, public storefront and provider integrations.
Core changes are allowed only for larger reusable platform capabilities with
neutral contracts and tests.

## Status

S0 — architecture and generic platform gap audit.

## Platform baseline

The extension targets the current 3mm Application Extension v1 contract and
Milestone 19 Public Web Runtime.

Planned module identity:

```text
org.3mm.store
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
