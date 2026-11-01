# API design

> **Scope:** contracts exposed over HTTP/REST, gRPC and GraphQL: resource modelling, versioning and compatibility, pagination and filtering, errors and status codes, idempotent semantics at the edge, edge validation and size limits, long-running operations, webhooks, schema-first tooling, gateway/BFF. **Hands off to:** dedup storage and replay mechanics → IDEM; client retries, timeouts, circuit breakers → RES; authn/authz, injection, SSRF → SEC; query/index side of pagination → DATA; HTTP caching headers and CDN → CACHE; rate-limit algorithms and capacity → SCALE; deploy sequencing of contract changes → OPS; service boundaries → ARCH; async consumers behind 202 → MSG.

## Contents
- Key decisions
- Best practices (API-BP-1…18)
- Bad practices (API-BAD-1…15)
- Anti-patterns (API-AP-1…6)
- Audit checklist (API-CHK-1…19)
- Go / Node.js notes

## Key decisions

| Decision | Options | Choose … when | Trade-off |
| --- | --- | --- | --- |
| Protocol | REST+JSON / gRPC (or Connect) / GraphQL | REST for public and partner APIs, browser clients, CDN-cacheable reads; gRPC for internal service-to-service with high RPS, streaming, polyglot codegen; GraphQL when many client shapes read a broad graph and clients are first-party | gRPC loses HTTP caching and needs gRPC-Web/Connect in browsers; GraphQL moves cost control, N+1 and caching into the server |
| Versioning | URI major (`/v1`) / media-type or header / date-pinned (`API-Version: 2026-10-01`) / unversioned additive-only | URI major for public APIs with rare breaking epochs; date-pinned when many long-lived integrators and frequent change (needs a response-transform layer); additive-only for internal APIs with contract tests | More versions = more code paths to test; unversioned relies on discipline and CI breaking-change checks |
| Pagination | offset+limit / opaque cursor (keyset) / page token (gRPC AIP-158) | Offset only for small bounded admin lists (< ~10k rows) that need jump-to-page; cursor for feeds, sync, large or frequently mutating sets | Cursors give no random access and no cheap total count |
| Partial update | PUT full replace / JSON Merge Patch (RFC 7396) / JSON Patch (RFC 6902) / FieldMask (gRPC) | Merge Patch for simple objects; JSON Patch when array element ops are needed; FieldMask for protobuf where absent vs default is ambiguous | Merge Patch cannot express "set to null" separately from "delete" or edit array items |
| Long-running work | synchronous / 202 + operation resource / callback webhook / streaming (SSE, gRPC stream) | Synchronous only if p99 < ~2–5 s and well under every proxy timeout; 202 when work is queued or can exceed that; webhook in addition for server-to-server integrators | Async adds a status resource, retention, and client polling logic |
| Error model | RFC 9457 `application/problem+json` / `google.rpc.Status` + details / GraphQL `errors[].extensions.code` | Match the protocol; one model per protocol across the whole estate | Custom formats force per-endpoint client parsing |
| Contract source of truth | schema-first (OpenAPI 3.1, protobuf, SDL) / code-first with generated spec | Schema-first with several consuming teams or any public API; code-first acceptable for one team/one consumer if the spec is generated and diffed in CI | Schema-first needs codegen discipline; code-first drifts silently without CI |
| Edge topology | single API gateway / BFF per client type / GraphQL federation | Gateway for cross-cutting concerns (TLS, authn, limits, routing); BFF when web and mobile need different aggregations; federation when many teams own parts of one graph | Each layer adds a hop and an owner; federation adds a router and schema governance |
| Event delivery to integrators | webhooks / pull events feed (`GET /events?after=`) / both | Both for anything business-critical: webhook as the low-latency signal, feed for reconciliation after outages | Feed requires event retention and a cursor contract |

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

## Audit checklist

