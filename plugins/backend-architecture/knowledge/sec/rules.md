# Security — rules

> **Scope:** protecting the API, its data and its runtime: the OWASP API Security Top 10 (2023) as concrete checks, authentication and token handling, authorization models and tenant isolation, input handling and injection, password storage, secrets, transport security, browser-facing controls (CORS, CSRF, headers), security logging and audit trails, supply chain, container and cloud least privilege, data protection. **Hands off to:** rate-limit algorithms, timeouts, load shedding → RES · per-tenant quotas and isolation by cells → SCALE · response shape, versioning, error format, pagination contract → API · log pipeline, alerting, retention tooling → OBS · CI/CD pipeline, config delivery, image build/deploy mechanics → OPS · webhook replay/dedup semantics → IDEM · DB roles and schema details → DATA.

## Best practices

`SEC-BP-1` — **Authorize every object access against the caller, server-side (API1 BOLA).** Guessable or leaked IDs otherwise expose other users' data. How: scope the query itself, not a check afterwards: `WHERE id = $1 AND owner_id = $2` / `AND tenant_id = $2`; return 404 for objects the caller cannot see; random IDs (UUIDv4/v7) are not authorization; cover nested and bulk endpoints, exports, file URLs and GraphQL node resolvers.

`SEC-BP-2` — **Deny by default and enforce function-level authorization centrally (API5 BFLA).** Endpoints added without a check become public. How: router-level middleware requiring an explicit policy per route (unannotated route fails at startup or in a test), admin routes on a separate router/host with its own authn, one policy module or engine (OPA, Cedar, Casbin, OpenFGA) called from handlers, decisions logged; fail closed when the PDP is unreachable.

`SEC-BP-3` — **Derive tenant and user identity only from the verified credential, and enforce isolation in depth.** Trusting `X-Tenant-ID` or `userId` in the body lets any user switch tenants. How: tenant from token claims or session; repository layer requires a tenant-scoped context; Postgres RLS with `SET LOCAL app.tenant_id = ...` inside each transaction (works with transaction poolers, see SCALE-CHK-7) and a non-owner app role (`FORCE ROW LEVEL SECURITY`); cross-tenant tests in CI.

`SEC-BP-4` — **Use standard OIDC/OAuth 2.x flows as profiled by the OAuth Security BCP (RFC 9700).** Legacy flows leak tokens. How: authorization code + PKCE for every client (including confidential), exact redirect URI matching, `state`/`nonce` checked, no implicit or resource-owner-password grants, client-credentials for machine-to-machine, `private_key_jwt` or mTLS client auth over shared secrets where supported.

`SEC-BP-5` — **Verify tokens fully, with a pinned algorithm.** A decoded-but-unverified or algorithm-confused JWT is a forged identity. How: verify signature with an allowlisted `alg` (e.g. `RS256`/`ES256`/`EdDSA`), validate `iss`, `aud`, `exp`, `nbf` with ≤60 s skew; fetch keys from the issuer's JWKS by `kid` with caching and refresh-on-unknown-kid; ignore `jku`/`x5u`/embedded `jwk` headers; reject `none`; never use one HMAC secret across services; opaque tokens → introspection with caching.

`SEC-BP-6` — **Keep credentials short-lived and revocable.** Stolen long-lived tokens give long-lived access. How: access tokens 5–15 min; refresh tokens rotated on every use with reuse detection (reuse of an old refresh token revokes the whole family), absolute lifetime cap; server sessions with idle (15–30 min for sensitive apps) and absolute timeouts, regenerate session ID on login and privilege change; revoke on password change, logout and admin action; API keys hashed at rest, prefixed for secret scanning, scoped, expiring.

`SEC-BP-7` — **Store passwords with a memory-hard, salted KDF and harden login (API2).** Fast hashes fall to GPU cracking within hours. How: argon2id (OWASP minimum m=19 MiB, t=2, p=1; tune to ~100–250 ms) or bcrypt cost ≥10–12 (72-byte input limit: reject longer or pre-hash with HMAC and a server pepper); rehash on login when parameters change; length ≥15 when password is the only factor, ≥8 with MFA, no composition rules, block breached passwords (NIST SP 800-63B-4, HIBP k-anonymity API); rate limit per account and per IP, generic error messages, uniform response timing, MFA/passkeys (WebAuthn) for privileged users; same rigour on reset and recovery flows (single-use, short-lived, hashed reset tokens).

