# Delivery & operations

> **Scope:** how code becomes a running, recoverable production system: configuration, CI gates, builds and artifacts, deploy strategies and rollback, migrations inside the deploy flow, compatibility during rollouts, process lifecycle in orchestrators, resources and autoscaling config, environments and IaC, backups/DR, on-call, dependency hygiene, delivery metrics and cost. **Hands off to:** secret storage, rotation and supply-chain signing policy → SEC; expand/contract schema mechanics and migration locking → DATA; health/readiness semantics and degradation → RES; scaling strategy and capacity models → SCALE; alerts, SLOs, runbook content and postmortems → OBS; contract design and versioning → API; deploy-independence as an architecture property → ARCH.

## Contents
- Key decisions
- Best practices (OPS-BP-1…20)
- Bad practices (OPS-BAD-1…16)
- Anti-patterns (OPS-AP-1…9)
- Audit checklist (OPS-CHK-1…20)
- Go / Node.js notes

## Key decisions

| Decision | Options | Choose … when | Trade-off |
| --- | --- | --- | --- |
| Deploy strategy | recreate / rolling / blue-green / canary (progressive, metric-gated) | rolling for stateless services with backward-compatible changes; blue-green when you need instant full switch-back or cannot run mixed versions for long; canary (1% → 10% → 50% → 100% with automated analysis) for high-traffic, high-risk services; recreate only for singletons that cannot run two versions | rolling runs mixed versions; blue-green doubles capacity during switch and doesn't help with DB state; canary needs good SLIs and enough traffic for statistical signal (Argo Rollouts, Flagger) |
| Release vs deploy | ship = release / feature flags decouple deploy from release | flags for risky or long-running features, gradual exposure, kill switches; ship=release for small, low-risk changes | flags add code paths and test combinations; stale flags become debt (expire them) |
| Delivery model | push CD from CI / GitOps pull (Argo CD, Flux) | GitOps for Kubernetes fleets: desired state in Git, drift auto-detected, audit trail; push for simple single-target deploys or non-k8s targets | GitOps adds a controller and repo-per-env conventions; push gives CI cluster credentials |
| Config source | env vars / mounted config files / remote config service / flags service | env vars for the 12-factor basics (≤ ~30 keys); files (ConfigMap) for structured config; remote/flag service for values changed without deploy | env vars are flat strings and visible in process listing; remote config adds a runtime dependency and needs safe defaults when unreachable |
| Migration timing | app runs migrations on start / pre-deploy job (Helm hook, k8s Job, CI step) / separate migration pipeline | pre-deploy job with a single runner and lock; separate pipeline for long backfills; never on every replica start at scale | in-app migrations race across replicas and couple startup time to migration time; separate pipelines need ordering discipline (expand before deploy, contract after) |
| Environments | dev/staging/prod long-lived / ephemeral per-PR preview / prod-only with flags | ephemeral previews when tests need real infra per change; at least one prod-like staging for migrations and integration; flags in prod for final validation | staging drifts and costs money; previews need fast IaC and seeded data |
| Artifact strategy | rebuild per env / build once, promote by digest | build once, promote the same digest through envs — always | needs env-agnostic images and runtime config |
| Base image | full distro / slim / distroless / scratch (Go static) | distroless or scratch for Go static binaries; distroless/`-slim` Node images; full distro only when tools are needed at runtime | no shell makes `kubectl exec` debugging harder (use ephemeral debug containers) |
| Backup & DR posture | backups only / PITR + cross-region copies / warm standby / active-active multi-region | pick by RPO/RTO per data class: PITR (RPO ≈ minutes) + restore tested quarterly for most; warm standby when RTO < 1 h; active-active only when RTO ≈ 0 justifies the consistency and cost burden | each step up roughly multiplies cost and operational complexity; active-active needs conflict handling (→ DATA, SCALE) |
| Dependency updates | ad hoc / scheduled batches / automated bots (Renovate, Dependabot) with auto-merge for patch | bots with grouping and auto-merge on green for patch/minor, weekly cadence; manual review for majors | noisy PRs without grouping; auto-merge needs trustworthy tests |