| ID | Check | Evidence / search hints | Default severity |
| --- | --- | --- | --- |
| API-CHK-1 | Is there a machine-readable contract that matches the routes? (API-BP-14) | Glob `**/openapi*.{yaml,yml,json}`, `**/*.proto`, `buf.yaml`, `**/*.graphql`; Go: `oapi-codegen`, `ogen`, `swag` annotations, `gqlgen.yml`; Node: `@nestjs/swagger`, `@fastify/swagger`, `zod-openapi`, `tsoa`. Sample 3 routes against the spec. Fail: no spec, or spec stale vs router | Medium |
| API-CHK-2 | Does CI block breaking contract changes? (API-BP-14, API-BP-15, API-BAD-8) | `.github/workflows/*`, CI files for `buf breaking`, `oasdiff`, `openapi-diff`, `graphql-inspector`. Fail: absent while external or cross-team consumers exist | Medium (High for public APIs) |
| API-CHK-3 | Are error statuses and the error body consistent? (API-BP-2, API-BP-3, API-BAD-1, API-BAD-2) | Go: `c.JSON(200, gin.H{"error"`, `http.StatusOK` written in error branches, error middleware mapping; Node: `res.status(200).json({ error`, `success: false`, Express/Fastify/Nest error handlers, `application/problem+json`. Fail: errors with 2xx, or validation/not-found reaching 500 | Medium |
| API-CHK-4 | Do responses leak internals? (API-BAD-3) | Go: `http.Error(w, err.Error()`, `c.JSON(500, err)`, `c.String(…, err.Error())`; Node: `res.json(err)`, `err.stack`, `err.message` in responses, Express default handler with `NODE_ENV` not `production`. Confirm by triggering a DB error in staging | High |
| API-CHK-5 | Is every list endpoint paginated with a clamped max? (API-BP-4, API-BAD-4) | Enumerate list handlers; check `limit` parsing and clamping; Go: GORM `.Find(&items)` without `.Limit`, raw SQL without `LIMIT`; Node: `findMany(` without `take`, `find({})` without `.limit(`. Fail: unbounded query or unclamped user limit on a growing table | High (Medium if table is small and bounded) |
| API-CHK-6 | Do large or mutating collections use cursor pagination? (API-BAD-5) | grep `OFFSET`, `.Offset(`, `skip:`, `.skip(`, `page=`; check table sizes. Fail: offset on tables > ~100k rows or used for sync/export | Medium |
| API-CHK-7 | Are request bodies and query cost bounded? (API-BP-7) | Go: `http.MaxBytesReader`, gRPC `grpc.MaxRecvMsgSize`; Node: `express.json({ limit`, Fastify `bodyLimit`, `graphql-depth-limit`, `@escape.tech/graphql-armor`; ingress `proxy-body-size`, nginx `client_max_body_size`. Fail: `json.NewDecoder(r.Body)` with no reader limit and no proxy limit | Medium |
| API-CHK-8 | Is input validated into DTOs, not bound into persistence models? (API-BP-6, API-BAD-6) | Go: `validate:"` tags, `protovalidate`, `DisallowUnknownFields`; red flag `ShouldBindJSON(&model)` where model is a GORM struct. Node: zod/joi/class-validator with `whitelist: true, forbidNonWhitelisted: true`; red flags `create({ data: req.body })`, `Model.create(req.body)`, `Object.assign(entity, req.body)`. Confirm a privileged field is writable | High |
| API-CHK-9 | Do money-moving or create endpoints accept an idempotency key? (API-BP-8, API-BAD-9) | grep `Idempotency-Key`, `idempotency`; list payment/order/transfer handlers. Fail: none on endpoints where a duplicate moves money or ships goods | High (Critical if clients auto-retry, e.g. mobile SDKs) |
| API-CHK-10 | Are concurrent edits of shared resources protected? (API-BP-9) | grep `ETag`, `If-Match`, `412`, row `version` columns used in updates. Fail: last-write-wins on documents/config edited by several users | Medium |
| API-CHK-11 | Do long operations run async under proxy timeouts? (API-BP-10, API-BAD-10) | Handlers doing exports, report generation, bulk imports, third-party chains; compare p99 to ALB idle timeout (60 s default), nginx `proxy_read_timeout` (60 s), API Gateway (29 s default), Cloud Run request timeout. Fail: p99 near or above any of them | High |
| API-CHK-12 | Are rate limits enforced per client and signalled? (API-BP-11) | Go: `golang.org/x/time/rate`, `tollbooth`, `httprate`; Node: `express-rate-limit`, `@fastify/rate-limit`, `@nestjs/throttler`; gateway/WAF config. Fail: public API with no limiting, or 429 without `Retry-After` | High (Medium for internal) |
| API-CHK-13 | Are outbound webhooks queued, signed, retried and time-limited? (API-BP-12, API-BAD-11) | grep `webhook`, `hmac`, `signature`; locate the delivery code path. Fail: delivery inside the request/transaction, no signature, no retry, or no per-attempt timeout | High |
| API-CHK-14 | Are inbound webhooks verified over raw body with a freshness window and dedup? (API-BP-13, API-BAD-12) | Go: `hmac.Equal`, body read before JSON decode; Node: `crypto.timingSafeEqual`, `express.raw(` / `rawBody`, provider SDK verify helpers. Fail: no verification or `===` compare on re-stringified JSON | High (Critical if it triggers fulfilment or payment state) |
| API-CHK-15 | Are IDs, money and timestamps typed safely? (API-BP-17, API-BAD-14) | Spec/DTOs: `int64`/`bigint` IDs as JSON numbers, `float`/`double`/`number` amounts, timestamps without offset. Note `protojson` already emits int64 as strings | Medium (High for money) |
| API-CHK-16 | Are GET handlers side-effect free? (API-BAD-15) | Router GET routes whose handlers call `Exec`, `Save`, `.update(`, `.save(`, publish or email. Fail: state change on GET | Medium |
| API-CHK-17 | Is GraphQL hardened? (API-BP-7, API-AP-6) | Go gqlgen: `extension.FixedComplexityLimit`, `handler.NewDefaultServer` (introspection on); Node: `graphql-armor`, `depthLimit`, persisted queries, `dataloader`. Fail: public endpoint with no depth/cost limit or resolvers querying per item | High for public, Medium internal |
| API-CHK-18 | Do gRPC calls carry deadlines and semantic status codes? (API-BP-18) | Go: client calls with `context.Background()`/`TODO()` and no `WithTimeout`, `status.Error(codes.Unknown`, `codes.Internal` for bad input; Node `@grpc/grpc-js`: missing `deadline` option. Fail: no deadline on hot paths | Medium |
| API-CHK-19 | Are deprecations and the gateway/BFF kept honest? (API-BP-16, API-AP-3, API-AP-4) | `Deprecation`/`Sunset` headers, per-client usage metrics; gateway plugins/BFF code containing pricing, authorization or orchestration rules | Low (Medium if domain logic lives in the gateway) |