`SEC-BP-8` — **Bind requests and responses to explicit DTOs (API3 BOPLA).** Decoding into domain models enables mass assignment; serialising them leaks internal fields. How: separate input structs/schemas per operation listing writable fields only; reject unknown fields; output DTOs or serializer allowlists per role; never return password hashes, internal flags, other users' PII, or full objects where a summary suffices; field-level authorization for sensitive properties (e.g. only admins see `email`).

`SEC-BP-9` — **Validate input at the boundary and keep data out of code paths (injection).** Every interpreter fed with strings is an injection point. How: schema validation of type, length, range, format and enums (Go `go-playground/validator` or generated OpenAPI validators; Node `zod`, `valibot`, `ajv`, Fastify schemas); SQL only via placeholders (identifiers such as sort columns via allowlist maps); commands via argument vectors without a shell and with `--` before user arguments; HTML via auto-escaping templates, never rendering user-supplied templates; NoSQL filters built from typed values (reject objects/operators where a string is expected); file paths confined to a root (`os.Root` in Go 1.24+, `path.resolve` + prefix check in Node); XML parsers with external entities disabled.

`SEC-BP-10` — **Bound resource consumption per request, per caller and per business flow (API4, API6).** Unbounded inputs and unprotected flows mean outages, bills and abuse. How: body size limits (Go `http.MaxBytesReader`, Express `json({ limit })` default 100 kb), upload size/type limits, decompression ratio limits, `ReadHeaderTimeout` and request timeouts, max page size, GraphQL depth/complexity/alias limits and disabled introspection in production for private APIs, rate limits per account/API key/IP (RES); for sensitive flows (signup, checkout, coupons, SMS/email sending, password reset) add business-level limits, bot detection, step-up verification and spend caps on paid third-party calls.

`SEC-BP-11` — **Contain server-side requests to user-supplied URLs (API7 SSRF).** Fetching attacker-chosen URLs reaches metadata endpoints and internal services. How: allowlist hosts/schemes where possible; otherwise resolve DNS, reject private, loopback, link-local (169.254.0.0/16, incl. 169.254.169.254), CGNAT and IPv6 ULA/mapped ranges, and connect to the vetted IP (check in the dialer to defeat DNS rebinding); disable or re-validate redirects; route through an egress proxy with its own allowlist; enforce IMDSv2 with hop limit 1; timeouts and size limits on the response.

`SEC-BP-12` — **Treat third-party APIs and inbound webhooks as untrusted (API10).** Compromised or spoofed upstreams inject data and actions. How: TLS verification always on; validate and size-limit upstream responses like user input; do not follow redirects blindly; verify webhook signatures (HMAC over raw body, constant-time compare, timestamp tolerance ~5 min, replay protection → IDEM); pin expected schemas; least-privilege, per-integration credentials.

`SEC-BP-13` — **Keep secrets out of code, images and git; rotate them.** Leaked repos, images and CI logs are the commonest breach source. How: secret manager (Vault, AWS Secrets Manager, GCP Secret Manager, Azure Key Vault) or SOPS/sealed secrets for GitOps; workload identity instead of static cloud keys; `.env` files only for local dev and in `.gitignore`, with a committed `.env.example`; pre-commit and CI secret scanning (gitleaks, trufflehog, GitHub push protection); build secrets via BuildKit `--mount=type=secret`, never `ARG`/`ENV`; dynamic short-lived DB credentials where possible; documented rotation and a revoke-first runbook for leaks (rewriting git history does not un-leak).

`SEC-BP-14` — **Encrypt and authenticate every hop.** Plaintext internal traffic is readable after any foothold. How: TLS 1.2+ (prefer 1.3) at the edge with HSTS; TLS to databases, caches and brokers (`sslmode=verify-full`); mTLS between services via mesh (Istio, Linkerd) or SPIFFE/SPIRE with short-lived certs and automated rotation; certificates verified against a pinned CA for private PKI rather than disabling verification.