## Best practices

`OPS-BP-1` — **Keep config out of code and load it into a typed struct validated at startup.** Missing or malformed config otherwise fails at 3 a.m. on the first request that touches it. How: env/files → one typed config object (Go `envconfig`/`koanf` + validation; Node `zod`/`envalid`); required keys without defaults; validate ranges/URLs; exit non-zero with a clear message before the readiness probe ever passes; log the effective config with secrets masked.

`OPS-BP-2` — **See SEC-BP-13 (canonical mechanism).** Wire secret delivery and rotation into the deployment path; inspect manifests and images.

`OPS-BP-3` — **Gate merges on a fast, reliable pipeline.** Broken main blocks everyone and erodes trust in CI. How: required checks: build, unit tests, lint (`golangci-lint`, `eslint`/`tsc --noEmit`), race tests (`go test -race`), dependency/vuln scan (`govulncheck`, `npm audit --omit=dev`/OSV-Scanner, Trivy/Grype on the image), contract/breaking-change checks (`buf breaking`, OpenAPI diff, Pact), migrations dry-run; target < 10–15 min, quarantine flaky tests with an owner and deadline.

`OPS-BP-4` — **Make builds reproducible and hermetic.** "Works on CI" drift and unverifiable artifacts. How: lockfiles committed and enforced (`go.sum`, `npm ci`, `pnpm install --frozen-lockfile`); pinned toolchain (`go` + `toolchain` directive, `.nvmrc`/`engines`, `packageManager`); base images pinned by digest; `-trimpath`, `CGO_ENABLED=0` for Go; multi-stage Dockerfiles; no network fetches at runtime start.

`OPS-BP-5` — **Build once, tag immutably, promote by digest.** Mutable tags make "what is running" unknowable and rollbacks non-deterministic. How: tag with git SHA (+ semver for releases), deploy by `image@sha256:...`; registry tag immutability on; never `:latest` in manifests; SBOM and provenance attestation (SLSA, cosign) attached (→ SEC).

`OPS-BP-6` — **Use progressive delivery with automated, metric-gated rollback.** Humans watching dashboards miss regressions and react late. How: canary steps with analysis on SLIs (error rate, p99 vs baseline) via Argo Rollouts/Flagger/cloud deploy tools; abort automatically on breach; `maxUnavailable: 0`, `maxSurge: 25%` for rolling; `minReadySeconds` ≥ 10–30 s so crash loops are caught before the rollout proceeds; `progressDeadlineSeconds` set.