## Go / Node.js notes

- Go 1.22+ `net/http.ServeMux` supports method and wildcard patterns (`POST /orders/{id}`), enough for many services without a router; `http.MaxBytesReader` + `json.Decoder.DisallowUnknownFields()` are the edge-validation primitives.
- Go `encoding/json` cannot distinguish absent, `null` and zero by default — PATCH handlers need pointer fields or a nullable wrapper; `omitzero` (Go 1.24) helps responses; `encoding/json/v2` is experimental behind `GOEXPERIMENT=jsonv2` (Go 1.25).
- Go codegen: `oapi-codegen`/`ogen` (OpenAPI), `buf` + `connect-go` (gRPC that also speaks HTTP/1.1 + JSON, usable from browsers), `gqlgen` (schema-first GraphQL).
- Node `JSON.parse` turns large integers into lossy numbers; keep IDs as strings end to end. Multi-MB bodies parse synchronously on the event loop, so body limits protect latency for every concurrent request, not just memory.
- Express 4 does not catch rejected promises from async handlers (requests hang or the process crashes); Express 5 does. Express body-parser default limit is 100 kB, Fastify `bodyLimit` 1 MiB.
- Fastify's schema-based response serialisation drops properties not in the schema — a cheap guard against API-BAD-7; Nest needs `ValidationPipe({ whitelist: true, forbidNonWhitelisted: true })` for the same on input.
- tRPC/ts-rest give end-to-end types only between TypeScript codebases; for polyglot or public consumers publish OpenAPI/proto instead (API-AP-5).
- GraphQL hardening tooling is richer in Node (Apollo, Yoga, graphql-armor); in Go, gqlgen supports complexity limits but you assemble the rest yourself.
