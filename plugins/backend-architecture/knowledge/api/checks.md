# API design — audit checklist

> **Scope:** contracts exposed over HTTP/REST, gRPC and GraphQL: resource modelling, versioning and compatibility, pagination and filtering, errors and status codes, idempotent semantics at the edge, edge validation and size limits, long-running operations, webhooks, schema-first tooling, gateway/BFF. **Hands off to:** dedup storage and replay mechanics → IDEM; client retries, timeouts, circuit breakers → RES; authn/authz, injection, SSRF → SEC; query/index side of pagination → DATA; HTTP caching headers and CDN → CACHE; rate-limit algorithms and capacity → SCALE; deploy sequencing of contract changes → OPS; service boundaries → ARCH; async consumers behind 202 → MSG.

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

## Also scan for (rules not cited above)

Bodies: `knowledge/api/rules.md`, looked up by ID.

- API-BAD-7 — Serialising internal entities as responses
- API-BAD-13 — Unknown query parameters silently ignored
- API-AP-1 — RPC tunnelling over HTTP
- API-AP-2 — Table-shaped CRUD API (database as API)
- API-AP-5 — Shared code library as the contract