`OPS-BP-7` — **Make rollback a tested, one-command operation.** A rollback you have never run will fail during the incident. How: previous digest kept and deployable (`kubectl rollout undo`, Argo revision, Helm `rollback`); app code N must work with schema N+1 (so rollback doesn't require reverse migration); rehearse in staging per quarter; feature flag kill switches for risky features.

`OPS-BP-8` — **Keep every change backward and forward compatible across one version step.** During rolling and canary deploys old and new pods, consumers and producers coexist. How: N and N+1 run against the same DB schema, read each other's messages and cache entries; add fields as optional, tolerate unknown fields, never rename/remove in one step; versioned cache keys when formats change; flags to turn on new write paths after full rollout.

`OPS-BP-9` — **Run migrations as a separate, single-runner step in expand → deploy → contract order.** Concurrent or blocking migrations cause lock storms and outages. How: expand migration (additive) before the deploy, as a k8s Job/Helm `pre-upgrade` hook or CI step with an advisory lock; deploy; backfill in batches; contract migration in a later release once no version reads the old shape; set `lock_timeout`/`statement_timeout` for DDL (mechanics → DATA).

`OPS-BP-10` — **See RES-BP-13 (canonical mechanism).** Wire startup/readiness/liveness handlers to the corresponding deployment probes.

`OPS-BP-11` — **See RES-BP-14 (canonical mechanism).** Align signal delivery, endpoint propagation and termination grace with the measured drain.

`OPS-BP-12` — **Set resource requests from measured usage and choose limits deliberately.** Missing requests cause noisy-neighbour evictions; tight CPU limits cause throttling and p99 spikes; no memory limit lets one leak take down a node. How: requests ≈ p90–p95 observed usage; memory limit = request (or modestly above) to avoid OOM surprises; CPU limit either omitted (with requests set, Guaranteed QoS not needed) or ≥ 2× request for latency-sensitive services, watching throttling; align runtime settings (Go `GOMEMLIMIT` ≈ 90% of memory limit, Node `--max-old-space-size` ≈ 75% of limit).

`OPS-BP-13` — **Configure autoscaling with sane bounds and a PodDisruptionBudget.** Unbounded or untuned autoscalers flap or scale to zero capacity during node drains. How: HPA/KEDA on a metric that leads load (RPS per pod, queue lag) rather than only CPU; `minReplicas` ≥ 2 (3 across zones for critical services); `maxReplicas` within DB connection budget; scale-down stabilisation window (≥ 300 s); PDB `maxUnavailable: 1` or `minAvailable` < replicas; topology spread across zones (strategy → SCALE).

`OPS-BP-14` — **Keep environments at parity and define them as code.** Staging that differs in versions, flags or topology catches nothing. How: same images, same Helm chart/Kustomize base with small overlays; same DB engine major version and extensions; Terraform/OpenTofu/Pulumi for all infra with remote state + locking; `plan` in CI on PRs, `apply` from pipeline only; scheduled drift detection (`terraform plan -detailed-exitcode`, Argo CD out-of-sync alerts).

`OPS-BP-15` — **Back up with defined RPO/RTO and prove restores regularly.** Untested backups are a hope, not a control. How: per data store: PITR/WAL archiving (RPO minutes), daily snapshots, copies in another region and account (ransomware/fat-finger protection, immutable/object-lock); automated restore drill at least quarterly into an isolated env with a data-validation query and a measured restore time compared to RTO; backups of object storage, queues' durable state and secrets/KMS keys too.

`OPS-BP-16` — **Have a written, rehearsed disaster-recovery plan.** Region or account loss is when improvisation fails. How: RPO/RTO per service tier signed off by business owners; runbook for failover (DNS, data promotion, config); IaC able to recreate the environment from scratch; game day/failover test at least yearly; dependency map showing which third parties are single-region.

`OPS-BP-17` — **Run sustainable on-call with ownership and runbooks.** Burned-out responders and tribal knowledge lengthen every incident. How: rotation of ≥ 5–6 people per primary schedule, follow-the-sun or compensated; paging only on symptoms (→ OBS); each service has an owner, escalation path, runbooks for deploy, rollback, scale, failover, and common alerts; incident roles (commander, comms) defined.

`OPS-BP-18` — **Upgrade dependencies continuously, in small batches.** Big-bang upgrades every two years are risky and leave CVEs open for months. How: Renovate/Dependabot weekly, grouped by ecosystem, auto-merge patch on green; runtime upgrades within each release's support window (Go supports the two latest minors; Node only even-numbered LTS lines, Active/Maintenance); SLA for critical CVEs (e.g. 7 days).

`OPS-BP-19` — **Measure delivery with DORA metrics and act on them.** Without numbers, "we're slow" or "deploys are risky" can't be prioritised. How: deployment frequency, lead time for changes (commit → prod), change failure rate, failed-deployment recovery time, plus rework rate; derive from CI/CD and incident data; elite-ish targets: on-demand deploys, lead time < 1 day, CFR < ~5–15%, recovery < 1 h.

`OPS-BP-20` — **Make cost visible per service and environment.** Unattributed spend grows unnoticed until a budget crisis. How: mandatory labels/tags (`team`, `service`, `env`) enforced by policy (OPA/Kyverno, Terraform validation); Kubecost/OpenCost or cloud cost allocation; budget alerts; review idle resources (oversized requests, orphaned volumes, non-prod running 24/7) monthly.

## Bad practices

`OPS-BAD-1` — **`:latest` or mutable tags in deploy manifests.** Different nodes run different code; rollback re-pulls the same broken image. → Instead: SHA tags, deploy by digest (OPS-BP-5).

`OPS-BAD-2` — **Config read lazily with silent defaults (`os.Getenv` in random places, `process.env.X || 'localhost'`).** Prod points at localhost or a zero timeout only discovered under traffic. → Instead: typed config validated at startup (OPS-BP-1).

`OPS-BAD-3` — **Secrets in Dockerfiles, `ENV`/`ARG`, `.env` committed, or plain values in Helm values/ConfigMaps.** Anyone with image or repo access has prod credentials. → Instead: runtime secret delivery (OPS-BP-2, → SEC).

`OPS-BAD-4` — **Rebuilding images per environment.** The artifact tested is not the artifact shipped. → Instead: build once, promote (OPS-BP-5).

`OPS-BAD-5` — **Running migrations on every app replica's startup.** Replicas race on DDL, startup blocks on long migrations, failed migrations crash-loop the whole fleet. → Instead: single-runner pre-deploy step (OPS-BP-9).

`OPS-BAD-6` — **See DATA-BP-14 (canonical mechanism).** Check migrations against both old and new deployed code, including rollback.

`OPS-BAD-7` — **No SIGTERM handling, or shell-form `CMD` so PID 1 is `/bin/sh`.** Signal never reaches the app; pod is SIGKILLed after the grace period, dropping requests and in-flight jobs. → Instead: exec-form `CMD`, init process, drain logic (OPS-BP-11).

`OPS-BAD-8` — **See RES-BP-13 (canonical mechanism).** A shared dependency failure must not restart the entire fleet through liveness.

`OPS-BAD-9` — **No resource requests, or CPU limits equal to a small request on latency-sensitive services.** Evictions and noisy neighbours, or CFS throttling that shows as random p99 spikes. → Instead: measured requests, deliberate limits, runtime tuning (OPS-BP-12).

`OPS-BAD-10` — **Redundancy inconsistent with the agreed availability requirement.** Evaluate singleton behavior, voluntary disruption and recovery using RES-BP-15. One replica is not automatically a High finding for every user-facing service.

`OPS-BAD-11` — **Manual changes in cloud consoles or `kubectl edit` in prod.** Drift: the next IaC apply reverts the fix or fails; no audit trail. → Instead: IaC/GitOps only, break-glass with follow-up PR (OPS-BP-14).

`OPS-BAD-12` — **Backups in the same account/region as the primary, never restored.** Ransomware, account compromise or region loss takes backups too; corrupt backups discovered during the disaster. → Instead: isolated, immutable copies and restore drills (OPS-BP-15).

`OPS-BAD-13` — **CI that skips or ignores failing tests and vulnerability scans (`|| true`, `continue-on-error: true`, `allow_failure`).** Gates become decorative. → Instead: required checks, quarantine with owner (OPS-BP-3).

`OPS-BAD-14` — **Unpinned toolchains and base images (`FROM node`, `FROM golang:latest`, `npm install` in CI).** Builds change without code changes; supply-chain exposure. → Instead: pinned versions/digests, lockfile-enforcing installs (OPS-BP-4).

`OPS-BAD-15` — **Feature flags never removed.** Dead branches, combinatorial test surface, accidental reactivation of old code. → Instead: flags with owner and expiry date, removal ticket created with the flag; report stale flags in CI (OPS-BP-6, OPS-BP-7).

`OPS-BAD-16` — **Deploying on Friday evening without on-call coverage or automated rollback.** Regressions sit unnoticed for days. → Instead: progressive delivery with auto-abort and staffed windows (OPS-BP-6, OPS-BP-17).

## Anti-patterns

`OPS-AP-1` — **Snowflake environments.** Symptoms: servers/clusters configured by hand; "don't touch staging, it's fragile"; nobody can recreate prod from code; IaC plan shows large unexplained diffs. Why it hurts: untestable changes, slow DR, drift-induced incidents. Way out: import existing resources into IaC (`terraform import`/import blocks), make plan clean, block console writes via IAM, schedule drift detection.

`OPS-AP-2` — **Release train / big-batch deploys.** Symptoms: deploys weekly or monthly bundling dozens of changes; release managers; code freeze before release; hard to identify which change broke prod. Why it hurts: higher change failure rate and longer recovery; lead time measured in weeks. Way out: trunk-based development with short-lived branches, flags for incomplete work, automated pipeline per service, deploy small changes many times a day.

`OPS-AP-3` — **Staging as the safety net.** Symptoms: long manual QA in staging; prod differs (data size, traffic, flags); "passed staging" incidents are common. Why it hurts: false confidence, slow delivery, production risk unchanged. Way out: parity where it matters (OPS-BP-14), contract tests, canaries and flags as the real production safety net.

`OPS-AP-4` — **ClickOps deployments.** Symptoms: deploy steps in a wiki; someone runs `helm upgrade` from a laptop; credentials for prod on developer machines. Why it hurts: unrepeatable, unaudited, depends on individuals and their local tool versions. Way out: pipeline or GitOps as the only path to prod, short-lived OIDC credentials for CI (no long-lived keys), audit log.

`OPS-AP-5` — **Schrödinger's backup.** Symptoms: backup jobs report success but nobody has restored one; restore procedure undocumented; RPO/RTO not defined. Why it hurts: the first real restore attempt happens during a disaster and fails or takes days. Way out: define RPO/RTO, automate restore drills with validation and timing, alert on drill failure.

`OPS-AP-6` — **Config sprawl.** Symptoms: the same setting in env vars, Helm values, ConfigMaps, code defaults and a remote config service with unclear precedence; per-env forks of manifests. Why it hurts: nobody knows the effective value; prod-only config bugs. Way out: one documented precedence order (defaults in code < file < env < flags), single typed config loader, Kustomize/Helm overlays that differ only in values, effective-config logging at startup.

`OPS-AP-7` — **Hero on-call.** Symptoms: one or two people answer every page; knowledge not in runbooks; incidents wait for a specific person. Why it hurts: bus factor 1, burnout, slow recovery when the hero is away. Way out: rotation with shadowing, runbooks written after every incident, ownership per service, measured page load per person.

`OPS-AP-8` — **Dependency freeze.** Symptoms: runtimes several majors behind (Go older than the two supported releases, Node on an EOL line), lockfiles untouched for a year, upgrade tickets perpetually postponed. Why it hurts: unpatched CVEs, blocked library upgrades, eventual forced migration under pressure. Way out: Renovate with grouping and auto-merge, a standing upgrade budget per sprint, runtime upgrades tracked as roadmap items.

`OPS-AP-9` — **Branch-per-environment promotion.** Symptoms: `develop` → `staging` → `main` branches merged or cherry-picked to promote; each env builds from its own branch; hotfixes applied to one branch and forgotten on others. Why it hurts: what was tested is not what ships, merge conflicts block releases, envs silently diverge. Way out: trunk-based development, build once and promote the same digest (OPS-BP-5), per-env differences only in config overlays.

## Audit checklist

| ID | Check | Evidence / search hints | Default severity |
| --- | --- | --- | --- |
| OPS-CHK-1 | Is config loaded into a typed structure and validated at startup? | Go: grep `os.Getenv`/`os.LookupEnv` outside a config package, vs `envconfig`, `koanf`, `viper` + validation; Node: `process.env.` scattered in modules, `|| '<default>'` fallbacks, vs `zod`/`envalid`/`@nestjs/config` schema. Fail: env read lazily across code or prod-sensitive defaults (localhost, 0 timeouts). Verifies OPS-BP-1, OPS-BAD-2, OPS-AP-6. | Medium |
| OPS-CHK-2 | Are secrets absent from images, repos and plain manifests? | Dockerfile `ENV`/`ARG` with `KEY`/`TOKEN`/`PASSWORD`; committed `.env*`; Helm values and ConfigMaps containing credentials; run gitleaks/trufflehog if allowed. Confirm runtime delivery (ExternalSecret, CSI, workload identity). Fail: any live credential in repo/image/ConfigMap. Verifies OPS-BP-2, OPS-BAD-3. | Critical (live prod secret) / High otherwise |
| OPS-CHK-3 | Does CI gate merges on tests, lint, vulnerability scan and contract checks? | `.github/workflows/*.yml`, `.gitlab-ci.yml`, `Jenkinsfile`: look for `go test -race`, `golangci-lint`, `govulncheck`, `npm ci`, `eslint`, `tsc`, `npm audit`/`osv-scanner`, `trivy`, `buf breaking`, `pact`; branch protection required checks. Fail: no tests or scan, or `continue-on-error: true`/`|| true` on them. Verifies OPS-BP-3, OPS-BAD-13. | Medium |
| OPS-CHK-4 | Are builds reproducible (lockfiles, pinned toolchain and base images)? | `go.sum` committed, `toolchain` in `go.mod`; `package-lock.json`/`pnpm-lock.yaml` + `npm ci`/`--frozen-lockfile`; `.nvmrc`/`engines`; Dockerfile `FROM` with version and ideally `@sha256:`. Fail: `npm install` in CI, `FROM node`/`:latest`, missing lockfile. Verifies OPS-BP-4, OPS-BAD-14. | Medium |
| OPS-CHK-5 | Are images tagged immutably and deployed by SHA/digest, built once? | k8s manifests/Helm values `image:` fields, CI build steps per env, registry immutability setting. Fail: `:latest`, branch tags, or per-env rebuilds. Also check whether workflows trigger on env branches (`on: push: branches: [staging]`). Verifies OPS-BP-5, OPS-BAD-1, OPS-BAD-4, OPS-AP-9. | High |
| OPS-CHK-6 | Is the rollout strategy safe (surge/unavailable, minReadySeconds, progress deadline) and progressive for critical services? | Deployment `strategy.rollingUpdate`, `minReadySeconds`, `progressDeadlineSeconds`; Argo Rollouts/Flagger `analysis` templates. Fail: `maxUnavailable` > 0 with few replicas, no readiness gating, or high-traffic critical service with no canary/auto-abort. Verifies OPS-BP-6, OPS-BAD-16. | Medium |
| OPS-CHK-7 | Is rollback documented, quick and independent of reverse migrations? | Runbooks, `helm rollback`/Argo history limits (`revisionHistoryLimit` > 0), feature flag kill switches. Fail: rollback requires rebuild or schema rollback. Verifies OPS-BP-7. | High |
| OPS-CHK-8 | Are changes compatible across N/N+1 (DB, messages, caches) during rollout? | Recent migrations: `DROP COLUMN`, `RENAME`, `NOT NULL` without default shipped with code that stops using it; message schemas removing/renaming fields; cache value formats changed without key versioning. Fail: breaking change shipped in a single release. Verifies OPS-BP-8, OPS-BAD-6. | High |
| OPS-CHK-9 | Do migrations run once per deploy, before the app, with lock and timeouts? | Go: `migrate.Up()`/`goose.Up` in `main`; Node: `prisma migrate deploy`, `knex.migrate.latest()`, TypeORM `migrationsRun: true` in app bootstrap or container `CMD`; vs k8s Job/Helm `pre-upgrade` hook/CI step. Fail: migrations on every replica start or without lock (→ DATA for DDL safety). Verifies OPS-BP-9, OPS-BAD-5. | High |
| OPS-CHK-10 | Are startup/readiness/liveness probes correct? | Deployment `startupProbe`, `readinessProbe`, `livenessProbe` paths and handlers; read the liveness handler. Fail: no readiness probe, liveness checking DB/downstreams, or liveness identical to readiness with low thresholds. Verifies OPS-BP-10, OPS-BAD-8. | High |
| OPS-CHK-11 | Does the process drain gracefully within the grace period? | Go: `signal.NotifyContext(..., syscall.SIGTERM)`, `srv.Shutdown(ctx)`, consumer close; Node: `process.on('SIGTERM'`, `server.close()`, `closeAllConnections`/`@godaddy/terminus`/`fastify.close`. Dockerfile `CMD` exec form, `tini`/`dumb-init`, not `npm start`. Manifest `terminationGracePeriodSeconds` vs drain time, `preStop`. Fail: no handler, shell-form CMD, `npm start` as PID 1, or grace period < drain. Verifies OPS-BP-11, OPS-BAD-7. | High |
| OPS-CHK-12 | Are resource requests/limits set and aligned with runtime memory settings? | `resources:` in manifests/Helm values; Go `GOMEMLIMIT`, Go version ≥ 1.25 or `automaxprocs`; Node `--max-old-space-size`/`NODE_OPTIONS`. Check throttling/OOMKill history if metrics available. Fail: missing requests, memory limit without runtime alignment, OOMKills or throttling > ~10% on latency paths. Verifies OPS-BP-12, OPS-BAD-9. | Medium |
| OPS-CHK-13 | Does deployment redundancy meet the service requirement? | Check replicas, autoscaling bounds, failure-domain placement and disruption behavior against RES-BP-15; include maxReplicas × pool size (DATA-BP-10). Do not flag replica count or missing PDB without establishing applicability and impact. | By concrete impact |
| OPS-CHK-14 | Is infrastructure fully in code, applied by pipeline, with drift detection? | `terraform/`, `*.tf`, `pulumi/`, `crossplane`; remote backend + locking; CI `plan` on PR and `apply` only from pipeline; drift job or Argo CD sync status. Fail: resources without IaC, local applies, no state locking. Verifies OPS-BP-14, OPS-BAD-11, OPS-AP-1, OPS-AP-4. | Medium |
| OPS-CHK-15 | Do environments share images, charts and engine versions? | Compare Helm values/Kustomize overlays across envs, DB engine versions in Terraform, feature flags defaults. Fail: env-specific code paths (`if env == "staging"`), divergent chart forks, different DB majors. Verifies OPS-BP-14, OPS-AP-3. | Low |
| OPS-CHK-16 | Are backups isolated, immutable and restore-tested against RPO/RTO? | Terraform/cloud config: PITR/`backup_retention_period`, cross-region/account copies, object lock; restore drill job or runbook with last-run date. Fail: no restore test in the last 6 months, or backups only in the primary account/region. Verifies OPS-BP-15, OPS-BAD-12, OPS-AP-5. | High (Critical for systems of record with no backups) |
| OPS-CHK-17 | Is there a DR plan with agreed RPO/RTO and a recent exercise? | `docs/dr*`, runbooks, game-day records; IaC able to target another region. Fail: no defined RPO/RTO for critical data, or no exercise in last 12 months. Verifies OPS-BP-16. | Medium |
| OPS-CHK-18 | Is on-call owned, staffed and backed by runbooks? | PagerDuty/Opsgenie schedules (Terraform), `CODEOWNERS`, service catalogue, `runbooks/`. Fail: required response coverage has no owner or cannot meet the incident target; team count alone is not a violation. Check deploy/rollback runbooks. Verifies OPS-BP-17, OPS-AP-7. | Medium |
| OPS-CHK-19 | Are dependencies and runtimes kept current with automated updates? | `renovate.json`, `.github/dependabot.yml`; `go` directive in `go.mod` vs supported releases; Node version in Dockerfile/`.nvmrc` vs LTS schedule; age of lockfile changes. Fail: EOL runtime or no automated updates with known critical CVEs open (`govulncheck`/`npm audit`). Verifies OPS-BP-18, OPS-AP-8. | Medium (High with exploitable CVEs) |
| OPS-CHK-20 | Are delivery performance and cost measured per service? | DORA dashboards, deploy frequency from CI history (`gh run list`), release cadence; cost labels on resources (`team`, `service`), Kubecost/OpenCost, budget alerts. Fail: monthly or slower deploys with code freezes, or no cost attribution. Verifies OPS-BP-19, OPS-BP-20, OPS-AP-2. | Low |

## Go / Node.js notes

- **Images:** Go builds a static binary (`CGO_ENABLED=0 go build -trimpath -ldflags="-s -w"`) that runs on `scratch`/`distroless/static` (~10–20 MB); remember CA certificates and `tzdata` (or `import _ "time/tzdata"`). Node needs the runtime: multi-stage with `npm ci --omit=dev` in the final stage, `node:<lts>-slim` or distroless `nodejs`, `NODE_ENV=production`; images are 100–200+ MB and `node_modules` is the main supply-chain surface.
- **PID 1 and signals:** Go handles SIGTERM itself if the binary is PID 1 (exec-form `ENTRYPOINT`). For Node, `npm start`/`yarn start` as `CMD` does not forward SIGTERM reliably — run `node dist/server.js` directly, with `--init`/`tini` to reap zombies; `node --watch`/nodemon never in prod.
- **Graceful shutdown specifics:** Go `http.Server.Shutdown(ctx)` stops listeners and waits for active requests but not hijacked/WebSocket connections — track those separately; `RegisterOnShutdown` helps. Node `server.close()` waits for keep-alive connections to idle out; use `server.closeIdleConnections()` (Node 18.2+) and a hard timeout, and stop BullMQ/Kafka consumers before closing DB pools.
- **Memory limits:** Go ≥ 1.19 honours `GOMEMLIMIT` (set ~90% of the container limit, `GOGC` stays default unless profiled); Go ≥ 1.25 sets `GOMAXPROCS` from the cgroup CPU limit, older versions need `go.uber.org/automaxprocs`. Node's V8 heap is sized from container memory in recent versions but often not optimally — set `--max-old-space-size` explicitly (~75% of limit, leaving room for buffers and native memory).
- **Config libraries:** Go: `caarlos0/env`, `kelseyhightower/envconfig`, `knadh/koanf`; avoid global `viper` singletons read deep in code. Node: `zod`/`envalid` schema parsed once at boot and exported as a frozen object; `dotenv` only in development (Node 20.6+ has `--env-file`).
- **Cold starts and readiness:** Go services typically start in tens of milliseconds, so startup probes are mostly about dependency warm-up; Node/TS services with large dependency trees can take seconds (module loading, JIT) — bundle with esbuild/tsup and use `startupProbe` rather than long `initialDelaySeconds`.
- **Vulnerability scanning:** `govulncheck` reports only vulnerabilities in code paths actually called (low noise); `npm audit` reports every transitive advisory including dev and unreachable ones — scope with `--omit=dev`, triage with OSV-Scanner or reachability-aware tools, and set an explicit policy rather than `|| true`.
- **Probes under load:** a Node process doing CPU-heavy work can't answer `/livez` until the event loop frees up, so tight liveness settings (`timeoutSeconds: 1`, `failureThreshold: 1`) cause restart storms exactly at peak — use `timeoutSeconds` 2–5 and `failureThreshold` 3–6. Go serves probes on separate goroutines, but a saturated `GOMAXPROCS` under CPU throttling shows the same symptom.
- **CI speed:** cache Go module and build caches (`actions/setup-go` with cache, `GOCACHE`, `GOMODCACHE`) and npm/pnpm stores (`actions/setup-node` `cache:`); use BuildKit cache mounts (`RUN --mount=type=cache`) in Dockerfiles; in monorepos build and deploy only affected services (Nx `affected`, `turbo --filter=...[origin/main]`, Go package diff or Bazel) to keep services independently deployable.
- **Build provenance in the binary:** Go embeds VCS info automatically (`debug.ReadBuildInfo()` → `vcs.revision`, `vcs.modified`) when built inside the repo, plus `-ldflags "-X main.version=$SHA"` for release names; Node has no equivalent — pass the SHA as a build arg into an env var or generated `version.json` so logs, error tracker `release` and `build_info` match the deployed digest.
