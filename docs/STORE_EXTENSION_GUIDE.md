# 3mm Store Application Extension Development Guide

## Status and purpose

This guide defines the architecture and delivery plan for a real e-commerce/store application built **as a separate 3mm Application Extension**.

It replaces the older Store Extension guidance that assumed direct FastAPI router registration, direct access to the Core database, PostgreSQL-specific table handling, and extension code running inside Core. Those patterns are no longer valid for the current 3mm architecture.

The Store extension may implement products, categories, inventory, carts, orders, customers, checkout, payments, shipping, administration, and a public storefront. **3mm Core must not learn Store-specific concepts in order to support them.**

The extension is expected to use the generic platform capabilities that already exist:

- Module Manifest v2 packaging;
- Application Extension v1 supervised service runtime;
- extension-owned SQLite/files and forward migrations;
- versioned query/command/job operations;
- public, operator and administrator audiences;
- extension-scoped permissions;
- connector and secret broker;
- backup/restore and lifecycle integration;
- Milestone 19 Public Web Runtime for public GET/HEAD pages and resources.

This document is a product-extension guide, not a request to add Store code to Core.

---

## 1. Non-negotiable architecture rules

### 1.1 Store owns the business model

The Store extension owns all meaning related to:

- products;
- categories;
- variants and options;
- prices and discounts;
- inventory;
- carts;
- customers;
- addresses;
- orders;
- checkout;
- shipping rules;
- payment-provider behavior;
- invoices and refunds;
- public product/category pages;
- Store-specific metadata and structured data;
- Store analytics and administration.

Core must not contain branches such as:

```python
if module_id == "store":
    ...
```

Core must not gain Store-specific routes such as:

```text
/api/store/products
/api/store/cart
/api/store/orders
```

The extension uses the existing generic Application Extension gateway and Public Web Runtime.

### 1.2 Store does not run inside Core

The Store backend runs as a supervised Application Extension service outside the Core process.

The Store service:

- does not import Core routers;
- does not register FastAPI routers in Core;
- does not call `context.register_router(...)`;
- does not import `backend.db.*`;
- does not call Core `get_db()`;
- does not read or write the Core SQLite database;
- does not create Store tables in the Core database;
- does not open an unmanaged HTTP listener;
- does not receive unrestricted network access.

Core communicates with the service only through the versioned Application Extension contracts.

### 1.3 Store owns its persistent state

Persistent Store state belongs in the Application Extension instance area. The current host layout is:

```text
/var/lib/3mm/application-extensions/<instance-id>/
  active.json
  releases/
  data/
    state.sqlite3
    files/
  run/
    service.sock
```

Store code must not construct or depend on those absolute paths. It receives the writable data area through `ApplicationContext.data_dir` and the database through `ApplicationContext.storage`.

The Store service owns the meaning of everything below its `data/` directory. Reviewed release artifacts, transport metadata and service keys remain platform-owned.

Schema changes use forward migrations declared by the extension package and executed by `ApplicationStorage`.

### 1.4 Core changes require a generic platform reason

Development of the Store must not become a sequence of small Store-driven Core edits.

Before changing Core, all of the following must be true:

1. the required behavior cannot be implemented with the current public web, application operation, storage, connector, secret, UI, lifecycle or backup contracts;
2. the missing capability is useful beyond Store;
3. the proposed Core change contains no Store/product/order/payment/provider semantics;
4. a neutral reference or contract test can prove the capability without installing Store;
5. compatibility, recovery, limits and failure behavior are defined before implementation.

A Store-specific Core endpoint is not an acceptable workaround.

---

## 2. Current 3mm platform contracts used by Store

## 2.1 Application Extension v1

Store is packaged as an Application Extension with a strict `application-extension.json`.

The package declares:

- service artifact and entrypoint;
- health operation;
- queries, commands and jobs;
- allowed audiences;
- idempotency requirements;
- strict input/output schemas;
- extension permissions;
- compiled UI routes where needed;
- connectors;
- scheduled jobs;
- extension storage and migration revision;
- public HTTP routes.

The service is installed, activated, disabled, upgraded, rolled back, backed up and restored through the normal Extensions lifecycle.

## 2.2 Application operations

Business APIs are declared operations, not arbitrary extension HTTP routers.

Current generic gateway surfaces include:

```text
POST /api/v1/application-extensions/<module-id>/public/operations/<operation-id>
POST /api/v1/application-extensions/<module-id>/operator/operations/<operation-id>
POST /api/v1/application-extensions/<module-id>/operations/<operation-id>
```

The last form is the administrator operation gateway.

Use audiences deliberately:

- `public` — intentionally anonymous operations;
- `operator` — authenticated staff with Store permissions;
- `administrator` — configuration and high-impact administration;
- `internal` — health, jobs and platform-driven operations.

The current contract is strict: every `command` and `job` operation **must** declare `idempotency: "required"`, while every `query` must declare `idempotency: "forbidden"`. Store code must implement replay-safe command handling against the caller-provided idempotency key.

## 2.3 Public Web Runtime v1

Milestone 19 allows the Store to own real public web routes while remaining isolated from the administrative SPA.

Public web v1 supports declared:

- `GET`;
- `HEAD`;
- HTML;
- JSON;
- XML/feed formats;
- plain text;
- bounded web assets;
- redirects;
- explicit 404/410 and other allowed statuses;
- caching metadata.

Example Store public routes may eventually include:

```text
/
/products/{slug}
/categories/{slug}
/brands/{slug}
/search
/robots.txt
/sitemap.xml
/manifest.webmanifest
/assets/{slug}
```

The exact route set is Store-owned and must not be hardcoded in Core.

### Important limitation: public mutations are not solved by M19

Public Web v1 is a **GET/HEAD publishing surface**. It is not the mutation path for cart, login or checkout operations.

3mm already has declared anonymous Application Extension operations at:

```text
POST /api/v1/application-extensions/<module-id>/public/operations/<operation-id>
```

However, that endpoint lives on the Core API surface, not on the isolated M19 public-web surface. A future public domain must **not** simply expose the complete Core/Admin API in order to make a Store cart work.

Therefore S0 must explicitly resolve the generic browser-to-public-operation ingress model. Acceptable directions include a narrowly scoped, versioned public interaction surface or an equally generic trusted ingress rule that exposes only the required public application-operation contract. The solution must not contain Store, cart, checkout or payment semantics.

Until that contract is accepted, the guide must not claim that a production public storefront can safely perform same-origin mutations.

Public Web v1 also intentionally forbids arbitrary transport behavior such as `Set-Cookie`. If Store later proves that an HttpOnly/SameSite public-session cookie or another transport primitive is mandatory, that is a **generic Public Web/session contract gap**, not a Store-specific Core exception.

A related S0 check is anonymous abuse protection. The current public operation context does not give the extension a trustworthy client-IP/header identity for source-aware throttling. If login, checkout or other public commands require platform-level rate limiting, define that generically rather than adding Store-only middleware.

---

## 3. Store architecture

Target shape:

```text
Browser
  |
  +---- Public GET/HEAD ----> 3mm Public Web Runtime
  |                              |
  |                              v
  |                         Core public gateway
  |                              |
  |                              v
  |                      Store supervised service
  |
  +---- Public mutations --> generic public interaction ingress
  |                              |
  |                              v
  |                     Application Extension public operations
  |
  +---- Staff/admin -------> generic operator/admin operation gateways
                                 |
                                 v
                         Store supervised service
                                 |
                +----------------+----------------+
                |                                 |
                v                                 v
        Store-owned SQLite                  Store-owned files
                |
                v
        transactional business state
                |
                v
     3mm connector/secret broker
                |
                v
         external provider APIs
```

Store must remain usable for local catalog/order administration even when an optional external provider is unavailable, unless a specific operation inherently requires that provider.

---

## 4. Repository boundary

The Store should live in its own repository.

Suggested source-repository structure:

```text
3mm-store/
  README.md
  CHANGELOG.md
  VERSION

  manifest.json
  application-extension.json
  compiled-ui.json

  service/
    pyproject.toml
    src/
      three_mm_store/
        __init__.py
        service.py
        migrations.py
        domain/
          catalog.py
          pricing.py
          inventory.py
          cart.py
          orders.py
          checkout.py
        operations/
          public.py
          operator.py
          admin.py
          internal.py
        public_web/
          renderer.py
          templates.py
          metadata.py
        connectors/
          payments.py
          shipping.py
        security/
          tokens.py

  source/
    frontend/
      CatalogAdmin.vue
      Orders.vue
      shared/

  build/
    build_package.py

  tests/
```

This is a suggested source layout, not a Core contract.

The **installed ZIP is stricter than the repository**. For an Application Extension package, the current validator allows the package metadata, one reviewed service wheel, optional `compiled-ui.json`, and compiled-UI source files under `source/frontend/`. Repository-only tests, build scripts, design assets and other development files must not be copied blindly into the installable ZIP.

For S1, where Store already has management UI, the package must target both `core` and `ui`, declare `compiled-ui.json`, and declare matching route entrypoints in `application-extension.json`.

---

## 5. Domain model principles

## 5.1 Money

Never use binary floating-point for money.

Use integer minor units plus an ISO currency code:

```json
{
  "price_minor": 1299,
  "currency": "EUR"
}
```

For EUR:

```text
1299 -> €12.99
```

Recommended rules:

- all persisted monetary amounts use integers;
- currency is explicit;
- arithmetic is integer-based;
- rounding rules are explicit at the business-rule boundary;
- order lines snapshot the accepted unit price;
- historical orders never depend on the current product price.

Fields should use names such as:

```text
price_minor
sale_price_minor
cost_minor
subtotal_minor
discount_minor
shipping_minor
tax_minor
total_minor
```

## 5.2 IDs

Do not expose SQLite row IDs as the only durable business identity.

Prefer stable opaque IDs for public/business records:

```text
prd_<random>
cat_<random>
var_<random>
crt_<random>
ord_<random>
cus_<random>
```

SQLite integer primary keys may still be used internally where useful.

## 5.3 Slugs

Public content may use human-readable slugs:

```text
/products/blue-shirt
/categories/shirts
```

Rules:

- normalized and validated;
- unique within the intended scope;
- previous slugs may be retained for redirects;
- changing a slug must not change the internal entity ID.

## 5.4 Snapshots

Orders must preserve what was actually purchased.

Order items snapshot at least:

- product ID;
- variant ID where applicable;
- SKU;
- display name;
- selected options;
- quantity;
- unit price;
- discount;
- tax treatment needed for the order;
- final line total.

Deleting or changing a product later must not rewrite historical orders.

---

## 6. Proposed Store-owned database

The final schema is decided during S0/S1. This section gives the preferred direction.

Do not create these tables in Core. They belong in the Store extension `state.sqlite3`.

### 6.1 Catalog

Recommended normalized tables:

```text
products
categories
product_categories
product_variants
product_media
inventory
slug_history
```

Optional later tables:

```text
brands
product_attributes
attribute_values
product_attribute_values
collections
```

Avoid storing the complete category tree, variants and inventory as one large JSON column when relational constraints are useful.

JSON remains appropriate for bounded flexible data such as:

- selected option snapshot;
- structured dimensions;
- provider metadata;
- extension-private rendering metadata.

### 6.2 Carts

Recommended:

```text
carts
cart_items
```

A cart should have:

- opaque cart ID;
- optional public cart token hash or customer link;
- currency;
- status;
- created/updated timestamps;
- expiry timestamp where applicable.

Cart items reference stable product/variant IDs but totals must always be recalculated by the service from authoritative Store data.

The browser must never be trusted to submit its own accepted price as truth.

### 6.3 Orders

Recommended:

```text
orders
order_items
order_addresses
order_status_history
payment_attempts
shipping_selections
```

Order creation must be transactional.

A command that creates an order should use an idempotency key so browser retries cannot produce duplicate orders.

### 6.4 Customers

Customer accounts are **not required for the first catalog MVP**.

Start with guest-capable architecture.

When customer accounts are introduced, decide explicitly whether Store owns:

- customer identity;
- public authentication;
- password/credential storage;
- address book;
- sessions;
- account recovery.

Do not reuse 3mm administrator/operator accounts as storefront customer accounts by accident.

If secure public customer sessions require a generic platform capability that does not yet exist, open a separate platform gap review before implementation.

---

## 7. Store operations

Operation names below are examples. S0 freezes the first contract before implementation.

## 7.1 Internal

```text
health
```

Later, if needed:

```text
maintenance
reconcile_provider_state
expire_carts
```

## 7.2 Public catalog queries

Examples:

```text
catalog_list_products
catalog_get_product
catalog_list_categories
catalog_get_category
catalog_search
```

These can support browser-side interactions where returning full HTML is unnecessary.

Public page rendering itself belongs to the M19 Public Web handler.

## 7.3 Public cart and checkout operations

Potential operations:

```text
cart_create
cart_get
cart_add_item
cart_update_item
cart_remove_item
checkout_preview
order_create
order_get_public_status
```

Mutations should use idempotency where replay could duplicate business state.

### Guest cart identity

The current architecture does not require a Core Store session.

A first implementation may use an extension-issued opaque cart token:

1. `cart_create` creates a cart and returns an unguessable token;
2. the browser stores it;
3. later cart operations submit it in the operation payload;
4. the service stores only an appropriate verifier/hash where possible;
5. token rotation/expiry rules are Store-owned.

This is suitable for S2 evaluation.

If the product requires HttpOnly/SameSite server cookies, S0/S2 must treat that as a possible **generic public-session platform gap** because M19 public responses do not expose arbitrary `Set-Cookie`.

## 7.4 Operator operations

Examples:

```text
product_create
product_update
product_archive
category_create
category_update
inventory_adjust
order_list
order_get
order_update_status
```

Declare Store permissions such as:

```text
catalog_manage
inventory_manage
orders_manage
reports_view
```

Do not require global 3mm administrator access for normal daily Store work.

## 7.5 Administrator operations

Reserve administrator audience for higher-impact configuration and recovery, for example:

```text
store_configuration_get
store_configuration_update
payment_connector_status
data_export
maintenance_rebuild_indexes
```

Use the least powerful audience that fits the operation.

---

## 8. Public storefront

## 8.1 Rendering

The Store service may return complete HTML through the M19 public handler.

Core does not render Store templates and does not know Store page types.

Possible public route contract:

```text
/                         -> storefront home
/products/{slug}          -> product
/categories/{slug}        -> category
/search                    -> search page
/robots.txt                -> discovery policy
/sitemap.xml               -> XML discovery resource
```

Product/category metadata, structured data, canonical links and discovery resources belong to Store.

M19 deliberately does not trust arbitrary `Host` headers as canonical identity. Store should therefore use an administrator-configured public base URL when it needs absolute canonical URLs, structured-data URLs or external redirects. That value should be ordinary **Store-owned configuration**, persisted in Store state and changed through a declared administrator operation. Do not derive canonical origin from an untrusted request Host value.

Do not assume `manifest.json` configuration is a general Store-settings database. In the current Core, activation-time configuration is primarily used for platform bindings such as declared devices/connectors. Store business settings belong to the Store service unless a later generic application-configuration contract intentionally expands this boundary.

## 8.2 Public assets

M19 permits bounded common web assets.

Store should generate optimized derivatives rather than serve original multi-megabyte uploads directly through the public response contract.

Recommended initial policy:

- WebP/JPEG derivatives;
- explicit dimensions;
- deterministic filenames or content hashes;
- bounded byte size;
- lazy loading;
- alt text from Store content;
- no path traversal or arbitrary filesystem access.

### S0 media gap audit

Before implementing uploads, test:

- administrator upload payload size;
- storage lifecycle;
- backup/restore;
- public image response limits;
- multiple derivative sizes;
- cache behavior.

If current generic contracts are insufficient for normal product media, define one reusable **extension media capability** rather than adding Store-specific upload/asset endpoints to Core.

---

## 9. Admin and operator UI

Store management UI should use the Application Extension compiled UI mechanism and declared application routes.

Suggested areas:

```text
Dashboard
Products
Categories
Inventory
Orders
Customers          # later
Discounts          # later
Shipping           # later
Payments           # later
Settings
Diagnostics
```

Daily workflow permissions should be Store-scoped.

Examples:

```text
catalog_manage
inventory_manage
orders_manage
customers_manage
reports_view
store_configure
```

Navigation visibility is not authorization. Core/server-side operation authorization remains authoritative.

---

## 10. Payments

Payment support is a Store concern built on generic 3mm connector/secret capabilities.

### 10.1 Do not put providers in Core

Core must not know:

- Stripe;
- PayPal;
- myPOS;
- BORICA;
- ePay;
- bank-transfer Store rules;
- provider-specific order state.

Provider adapters belong in Store or in a later independently justified connector extension architecture.

### 10.2 Secrets

API keys and credentials must use the platform secret mechanism.

Do not place live secrets in:

- repository files;
- `manifest.json`;
- `application-extension.json`;
- frontend bundles;
- public operation payloads;
- logs;
- AI prompts/context.

### 10.3 Card data

Prefer provider-hosted or tokenized payment flows.

The Store should not persist:

- PAN/card number;
- CVV;
- raw payment credentials.

PCI scope must be intentionally minimized.

### 10.4 Payment state

Store owns a provider-neutral internal payment state model, for example:

```text
not_required
pending
authorized
paid
failed
cancelled
refunded
partially_refunded
unknown
manual_review
```

Provider responses are mapped into Store-owned state.

Ambiguous network outcomes must not be blindly retried when that could duplicate a charge.

---

## 11. Shipping

Shipping rules belong to Store.

Initial shipping can be simple and local:

```text
fixed rate
free above threshold
pickup
weight-based
```

Later carrier APIs use declared connectors.

Do not put courier names or shipping formulas in Core.

Store should persist the accepted shipping option and amount on the order so later configuration changes do not rewrite history.

---

## 12. Tax and discounts

Tax and discount logic must be deterministic and tested.

Do not hardcode an unexplained:

```python
tax = subtotal * 0.10
```

The Store extension owns:

- tax mode;
- tax rate/rules;
- inclusive/exclusive display;
- discount definitions;
- coupon rules;
- order-level vs line-level allocation;
- rounding policy.

