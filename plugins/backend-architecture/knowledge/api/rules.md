# API design — rules

> **Scope:** contracts exposed over HTTP/REST, gRPC and GraphQL: resource modelling, versioning and compatibility, pagination and filtering, errors and status codes, idempotent semantics at the edge, edge validation and size limits, long-running operations, webhooks, schema-first tooling, gateway/BFF. **Hands off to:** dedup storage and replay mechanics → IDEM; client retries, timeouts, circuit breakers → RES; authn/authz, injection, SSRF → SEC; query/index side of pagination → DATA; HTTP caching headers and CDN → CACHE; rate-limit algorithms and capacity → SCALE; deploy sequencing of contract changes → OPS; service boundaries → ARCH; async consumers behind 202 → MSG.

## Best practices

`API-BP-1` — **Model resources as nouns with stable, opaque, server-generated IDs; express non-CRUD actions as custom methods or sub-resources.** Why: verb URLs and RPC tunnelled through REST lose method semantics (safety, idempotency, caching). How: `POST /orders/{id}:cancel` (AIP-136 style) or `POST /orders/{id}/cancellation`; IDs as strings (`ord_01J…`), never raw DB auto-increments.

`API-BP-2` — **Use status codes by meaning so clients, retries and monitors behave correctly.** Why: retry logic (RES) keys off the class: 4xx is not retried except 408/429, 5xx/503 may be. How: 201 + `Location` on create, 202 for accepted async work, 204 for empty success, 400 malformed, 401 unauthenticated, 403 forbidden, 404, 409 state conflict, 412 failed `If-Match`, 415, 422 semantic validation, 429 and 503 with `Retry-After`; 500 only for genuine server faults.

`API-BP-3` — **Return errors as RFC 9457 problem details with stable machine codes.** Why: clients branch on codes, not English text; one shape across services. How: `Content-Type: application/problem+json` with `type` (stable documented URI), `title`, `status`, `detail`, `instance`, plus extensions `code`, `errors[]` (`pointer` as JSON Pointer to the field, `code`, `message`) and `trace_id`; never include stack traces, SQL or upstream hostnames (SEC).

`API-BP-4` — **Paginate every collection with an opaque cursor and a server-enforced maximum page size.** Why: unbounded lists become OOMs and full scans as data grows; offsets skip/duplicate items under concurrent inserts. How: `limit` default 50, clamp to 100–1000; cursor = base64 of last sort key (e.g. `(created_at, id)`), HMAC-signed or encrypted so clients cannot forge it; `next_cursor: null` at the end; total counts optional and capped/estimated. DB side → DATA-BP-11.

`API-BP-5` — **Whitelist filter and sort fields, back them with indexes, and reject unknown parameters.** Why: a misspelt filter silently ignored returns everything; arbitrary sort fields cause full scans. How: explicit grammar (`filter[status]=paid`, `sort=-created_at`, or AIP-160 filter strings) mapped to parameterised queries; 400 with a problem `code` for unknown or unsupported params.

`API-BP-6` — **Validate every request against the schema at the edge, before business logic.** Why: type/size/enum errors deep in the domain become 500s or injection vectors. How: OpenAPI/JSON Schema validators, `protovalidate` for protobuf; enforce `maxLength`, numeric ranges, `maxItems`, formats; bind to request DTOs, never to persistence models (mass assignment); decide the unknown-field policy explicitly (reject on public writes, or ignore but never persist). Domain invariants are still enforced in the domain and DB.

`API-BP-7` — **Bound request size and query cost at every layer.** Why: a single large JSON body or deep query exhausts memory or CPU (in Node it also blocks the event loop). How: JSON bodies ~1 MiB default, per-route overrides; large uploads go direct to object storage via pre-signed URLs; batch endpoints ≤ 100 items; gRPC `MaxRecvMsgSize` deliberate (default 4 MiB); GraphQL depth ≤ ~10 plus cost/complexity budget; header size limits at the proxy.

`API-BP-8` — **See IDEM-BP-1, IDEM-BP-2 (canonical mechanism).** Expose and document the operation identity, replay window and conflict response in the API contract.

`API-BP-9` — **Keep PUT and DELETE idempotent and protect contended updates with ETag/If-Match.** Why: last-write-wins silently loses concurrent edits (API-level lost update). How: strong `ETag` derived from a row version; mutating requests send `If-Match`; mismatch → 412; return 428 when `If-Match` is required but missing; repeated DELETE returns the same documented result (204, or 404 consistently).

`API-BP-10` — **Model long-running work as 202 Accepted plus an operation resource.** Why: requests longer than proxy timeouts (often 30–60 s) produce 504s while work continues, and client retries duplicate it. How: `202` + `Location: /operations/{id}` and `Retry-After`; operation has `status` (pending, running, succeeded, failed, cancelled), `progress`, `result` link or problem `error`, timestamps; retain 1–7 days; support `POST /operations/{id}:cancel`; combine with API-BP-8 so the create is idempotent.