`SEC-BP-15` — **Configure browser-facing controls deliberately (API8).** Misconfigured CORS and cookies turn the browser into the attacker's client. How: CORS with an explicit origin allowlist, credentials only for those origins, `Vary: Origin`; cookies `HttpOnly; Secure; SameSite=Lax` (or `Strict`), `__Host-` prefix for session cookies; CSRF defence for cookie-authenticated state-changing requests (synchronizer or double-submit token, or Fetch Metadata `Sec-Fetch-Site` checks, e.g. Go 1.25 `http.CrossOriginProtection`); headers: HSTS, `X-Content-Type-Options: nosniff`, `Content-Security-Policy: default-src 'none'; frame-ancestors 'none'` for JSON APIs, `Referrer-Policy`, `Cache-Control: no-store` on sensitive responses; generic error bodies without stack traces.

`SEC-BP-16` — **See OBS-BP-4, OBS-BP-16 (canonical mechanism).** Verify coverage and access controls for authentication, privilege changes and sensitive actions; diagnostics are not the audit trail.

`SEC-BP-17` — **Secure the supply chain.** Dependency and build compromise bypass every code review. How: committed lockfiles (`go.sum`, `package-lock.json`/`pnpm-lock.yaml`) and reproducible installs (`npm ci`, `-mod=readonly`); vulnerability scanning with reachability where available (`govulncheck`, `npm audit --omit=dev`, OSV-Scanner, Trivy/Grype on images) failing CI on fixable High/Critical; Dependabot/Renovate with a minimum release age (e.g. 3–7 days) to dodge freshly hijacked versions; npm lifecycle scripts disabled by default (pnpm ≥10 default, `ignore-scripts=true` with an allowlist); SBOM (Syft, CycloneDX) and signed images/provenance (cosign, SLSA) verified at admission; SAST (gosec, Semgrep, CodeQL) on PRs; pinned CI actions by commit SHA.

`SEC-BP-18` — **Run with least privilege: process, container, cluster, cloud.** Every unneeded privilege enlarges the blast radius of an RCE. How: minimal images (distroless, Chainguard/Wolfi, `scratch` for static Go), non-root `USER 65532`, `runAsNonRoot`, `readOnlyRootFilesystem: true` (writable `emptyDir` only where needed), `allowPrivilegeEscalation: false`, `capabilities.drop: ["ALL"]`, `seccompProfile: RuntimeDefault`, `automountServiceAccountToken: false` unless needed, Pod Security Admission `restricted`, NetworkPolicies default-deny; one IAM role per service scoped to specific actions and resources (no `*`), separate DB roles for app (DML only), migrations (DDL) and read-only access.

`SEC-BP-19` — **Minimise, encrypt and expire data.** Data you do not hold cannot leak. How: collect only fields with a purpose; classify data (public/internal/confidential/restricted) and map where each class lives (DB, logs, backups, analytics, search, caches); KMS-backed encryption at rest everywhere, envelope field-level encryption for restricted fields with blind indexes for lookup; retention periods enforced by TTL jobs or partition drops including backups and replicas; crypto-shredding (per-tenant/per-user keys) for deletion requests; pseudonymise data copied to non-production.

`SEC-BP-20` — **Maintain an API and environment inventory (API9, API8).** Forgotten versions and debug endpoints become the soft entry point. How: OpenAPI/proto specs generated or checked in CI against the router; every host, version and endpoint has an owner and lifecycle; deprecated versions removed on schedule; pprof, metrics, health details, Swagger UI, GraphQL playgrounds and admin tools off the public listener; non-production environments with no production data or credentials; secure defaults in config (debug off, verbose errors off) with a production config check at startup.

`SEC-BP-21` — **Declare domain authorization invariants once and enforce them at the policy chokepoint.** Rules such as "an elevated role does not act on the actor's own record", "the approver differs from the requester" or "a role acts only through its relationship to the target" protect integrity, not only confidentiality; re-implemented per module, they drift, and a bulk, import, CLI, job or newly added module path omits them. How: derive the invariants from the target project's own requirements, specs and ADRs (this skill does not prescribe domain rules); express each as a property of the action/permission declaration (for example "not on self", "distinct approver required") evaluated in the central policy; keep a table-driven test that enumerates every declared action × role × target relation, including target = actor and targets tied to the actor; add a database or policy-engine predicate as defence in depth where the store enforces authorization. Verification: the matrix test fails when a new action has no decision for the self case.