The first MVP may deliberately support only one simple configured tax policy.

Complex jurisdiction engines are not required for S1/S2.

---

## 13. Inventory

Inventory is Store-owned state.

Basic model:

```text
product/variant
stock_on_hand
reserved
available
updated_at
```

Rules must define when stock changes:

- adding to cart should normally not permanently deduct stock;
- checkout/order creation may reserve or deduct according to Store policy;
- cancelled/failed orders release reservations;
- manual adjustments are audited in Store history.

Never trust the browser's submitted stock or price.

---

## 14. Connectors and external systems

The Store service does not receive unrestricted network access.

External integrations use the generic connector broker.

Examples:

- payment provider;
- courier/shipping API;
- external ERP;
- accounting API;
- supplier catalog.

Each connector should define:

- allowed origin;
- scheme;
- path prefix;
- timeout;
- authentication kind;
- mutation support;
- secret reference;
- retry/reconciliation policy.

External mutations that matter to business state should use Store-owned durable outbox/reconciliation state where appropriate.

---

## 15. Security

Minimum Store security requirements:

- strict schema validation for every operation;
- idempotency for state-changing commands where replay matters;
- server-side authorization;
- no Store data in Core DB;
- no unrestricted network access;
- no secrets in frontend or manifest;
- no raw exception text returned to public users;
- bounded payloads and query values;
- output encoding for rendered HTML;
- safe URL/slug handling;
- safe file paths;
- upload type/size validation;
- rate-limit review for anonymous public operations;
- cart/order tokens generated with cryptographic randomness;
- customer-sensitive data classified and covered by export/erasure policy;
- logs must not contain passwords, payment credentials or full private order payloads.

### CSRF note

Public Web v1 does not currently establish Store cookies. If a later Store design introduces cookie-authenticated mutation requests, CSRF protection becomes mandatory and must be designed together with the generic public-session mechanism.

---

## 16. Privacy and data lifecycle

Store may hold personal data.

The extension must define:

- what customer data is collected;
- why it is collected;
- retention periods;
- export behavior;
- erasure behavior;
- what order data must remain for legal/accounting reasons;
- which fields are private or secret;
- what appears in diagnostics.

Core should only understand the generic classification/lifecycle contract, not Store row contents.

---

## 17. Backup, restore, disable and uninstall

Store must participate in the normal Application Extension lifecycle.

### Disable

Expected behavior:

- Store service stops;
- Store operations become unavailable;
- public Store routes stop resolving;
- scheduled jobs stop;
- data under the extension `data/` subtree remains preserved.

### Upgrade

An upgrade must:

1. validate package and contracts;
2. stage the new service;
3. apply forward migration safely;
4. check readiness;
5. activate only after success;
6. preserve the prior healthy version for rollback according to platform rules.

### Backup/restore

Backup should preserve required Store state:

```text
state.sqlite3
required files/media
migration revision
durable outbox/reconciliation data
configuration references
```

Secret material follows the platform secret/recovery rules rather than being embedded in the Store archive.

### Uninstall vs data erase

Uninstalling the package and erasing Store business data must remain explicit, distinguishable actions.

---

## 18. Performance principles

Do not optimize prematurely, but design the data model correctly.

Initial requirements:

- indexes for slug, SKU, status, created time and common relationships;
- pagination on catalog/order lists;
- no unbounded SELECT/list operation;
- optimized product image derivatives;
- public cache headers where content permits;- bounded search input;
- no N+1 queries on category/product listing;
- use `ApplicationContext.storage.transaction()` for business transactions;
- do not override the SDK's SQLite/WAL behavior unless a later platform contract explicitly allows it;
- transactional order creation.

A CDN, service worker or distributed cache is not required for the first Store milestone.

---

## 19. Observability

Store-specific diagnostics may expose safe aggregates such as:

```text
active products
low-stock items
open orders
failed payment attempts
connector health
pending outbox entries
last migration revision
```

Diagnostics must not expose:

- card/payment credentials;
- secret references with secret values;
- customer passwords;
- full private addresses in generic health output;
- raw connector responses containing sensitive data.

Use correlation IDs where supported to connect browser operation, Core gateway, Store transaction and connector attempt.

---

# Known generic platform questions before Store implementation

These are not Store features. They are platform-boundary questions that S0 must answer against the current 3mm main branch.

## A. Public mutation ingress

M19 proves isolated public GET/HEAD serving on the public surface. The anonymous Application Extension operation gateway currently lives on the Core API surface.

A production Store must not require exposing the entire Core/Admin API to the Internet. Before S2, define and accept a generic, bounded way for a public browser origin to invoke declared `public` application commands.