`API-BP-11` — **See RES-BP-10 (canonical mechanism).** Document caller scope, 429 and Retry-After; keep limit implementation in RES.

`API-BP-12` — **Send webhooks from a durable queue, signed, retried, and verifiable.** Why: inline delivery couples your latency to customer endpoints and loses events on failure. How: follow the Standard Webhooks shape (`webhook-id`, `webhook-timestamp`, `webhook-signature` = HMAC-SHA256 over `id.timestamp.body`); at-least-once with exponential backoff over 24–72 h; 5–10 s timeout per attempt; event id for receiver dedup; auto-disable after sustained failure with notification; SSRF guard on target URLs (SEC-*); offer the events feed for replay.

`API-BP-13` — **See IDEM-BP-20, SEC-BP-12 (canonical mechanism).** At the HTTP boundary verify the raw payload and acknowledge only durable acceptance.

`API-BP-14` — **Keep the contract schema-first and gate it in CI.** Why: hand-maintained docs drift; breaking changes ship unnoticed. How: OpenAPI 3.1 / `.proto` / SDL in the repo; lint (Spectral, `buf lint`); breaking-change diff against main (`buf breaking`, `oasdiff`, `graphql-inspector`); generated servers/clients; contract tests for key consumers.

`API-BP-15` — **Evolve additively within a version and treat everything else as breaking.** Why: deployed clients cannot be upgraded in lockstep. How: allowed — new endpoints, new optional request fields, new response fields, new enum values only if clients were told to tolerate unknowns; breaking — removing/renaming/retyping fields, making optional required, tightening validation, changing defaults, semantics or error codes; protobuf: never reuse field numbers or names (`reserved`); clients are tolerant readers.

`API-BP-16` — **Deprecate with signals, telemetry and a dated sunset.** Why: removing an endpoint nobody measured breaks a silent integrator. How: `Deprecation` (RFC 9745) and `Sunset` (RFC 8594) headers plus a `Link` to the migration guide; per-client usage metrics; ≥ 6–12 months notice for public APIs.

`API-BP-17` — **Use interoperable value types.** Why: JS `number` loses integer precision above 2^53−1; binary floats corrupt money. How: IDs and int64 as strings in JSON; money as integer minor units or decimal string plus ISO 4217 currency; timestamps RFC 3339 in UTC; enums as strings; one casing convention across the API.

`API-BP-18` — **See RES-BP-1, API-BP-2 (canonical mechanism).** Propagate gRPC deadlines and map semantic failures to gRPC status codes.

## Bad practices

`API-BAD-1` — **200 OK with `{"success": false}` or an error body.** Monitors, caches, and client retry logic all see success; error rates vanish from dashboards. → Instead: correct status + problem details (API-BP-2, API-BP-3).

`API-BAD-2` — **Validation errors, not-found and conflicts surface as 500.** Unhandled exceptions map to 500, paging on-call and triggering client retries of permanently invalid requests. → Instead: typed domain errors mapped to 4xx in one error middleware (API-BP-2).

`API-BAD-3` — **Error responses expose internals** (`err.Error()`, stack traces, SQL, upstream URLs). Information leak and accidental contract (clients parse messages). → Instead: API-BP-3; log details server-side with the trace id.

`API-BAD-4` — **Unbounded or unclamped list endpoints** (`?limit=1000000` honoured, or no limit at all). Memory spikes, full scans, timeouts as tables grow. → Instead: API-BP-4.

`API-BAD-5` — **Deep offset pagination on large or hot collections.** Cost grows with offset; concurrent inserts cause skipped and duplicated items in sync jobs. → Instead: cursor pagination (API-BP-4).

`API-BAD-6` — **Binding request bodies straight into ORM/persistence models (mass assignment).** Clients set `role`, `tenant_id`, `price`, `is_verified`; DB schema becomes the API. → Instead: request DTOs with whitelisted fields (API-BP-6).

`API-BAD-7` — **Serialising internal entities as responses.** Leaks fields like `password_hash` or internal flags, and couples every schema change to the contract. → Instead: explicit response types or schema-driven serialisation (API-BP-1, API-BP-15).

`API-BAD-8` — **Breaking change shipped in place** (renamed field, newly required param, changed enum meaning, reused proto field number). Live clients fail or, worse, misinterpret data. → Instead: API-BP-15 with CI gate API-BP-14.

`API-BAD-9` — **Payment/order POST with no idempotency support.** A timeout + retry creates two charges or two orders. → Instead: API-BP-8 and IDEM.

`API-BAD-10` — **Minutes-long work inside a synchronous request.** Load balancer cuts at 30–60 s, client sees 504 and retries while the first run continues. → Instead: API-BP-10.

`API-BAD-11` — **Webhooks delivered inline in the request or transaction, with no timeout or retry.** A slow customer endpoint stalls your API; a failed attempt loses the event. → Instead: API-BP-12.

`API-BAD-12` — **Incoming webhooks accepted without signature and timestamp checks**, or HMAC computed on re-serialised JSON. Forged or replayed events; valid ones fail verification. → Instead: API-BP-13.