`SEC-BP-22` — **Separate duties on irreversible, high-impact decisions when the domain requires it.** One principal preparing, changing and approving an outcome removes the only independent check. How: identify irreversible or externally visible decisions (approvals, payouts, published results, privilege grants); record who prepared or modified what; refuse approval by a principal who prepared or modified the subject where the domain's rules call for maker-checker. Applicability: the requirement comes from the target domain; where the owner explicitly accepts single-actor approval, record the acceptance instead of a finding; where the specs are silent, raise an owner question.

## Bad practices

`SEC-BAD-1` — **Decoding a JWT without verifying it** (Node `jwt.decode(`, Go `jwt.ParseUnverified`, base64-splitting the token, trusting claims from an upstream that did not verify). Anyone can mint an identity. → Instead: SEC-BP-5.

`SEC-BAD-2` — **Algorithm taken from the token header** (no `algorithms`/`WithValidMethods`, a key function returning the same key for any `alg`, accepting `none`, HS256 verified with an RSA public key as HMAC secret). → Instead: pinned algorithms (SEC-BP-5).

`SEC-BAD-3` — **Identity or role taken from the request** (`userId`/`tenantId`/`role` in body, query or custom header used for authorization; admin checks only in the frontend). → Instead: SEC-BP-1, SEC-BP-2, SEC-BP-3.

`SEC-BAD-4` — **Request body decoded into domain/ORM models or passed straight to updates** (Go `json.NewDecoder(r.Body).Decode(&user)` with `Role`/`IsAdmin`/`TenantID` fields, GORM `Updates(bodyMap)`; Node `Object.assign(entity, req.body)`, `{...req.body}`, `prisma.user.update({ data: req.body })`). → Instead: SEC-BP-8.

`SEC-BAD-5` — **Returning ORM entities or full rows** (`res.json(user)`, `json.Marshal(dbUser)`) and relying on the client to hide fields. Hashes, tokens and internal fields leak. → Instead: output DTOs (SEC-BP-8).

`SEC-BAD-6` — **SQL built from strings** (Go `fmt.Sprintf("... WHERE x = '%s'")`, `db.Raw(fmt.Sprintf`, GORM `Where(fmt.Sprintf`/`Order(userInput)`; Node template literals in `query(`, `$queryRawUnsafe`, `knex.raw` with interpolation, `sequelize.query` with `${}`). → Instead: placeholders and identifier allowlists (SEC-BP-9).

`SEC-BAD-7` — **Shell commands with user input** (Go `exec.Command("sh", "-c", ...)`; Node `child_process.exec(`/`execSync(`, `spawn(..., { shell: true })`), or user values that can start with `-` passed as arguments. → Instead: argv form without shell, `--` separator, allowlists (SEC-BP-9).

`SEC-BAD-8` — **Unsafe template and dynamic code use** (Go `text/template` for HTML, `template.HTML(userInput)`, parsing user-supplied templates; Node `<%-` in EJS, `{{{ }}}` in Handlebars, `eval`, `new Function`, `vm` treated as a sandbox, `_.template` on user input). → Instead: auto-escaping templates, no user-authored templates (SEC-BP-9).

`SEC-BAD-9` — **Passwords hashed with MD5/SHA-1/SHA-256 (even salted) or encrypted reversibly; bcrypt fed >72 bytes silently.** → Instead: SEC-BP-7.

`SEC-BAD-10` — **Secrets committed or baked in** (`.env` in git, keys in `config.yaml`, Dockerfile `ENV API_KEY=`/`ARG` secrets, secrets in k8s manifests as plain `Secret` YAML in the repo, CI logs echoing them). → Instead: SEC-BP-13.

`SEC-BAD-11` — **TLS verification disabled** (Go `InsecureSkipVerify: true`; Node `rejectUnauthorized: false`, `NODE_TLS_REJECT_UNAUTHORIZED=0`; `sslmode=disable`/`require` without verify). Any network attacker can intercept. → Instead: SEC-BP-14.

