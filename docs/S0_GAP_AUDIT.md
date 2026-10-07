# S0 — Generic Platform Gap Audit

Status: **open**

Branch: `s0/store-foundation`

Module: `org.3mm.store`

## Purpose

S0 exists to prevent Store development from turning into repeated Store-specific
changes to 3mm Core.

Every Store requirement must first be mapped to an existing generic 3mm
contract. A Core change is considered only when a requirement cannot be met
safely through those contracts and the missing capability is reusable by other
Application Extensions.

No Store business feature is implemented during S0 merely to bypass an
unresolved platform boundary.

## Accepted platform baseline

Store is designed against the current 3mm platform after Milestone 19:

- Module Manifest v2;
- Application Extension v1 supervised service;
- extension-owned `ApplicationStorage` / SQLite;
- query, command and job operations;
- public, operator, administrator and internal audiences;
- extension-scoped permissions;
- compiled UI;
- connector and secret broker;
- lifecycle, backup, restore and rollback;
- isolated Public Web Runtime v1 for GET/HEAD content.

## Gap register

| ID | Area | Current status | S0 decision required |
| --- | --- | --- | --- |
| G1 | Public mutation ingress | **Open / likely platform gap** | Define how a browser on the isolated public origin invokes only declared public Application Extension commands without exposing the whole Core/Admin API. |
| G2 | Guest/public sessions | **Open** | Decide whether opaque Store-issued bearer cart tokens are sufficient for S2. If HttpOnly/SameSite sessions are required, define a generic public-session contract. |
| G3 | Anonymous abuse protection | **Open** | Decide whether ingress-level limits are sufficient for login/checkout/public commands or whether a generic public-operation rate-limit contract is required. |
| G4 | Product media | **Confirmed generic gap candidate** | S0.1 confirmed the 1 MiB Application RPC / 512 KiB M19 bounds and no generic Application Extension multipart/media-upload contract. Catalog work proceeds without a Store-specific workaround; design a reusable extension-media capability separately. |
| G5 | Public Internet ingress | **Open, not required for S1 local acceptance** | Define trusted reverse-proxy/origin/TLS binding before calling the Store Internet-production-ready. M19 itself proves only the isolated local public surface. |
| G6 | Store business settings | **No Core gap expected** | Keep Store name, public base URL, tax/display policy and similar settings in Store-owned state, managed by declared admin operations. Use manifest configuration only for platform-owned bindings. |
| G7 | Catalog/admin CRUD | **S0.1 closed — no Core gap** | The S1 schema, operations, permissions and compiled UI boundary are frozen in `S0_CATALOG_CONTRACT.md`. |
| G8 | Public catalog rendering | **S1.5 implemented — no Core gap** | Home/category/product pages and slug redirects use M19 GET/HEAD routes through one exact v1 public render operation. |
| G9 | Payment/shipping providers | **No Core gap expected initially** | Prove provider integration fits declared connector + secret boundaries. Provider semantics remain Store-owned. |
| G10 | Personal-data lifecycle | **No Core gap expected** | Before S2 introduces customer/contact/address personal data, implement retention/export/erasure operations required by Application Extension v1. |

See [S0.1 Catalog Contract](S0_CATALOG_CONTRACT.md) for the accepted S1 catalog boundary.

## Core-change gate

A proposal to change 3mm Core must satisfy all of these:

1. current generic contracts cannot safely implement the requirement;
2. the missing capability is useful beyond Store;
3. the proposed Core contract contains no product/cart/order/payment/provider semantics;
4. a neutral reference package or protocol test can prove it;
5. limits, authorization, compatibility, failure isolation and recovery are defined;
6. Store can consume the result without a module-ID-specific Core branch.

If any point fails, the change stays in Store or the design is revised.

## S0 decisions to freeze

Before S1 implementation begins, record explicit decisions for:

- catalog entity IDs and slug policy;
- money representation and one-currency S1 policy;
- Store-owned business settings;
- S1 product/category/inventory schema;
- compiled UI route and permission model;
- M19 public route inventory;
- media storage/upload/derivative strategy;
- public mutation ingress direction;
- guest cart identity strategy for S2;
- personal-data transition boundary;
- connector boundary for payment/shipping;
- backup/restore expectations;
- package/build/test workflow.

## S0 exit criteria

S0 is complete when:

- the first installable package contract can be described without Store-specific
  Core code;
- S1 catalog CRUD and public rendering have no unresolved platform dependency;
- every open Core-gap candidate is either resolved by existing contracts or
  promoted into a separately designed generic platform milestone;
- package identity, repository layout, storage ownership, permission model and
  testing boundary are frozen enough to start S1;
- no implementation relies on legacy `/api/store/*` behavior or name-based
  Store heuristics in old frontend helper code.

## Current rule

Do not patch Core during S0 just to make the first Store implementation easier.