This is the strongest currently known Core-gap candidate.

## B. Public sessions

Guest carts can initially use a cryptographically random extension-issued bearer token in the operation payload. That does not require Core to understand carts.

If secure customer login requires HttpOnly/SameSite cookies, session rotation, logout or recovery on the isolated public origin, treat that as a generic public-session contract and design it independently of Store.

## C. Anonymous rate limiting

Public commands such as login, coupon validation, checkout and order creation may need source-aware throttling. The current public operation context does not expose a trusted source identity to the extension.

Decide whether generic ingress-level limits are sufficient or whether the platform needs a reusable public-operation rate-limit contract.

## D. Media transport

M19 public responses are bounded to 512 KiB per response, with route defaults normally smaller. Product media can work with optimized derivatives, but administrator upload, derivative generation, backup and serving must be tested before S1 is closed.

Do not add `/api/store/upload` to Core. If a reusable extension media capability is needed, design and test it generically.

## E. External public ingress

M19 physical acceptance proves a loopback-only public listener. DNS, TLS, trusted reverse-proxy/public-domain binding and Internet exposure are separate deployment concerns.

S6 cannot be called Internet-production-ready until that deployment boundary is explicitly implemented and accepted.

---

# Delivery plan

## S0 — Architecture and generic gap audit

**Goal:** freeze the first Store contract before business implementation.

Deliverables:

- repository skeleton;
- product scope for S1-S6;
- Store-owned domain boundary;
- Store-owned business configuration model;
- initial data model;
- operation inventory and audiences;
- Store permission model;
- public route inventory;
- cart/session decision;
- public mutation ingress decision;
- anonymous rate-limit decision;
- product media upload/serving audit;
- payment and shipping connector boundaries;
- backup/restore classification;
- threat model;
- Core gap report.

### S0 acceptance

S0 is complete only when we can answer:

- Can catalog CRUD be implemented with current Application Extension operations?
- Which settings are Store-owned and which are true platform bindings?
- Can public catalog pages be implemented entirely through M19?
- Can a browser on the isolated public origin reach declared public commands without exposing the whole Core/Admin API?
- What generic ingress contract is used for public mutations?
- What is the guest cart identity/token strategy?
- Is generic anonymous rate limiting sufficient for login/checkout abuse cases?
- Do we need customer accounts in the first product version?
- Are media upload/serve limits sufficient?
- Can checkout/order creation be transactional and idempotent inside extension-owned SQLite?
- Can payment providers be implemented with current connector/secret contracts?
- Can Store be installed, upgraded, disabled, backed up and restored without Store-specific Core code?

Any `NO` becomes a documented generic platform gap.

**No Core code is changed during S0 merely to make the Store easier to implement.**

---

## S1 — Catalog MVP

**Goal:** a real installable Store extension that can manage and publish a catalog.

Scope:

- categories;
- products;
- SKU;
- active/archive state;
- price in minor units;
- one currency;
- basic product media;
- optional simple variants if they fit cleanly;
- basic inventory;
- operator/admin catalog UI;
- public home/category/product pages;
- 404 and slug redirect behavior;
- deterministic package build;
- extension-owned migrations.

Not in S1:

- cart;
- customer accounts;
- checkout;
- payment;
- shipping-provider APIs;
- advanced promotions.

### S1 acceptance

- package installs through normal Extensions lifecycle;
- no Core changes are required by Store semantics;
- product/category data survives service/Core restart;
- operator permissions work without global admin;
- public product/category pages render through M19;
- disabling Store removes public ownership while preserving Store data;
- backup/restore preserves catalog and required media;
- failed Store service leaves 3mm Admin usable.

---

## S2 — Cart and order draft

**Goal:** build a safe public shopping flow without payment dependency.

Scope:

- guest cart;
- opaque cart token;
- add/update/remove items;
- authoritative price recalculation;
- stock validation;
- checkout preview;
- contact/shipping data needed for an order;
- idempotent order creation;
- order/order-item snapshots;
- public order reference/status model.

### S2 acceptance

- repeated commands cannot accidentally duplicate an order;
- changing browser-submitted price does not alter authoritative totals;
- expired/invalid cart tokens fail safely;
- restart preserves carts/orders according to retention policy;
- no Store-specific Core endpoint is introduced.

---

## S3 — Checkout primitives

**Goal:** make order totals and order state complete before integrating real payment providers.

Scope:

- shipping methods;
- simple configured tax policy;
- discounts/coupons if required;
- order state machine;
- inventory reservation/deduction rules;
- cancellation;
- operator order management;
- deterministic total/rounding tests.

### S3 acceptance

Every total can be reproduced from persisted order snapshots and explicit Store rules.

