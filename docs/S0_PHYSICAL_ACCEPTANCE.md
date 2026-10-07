# S0 Physical Acceptance

Status: **passed on 2026-10-07**

Package version: `0.1.0-dev.0`

Accepted package SHA-256:

```text
4992466baff93cc2f5f37a3f85bd716147cb0817e7516996f84e87016d444141
```

Target: physical `rasp-3mm` running the merged 3mm platform after Milestone 19.

## Contract validation

The deterministic Store ZIP passed the real current 3mm package validator:

```text
VALID
module_id: org.3mm.store
version: 0.1.0-dev.0
sha256: 4992466baff93cc2f5f37a3f85bd716147cb0817e7516996f84e87016d444141
operations: 1
routes: 3
storage_revision: 0001
```

## Physical activation

The package was uploaded and activated through the normal 3mm Extensions
lifecycle.

Store application instance:

```text
c7ba07bcce44f1f52fd74a3e
```

The supervised unit was active:

```text
3mm-application-extension@c7ba07bcce44f1f52fd74a3e.service
active (running)
```

No manual Store runtime files were copied into the application state area.

## Storage and migration

The host created the Store-owned database under the application `data/`
subtree and migration `0001` created:

```text
categories
idempotency_records
inventory
product_categories
product_media
products
slug_history
store_settings
three_mm_outbox
three_mm_schema_migrations
```

The migration journal contained exactly:

```text
0001
```

After restarting only the Store supervised service, the unit returned to
`active` and the migration journal still contained exactly one `0001`
entry. The migration was not re-applied.

## Compiled UI

All three declared compiled application routes opened successfully:

```text
/store/catalog
/store/inventory
/store/settings
```

At S0 they intentionally rendered foundation placeholders only.

## Acceptance conclusion

S0 proves that 3mm Store can be packaged, validated, installed, migrated,
started, restarted and rendered as a separate Application Extension without a
Store-specific Core change.

The remaining generic platform-gap candidates from S0 stay separate from Store
business implementation, notably public mutation ingress and product-media
ingestion.

S1 may therefore implement Store-owned catalog behavior on this accepted
foundation.