`SEC-BAD-12` — **Permissive CORS** (`cors({ origin: '*' })` on cookie-authenticated APIs, origin reflected from the request with `credentials: true`, `Access-Control-Allow-Origin: null` accepted, regex allowlists like `/example\.com/` matching `example.com.evil.net`). → Instead: SEC-BP-15.

`SEC-BAD-13` — **Secrets and PII in logs and error responses** (logging `req.headers`, full bodies, DSNs with passwords; stack traces and SQL errors returned to clients). → Instead: SEC-BP-16, SEC-BP-15.

`SEC-BAD-14` — **Non-constant-time comparison of secrets** (`==`/`===`/`bytes.Equal` on HMACs, API keys, reset tokens). Enables timing attacks. → Instead: Go `hmac.Equal`/`subtle.ConstantTimeCompare`, Node `crypto.timingSafeEqual` on equal-length buffers.

`SEC-BAD-15` — **Weak randomness for security values** (Go `math/rand`, Node `Math.random()` for tokens, IDs used as secrets, OTPs). → Instead: `crypto/rand` (`rand.Text()` in Go 1.24+), Node `crypto.randomBytes`/`randomUUID`, ≥128 bits for tokens.

`SEC-BAD-16` — **Container running as root with a writable filesystem and full capabilities** (no `USER` in Dockerfile, no `securityContext`, `privileged: true`, `hostPath` mounts, Docker socket mounted). → Instead: SEC-BP-18.

## Anti-patterns

`SEC-AP-1` — **Perimeter-only trust.**
- Symptoms: "the gateway handles auth"; services accept any call from inside the VPC/cluster; internal endpoints without authn; identity forwarded as a plain `X-User-Id` header.
- Why it hurts: one SSRF, compromised pod or misrouted ingress gives full access; lateral movement is free.
- Way out: zero-trust posture: mTLS workload identity (SEC-BP-14), services verify a signed end-user/caller token and enforce authorization themselves (SEC-BP-2), NetworkPolicies default-deny.

`SEC-AP-2` — **Authorization scattered as ad-hoc `if`s.**
- Symptoms: role checks copy-pasted per handler with variations; some endpoints missing them; no list of who can do what; tests cover the happy path only.
- Why it hurts: BOLA/BFLA gaps appear with every new endpoint; policy changes require touching dozens of files.
- Way out: central policy module or engine (SEC-BP-2), deny-by-default middleware, a permission matrix test enumerating roles × endpoints × ownership.

`SEC-AP-3` — **Homegrown authentication and crypto.**
- Symptoms: custom token formats, hand-written password reset flows, AES in ECB/CBC without MAC, self-made JWT parsing, "encryption" with static IVs.
- Why it hurts: subtle mistakes are invisible until exploited; the team owns every future vulnerability.
- Way out: OIDC provider (SEC-BP-4), vetted libraries (AEAD via Tink, libsodium, Go `crypto/cipher` GCM with random nonces), cloud KMS for keys.

`SEC-AP-4` — **Shared god credentials.**
- Symptoms: one DB superuser for app, migrations and humans; one IAM role or API key used by all services; admin token in a shared password manager entry; long-lived cloud access keys on laptops and CI.
- Why it hurts: one leak compromises everything; audit trails cannot attribute actions; rotation is avoided because it breaks everything.
- Way out: per-service identities and roles (SEC-BP-18), workload identity and OIDC federation for CI (no static keys), named human access via SSO with just-in-time elevation.

`SEC-AP-5` — **JWT as an irrevocable session.**
- Symptoms: hours- or days-long access tokens in `localStorage`; logout only deletes the client copy; permissions and PII embedded in claims and trusted until expiry.
- Why it hurts: stolen tokens (XSS, logs, devices) cannot be revoked; role removals take effect only at expiry; PII leaks wherever the token travels.
- Way out: server sessions or BFF for browsers, short access tokens with rotating refresh (SEC-BP-6), minimal claims with permissions resolved server-side.