---

## S4 — Payments and external connectors

**Goal:** integrate one real payment flow through generic connector/secret boundaries.

Scope:

- provider adapter inside Store;
- administrator connector configuration;
- secret reference;
- payment attempt state;
- redirect/return flow where applicable;
- idempotency/reconciliation;
- failure and ambiguous-outcome handling;
- refund support only if required by the first provider/product.

### S4 acceptance

- Core contains no provider-specific behavior;
- provider credentials never reach frontend or logs;
- ambiguous network outcomes cannot create duplicate charges;
- Store remains administrable when provider is down.

---

## S5 — Administration and operations

**Goal:** make Store practical for daily use.

Scope may include:

- order filters;
- inventory alerts;
- bulk catalog operations;
- import/export;
- customer administration if accounts are implemented;
- operational dashboard;
- reports;
- refund/manual-review workflow;
- data export/erasure;
- richer diagnostics.

Performance work must be driven by measured Store workloads.

---

## S6 — Public website quality

**Goal:** make the public storefront application-quality without moving website semantics into Core, and separately validate the trusted public ingress/TLS boundary required for real Internet production.

Scope:

- complete metadata;
- canonical URLs;
- structured data;
- XML discovery resources;
- robots policy;
- redirects;
- cache headers;
- optimized media;
- responsive storefront;
- accessibility;
- locale/content strategy;
- performance budget.

SEO behavior is Store-owned.

Core continues to provide only the generic M19 public transport/ownership contract.

---

# Package guidance

The official Store module ID for this repository should be:

```text
org.3mm.store
```

Keep that identity stable once the first installable package is published.

A Store package follows Module Manifest v2 + Application Extension v1. From S1 onward, because the Store has management UI, it should target both `core` and `ui`.

## S1 manifest shape

Illustrative `manifest.json`:

```json
{
  "manifest_version": 2,
  "module_id": "org.3mm.store",
  "name": "3mm Store",
  "version": "0.1.0",
  "runtimes": ["core", "ui"],
  "entrypoints": {
    "core": "application-extension.json",
    "ui": "compiled-ui.json"
  },
  "compatibility": {
    "protocol": "1.0",
    "core": ">=0.3.0",
    "architectures": ["any"]
  },
  "capabilities": {
    "provides": [],
    "consumes": []
  },
  "permissions": [
    "data.read",
    "data.write",
    "process.spawn"
  ],
  "configuration_schema": {
    "type": "object",
    "additionalProperties": false,
    "properties": {}
  },
  "configuration_defaults": {},
  "registrations": [],
  "health_check": {
    "type": "json_file",
    "path": "application-extension.json"
  }
}
```

The manifest permission set is not advisory. The current package validator derives the exact required permissions from `application-extension.json` and rejects mismatches.

Store business configuration such as store name, public base URL, tax display choices and order-number policy should normally live in Store-owned SQLite and be managed through administrator operations. Reserve manifest configuration for platform-level bindings/configuration that the host contract actually owns.

Examples:

- base supervised application: `data.read`, `data.write`, `process.spawn`;
- declared connectors add `network.outbound`;
- connector secret references add `secrets.use`;
- event subscriptions add `events.consume`;
- emitted application events add `events.publish`;
- device command bindings add `capabilities.invoke`.

Do not add permissions pre-emptively.

## Minimal valid Application Extension contract

`operations` cannot be empty. At minimum the service needs its declared internal health query.

For an S1 catalog-only package that does **not yet store customer/order personal data**, a minimal valid shape is:

```json
{
  "application_extension_version": 1,
  "module_id": "org.3mm.store",
  "version": "0.1.0",
  "service": {
    "artifact": "service/three_mm_store-0.1.0-py3-none-any.whl",
    "artifact_sha256": "<build-time-sha256>",
    "entrypoint": "three_mm_store.service:create_service",
    "sdk_version": "1.3",
    "health_operation_id": "health"
  },
  "operations": [
    {
      "operation_id": "health",
      "kind": "query",
      "audiences": ["internal"],
      "idempotency": "forbidden",
      "input_schema": {
        "type": "object",
        "properties": {},
        "required": [],
        "additionalProperties": false
      },
      "output_schema": {
        "type": "object",
        "properties": {
          "status": {
            "type": "string",
            "enum": ["ready"]
          }
        },
        "required": ["status"],
        "additionalProperties": false
      }
    }
  ],
  "routes": [],
  "public_http_routes": [],
  "storage": {
    "schema_revision": "0001",
    "migration_entrypoint": "three_mm_store.migrations:get_migrations",
    "classifications": ["private"],
    "contains_personal_data": false
  }
}
```