`API-BAD-13` — **Unknown query parameters silently ignored.** `?stauts=active` returns every record, including ones the caller did not mean to fetch or mutate in bulk. → Instead: API-BP-5.

`API-BAD-14` — **64-bit IDs or money as JSON numbers / floats.** JS clients round IDs; float sums drift by cents. → Instead: API-BP-17.

`API-BAD-15` — **GET with side effects** (`GET /orders/1/confirm`, tracking pixels that mutate state). Prefetchers, crawlers, caches and retries trigger the action. → Instead: POST custom method (API-BP-1).

## Anti-patterns

`API-AP-1` — **RPC tunnelling over HTTP.**
- Symptoms: one `POST /api` or `/rpc` endpoint with `{"action": "...", "params": {}}`; every call is POST; status always 200.
- Why it hurts: no method semantics, no HTTP caching, no per-route limits, auth or metrics; gateways and monitors are blind.
- Way out: if RPC is the real model, use gRPC/Connect properly with codes and deadlines; otherwise migrate actions to resources and custom methods behind a compatibility shim.

`API-AP-2` — **Table-shaped CRUD API (database as API).**
- Symptoms: endpoints mirror tables 1:1; clients orchestrate business flows (create order → add items → set status → reserve stock) across several calls.
- Why it hurts: invariants live in clients, partial failure leaves inconsistent state, no transaction spans the calls, schema cannot change.
- Way out: task-oriented endpoints per business operation on aggregates (`POST /orders` with items, `POST /orders/{id}:submit`), executed in one server-side transaction or saga (IDEM).

`API-AP-3` — **Copy-paste versioning.**
- Symptoms: `/v1`…`/v6` each with duplicated handlers and services; fixes applied to some versions only.
- Why it hurts: maintenance multiplies, security fixes miss old copies, nobody knows who uses what.
- Way out: one current implementation plus a thin version-transform layer at the edge (request/response migrations per version), usage telemetry, sunsets (API-BP-16).

`API-AP-4` — **Smart gateway / fat BFF.**
- Symptoms: business rules, pricing, authorization decisions or multi-service orchestration in gateway plugins or the BFF; domain teams must change the gateway to ship features.
- Why it hurts: a shared bottleneck owned by no domain, untested logic, every team blocked on one deploy.
- Way out: gateway keeps cross-cutting concerns only; BFF only aggregates and reshapes; move rules into owning services.

`API-AP-5` — **Shared code library as the contract.**
- Symptoms: consumers import the provider's internal Go package or npm models package to call it; contract changes require coordinated releases.
- Why it hurts: lockstep deploys, language lock-in, transitive dependency conflicts — a distributed monolith (ARCH).
- Way out: publish OpenAPI/proto/SDL; generate clients per consumer; version the schema, not the library.

`API-AP-6` — **Chatty client APIs.**
- Symptoms: one screen needs 10–50 sequential calls; N+1 across the network (`GET /orders` then `GET /orders/{id}/items` per row).
- Why it hurts: latency multiplies on mobile networks, load multiplies on servers, partial failures are common.
- Way out: compound documents (`?include=items`), batch reads (`GET /items?ids=…`), a BFF per client, or GraphQL with DataLoader batching.

## Go / Node.js notes

- Go 1.22+ `net/http.ServeMux` supports method and wildcard patterns (`POST /orders/{id}`), enough for many services without a router; `http.MaxBytesReader` + `json.Decoder.DisallowUnknownFields()` are the edge-validation primitives.
- Go `encoding/json` cannot distinguish absent, `null` and zero by default — PATCH handlers need pointer fields or a nullable wrapper; `omitzero` (Go 1.24) helps responses; `encoding/json/v2` is experimental behind `GOEXPERIMENT=jsonv2` (Go 1.25).
- Go codegen: `oapi-codegen`/`ogen` (OpenAPI), `buf` + `connect-go` (gRPC that also speaks HTTP/1.1 + JSON, usable from browsers), `gqlgen` (schema-first GraphQL).
- Node `JSON.parse` turns large integers into lossy numbers; keep IDs as strings end to end. Multi-MB bodies parse synchronously on the event loop, so body limits protect latency for every concurrent request, not just memory.
- Express 4 does not catch rejected promises from async handlers (requests hang or the process crashes); Express 5 does. Express body-parser default limit is 100 kB, Fastify `bodyLimit` 1 MiB.
- Fastify's schema-based response serialisation drops properties not in the schema — a cheap guard against API-BAD-7; Nest needs `ValidationPipe({ whitelist: true, forbidNonWhitelisted: true })` for the same on input.
- tRPC/ts-rest give end-to-end types only between TypeScript codebases; for polyglot or public consumers publish OpenAPI/proto instead (API-AP-5).
- GraphQL hardening tooling is richer in Node (Apollo, Yoga, graphql-armor); in Go, gqlgen supports complexity limits but you assemble the rest yourself.