`SEC-AP-6` — **Tenant isolation by convention.**
- Symptoms: every query must "remember" `AND tenant_id = ?`; raw SQL and reports skip it; background jobs run without tenant context; caches keyed without tenant.
- Why it hurts: one forgotten clause is a cross-tenant breach, often Critical and reportable.
- Way out: tenant-scoped repositories that cannot be constructed without a tenant, RLS as a backstop (SEC-BP-3), tenant-prefixed cache keys, cross-tenant access tests.

`SEC-AP-7` — **Logs and analytics as an ungoverned PII lake.**
- Symptoms: request/response bodies logged "for debugging"; production DB dumps in staging and analytics; no retention or access controls on log stores.
- Why it hurts: breach surface and regulatory exposure (GDPR, HIPAA) far beyond the primary database, usually with weaker access control.
- Way out: redaction at source (SEC-BP-16), data classification and retention for every store (SEC-BP-19), synthetic or pseudonymised non-production data.

`SEC-AP-8` — **Cross-cutting rule re-implemented per module.**
- Symptoms: the same guard (`if target == caller`, "not own record", "distinct approver", "only in state X") is hand-written in some handlers or services but absent in others that reach the same state; bulk, import, batch, CLI or job paths bypass the per-endpoint check; a new module copies an older one without the guard.
- Why it hurts: the strongest-looking modules hide the hole in the weakest, and a reviewer who samples one path sees the guard and records a strength.
- Way out: one declaration evaluated centrally (SEC-BP-21); enumerate every writer of the guarded state (SEC-CHK-22); a matrix test over the whole registry.

## Go / Node.js notes

- Memory safety vs dynamic features: Go has no `eval` and a static type system, so mass assignment and injection come from explicit decoding and string building; Node adds prototype pollution (`__proto__`/`constructor.prototype` via deep merge of `req.body`: `lodash.merge` < 4.17.21, custom merges), so validate with schemas, use `Object.create(null)` or `Map` for user-keyed maps, and run with `--disable-proto=delete` where compatible.
- JWT libraries: Go `github.com/golang-jwt/jwt/v5` (use `WithValidMethods`, `WithAudience`, `WithIssuer`, `WithExpirationRequired`) or `lestrrat-go/jwx` with JWKS caching; Node `jose` (`jwtVerify` + `createRemoteJWKSet`) preferred over `jsonwebtoken` (v9+ rejects `none` by default, but still requires `algorithms`).
- Password hashing: Go `golang.org/x/crypto/argon2` (`IDKey`) or `bcrypt` (returns `ErrPasswordTooLong` above 72 bytes); Node `argon2` or `@node-rs/argon2` (async, off the event loop; `bcrypt` silently truncates at 72 bytes and `*Sync` variants block, see PERF-BAD-8).
- HTTP server defaults: Go `http.ListenAndServe` has no timeouts (Slowloris), so construct `http.Server` with `ReadHeaderTimeout`, `ReadTimeout`, `WriteTimeout`, `IdleTimeout`, `MaxHeaderBytes`; Node has `headersTimeout`/`requestTimeout` defaults (60 s/300 s) and Express body parsers default to 100 kb.
- CSRF and CORS: Go 1.25 `net/http.CrossOriginProtection` (Fetch Metadata based), `rs/cors`; Node `cors` with function-based allowlists, `csrf-csrf` or `csrf-sync` (the old `csurf` is deprecated), `helmet` for headers.
- Path traversal: Go 1.24+ `os.Root`/`os.OpenInRoot` confines file access; `filepath.Join` does not. Node: `path.resolve(base, input)` then verify it starts with `base + path.sep`; Express `res.sendFile` with `root` option.
- Scanners: `govulncheck` reports only vulnerabilities in reachable code, so its output is low-noise and CI-gateable; `npm audit` is advisory-based (no reachability), so gate on `--omit=dev` and fixable High/Critical, triage the rest. SAST: `gosec`, `staticcheck`; Node `eslint-plugin-security`, Semgrep rulesets for both.
- Static Go binaries run on `scratch`/distroless with no shell, which defeats many post-exploitation steps; Node needs the runtime, so use `node:*-slim` or distroless Node/Chainguard images, multi-stage builds with `npm ci --omit=dev`, and never ship the build toolchain.