S1 then adds the actual catalog operations, compiled UI route declarations and M19 public route handler.

## Personal-data transition

Do **not** set:

```json
"contains_personal_data": true
```

without also implementing the required data-lifecycle contract.

The current validator requires all three when personal data is declared:

- `retention_operation_id` -> internal `job`;
- `export_operation_id` -> administrator `command`;
- `erasure_operation_id` -> administrator `command`.

Therefore the natural transition is:

- S1 catalog only: `contains_personal_data: false`;
- S2/S3, once customer/contact/address/order-personal data is introduced: set it to `true` and add retention/export/erasure operations in the same reviewed package change.

## Public HTTP route handler contract

Every M19 `public_http_routes` entry must point to an operation that is exactly:

- `kind: "query"`;
- `audiences: ["public"]`;
- `idempotency: "forbidden"`;
- input schema equal to the platform v1 public HTTP request schema;
- output schema equal to the platform v1 public HTTP response schema.

Do not invent a custom request/response schema for the render handler.

## Compiled UI

If `application-extension.json` declares application `routes`, the module must have the UI runtime and `compiled-ui.json`.

`compiled-ui.json` route entrypoints provide the Vue source/route identity. Authorization remains in `application-extension.json`; do not use compiled-UI `requires_role` as the Store authorization model.

The installable package contains UI source under:

```text
source/frontend/
```

The current validator accepts `.vue`, `.ts`, `.js`, `.css` and `.json` source files there.

The service wheel is loaded directly by the supervised host. Activation does not run `pip install` or fetch dependencies from the Internet. Store service code should therefore use the 3mm SDK/standard library or bundle reviewed pure-Python dependencies inside its wheel when appropriate; adding arbitrary runtime dependency installation is not part of the Store contract.

## Package limits

Current module package validation is bounded:

```text
ZIP size:        <= 10 MiB
expanded size:   <= 40 MiB
file count:      <= 256
```

Do not bundle customer/product runtime media into the immutable module ZIP. Runtime media belongs in the Store extension data area and participates in backup according to the application data rules.

Add operations, routes, connectors and jobs incrementally as their contracts are implemented and tested. Do not declare the complete future Store API in the first package.

---

# Testing strategy

Each stage needs tests at several boundaries.

## Contract tests

Validate:

- manifest;
- operation schemas;
- audience;
- idempotency;
- public route conflicts;
- public response content types/statuses;
- migration declarations.

## Service tests

Use temporary Store SQLite state and deterministic clock/random providers where useful.

Cover:

- constraints;
- transactions;
- money arithmetic;
- slug rules;
- inventory;
- cart behavior;
- idempotency;
- order snapshots;
- migrations.

## Integration tests

Exercise Store through the real generic 3mm boundaries rather than importing Store functions into Core tests.

Examples:

- activate package;
- invoke operator operation;
- invoke public operation through the accepted public-interaction ingress once that contract exists;
- render public page through M19;
- disable/re-enable;
- service crash;
- connector failure;
- backup/restore;
- broken upgrade rollback.

## Physical acceptance

Before calling a meaningful Store stage complete, verify on the target Raspberry/3mm installation:

- install package;
- activate;
- Store service healthy;
- public routes work;
- Admin remains healthy when Store fails;
- restart recovery;
- disable/re-enable;
- backup/restore where relevant;
- resource impact.

---

# Explicit anti-patterns

Do **not** reintroduce any of the following:

```python
from fastapi import APIRouter
from backend.db... import ...
from backend.utils.db_utils import get_db

router = APIRouter(prefix="/api/store")
context.register_router(router)
```

Do not create Store tables in Core DB.

Do not solve transaction problems by opening a Core DB session from the extension.

Do not add Store-specific routes to `backend/main.py`.

Do not add payment-provider credentials to package configuration.

Do not use `float` for persisted money.

Do not trust prices, totals, stock or authorization decisions sent by the browser.

Do not make a Core change because one Store task is inconvenient.

Also do not rely on legacy Store/shop heuristics that may still exist in older Core frontend helper code. The new Store must use the Application Extension v1 and M19 contracts only. Any legacy `/api/store/*` fallback or name-based Store detection is not part of the Store architecture and should be treated as separate technical debt, not as a supported Store API.

---

# Definition of success

The Store architecture is successful when a substantial e-commerce product can evolve inside its own repository and package while 3mm Core remains a generic platform.

Normal Store work should mean:

```text
change Store -> build Store package -> test -> install/upgrade Store
```

not:

```text
change Store -> patch Core -> patch Store -> release both together
```

Core changes are reserved for larger, reusable platform capabilities with their own neutral contracts, limits, tests and recovery behavior.