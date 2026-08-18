# Observability stack

An optional Docker Compose stack — an OpenTelemetry Collector, Prometheus,
Loki, Tempo, and Grafana — for viewing what the backend exports (see the root
README's "Telemetry" section for what it sends and why). Not part of the
app's own compose files: most of the time you don't need this running, so it
lives in its own directory and its own Compose project.

```
backend (OTLP) -> otel-collector -> Tempo      (traces)
                                  -> Prometheus (metrics, via remote_write)
                                  -> Loki       (logs, once the app emits any)
                                                    \
                                                     -> Grafana (all three, pre-wired)
```

## Run it

### Local dev

The collector needs to be reachable from the app container, so it joins the
app stack's own Docker network as an *external* network — which means the app
stack has to be up first:

```sh
docker compose up -d --build                        # from the repo root — the app stack
docker compose -f observability/docker-compose.yaml up -d
```

If you want this stack running without the app (just to poke around
Grafana), create the network by hand first: `docker network create sdip`.

By default this joins `sdip`, the network `docker-compose.yaml` (local dev)
creates. To point it at `docker-compose.prod.yaml`'s network instead:

```sh
SDIP_NETWORK=sdip-prod docker compose -f observability/docker-compose.yaml up -d
```

Then turn telemetry on in the app stack by setting, in its `.env`:

```
OTEL_EXPORTER_OTLP_ENDPOINT=http://otel-collector:4318
```

and restart the app container. `SDIP_ENVIRONMENT` and `SDIP_GIT_COMMIT` (see
the root README) are worth setting too — they're what tells traces and
metrics from different deployments apart in Grafana.

### Dev and production, sharing one stack

`sdip` and `sdip-prod` each run on their own EC2 instance with Postgres and
the app already on it — running a full second copy of this stack on either
is real, avoidable memory pressure on an already-small box. Since every
trace and metric already carries `deployment.environment`
(`SDIP_ENVIRONMENT`, wired in `backend/app/telemetry.py`) as a resource
attribute, one shared stack works instead: it's the label the provisioned
dashboard filters and splits on, so dev and production stay visually
distinct even sharing storage.

That shared stack runs on its own dedicated EC2 instance, deployed from
**`deploy/aws/observability-stack.yaml`** — a separate CloudFormation stack
(`sdip-observability`), decoupled from either app instance's lifecycle:

```sh
aws cloudformation deploy \
  --stack-name sdip-observability \
  --template-file deploy/aws/observability-stack.yaml \
  --capabilities CAPABILITY_IAM \
  --tags Project=sdip Environment=shared
```

It defaults to this account's default VPC (app stacks each get their own,
which is why they're at the account's 5-VPC limit — a third dedicated VPC
just for this instance isn't worth it) and to the two app stacks' current
Elastic IPs as the only CIDRs allowed to send it OTLP. Update
`AppInstanceCidr1`/`AppInstanceCidr2` if either app stack is ever replaced
(Elastic IPs otherwise survive that, so this is rare).

Point each app instance at the stack's `ElasticIp` output, in its `.env`:

```
OTEL_EXPORTER_OTLP_ENDPOINT=http://<sdip-observability ElasticIp>:4318
SDIP_ENVIRONMENT=dev          # or "production" on sdip-prod - don't skip this,
                               # docker-compose.prod.yaml's own default is
                               # "production" for BOTH if left unset
```

then `docker compose -f docker-compose.prod.yaml up -d` to restart the app
container and pick it up. OTLP has no auth of its own — the security group
rule restricting ingestion to exactly those two IPs is the only thing
stopping anyone else on the internet from writing into your stack, so don't
widen it.

There is deliberately no GitHub Actions deploy wired up for this stack yet
(unlike the app stacks) — update config by hand over Session Manager:

```sh
aws ssm start-session --target <sdip-observability InstanceId>
cd /opt/sdip && git pull && docker compose -f observability/docker-compose.yaml up -d
```

Grafana, Prometheus, Tempo, and Loki all stay bound to the instance's
loopback interface only (see below) — nothing opens a port for them, so the
only way in is an SSM port-forward:

```sh
aws ssm start-session --target <sdip-observability InstanceId> \
  --document-name AWS-StartPortForwardingSession \
  --parameters '{"portNumber":["3030"],"localPortNumber":["3030"]}'
```

then open http://localhost:3030 same as local dev.

## What's exposed

| Service | URL | Notes |
| --- | --- | --- |
| Grafana | http://localhost:3030 | `admin` / `admin` by default — override with `GRAFANA_ADMIN_USER` / `GRAFANA_ADMIN_PASSWORD`. Prometheus, Loki, and Tempo are pre-provisioned as datasources, cross-linked (trace → logs, trace → metrics) so you can jump between them from a trace view. Ships with one pre-provisioned dashboard, "SDIP Application Metrics" (rooms created, active participants, canvas elements created — see the backend README's "Telemetry" section for what feeds it), auto-refreshing every 5s. |
| Prometheus | http://localhost:9090 | |
| Tempo | http://localhost:3200 | Query API only; browse traces through Grafana. |
| Loki | http://localhost:3100 | Query API only; browse logs through Grafana. |
| OTel Collector | localhost:4317 (gRPC) / localhost:4318 (HTTP) | What `OTEL_EXPORTER_OTLP_ENDPOINT` points at. Published to the host too, so a backend run outside Docker (`make run`) can reach it at `http://localhost:4318`. |

## Alerting

Grafana's unified alerting is file-provisioned from `grafana/provisioning/alerting/`:

- **`CanvasComponentsDedupedSpike`** — fires when `sdip.canvas.components.deduped`
  (see the backend README's "Telemetry" section) is above zero for 5
  consecutive minutes. That counter should normally sit at zero; a sustained
  rise means `DatabaseStore._dedupe_duplicate_components` is dropping
  legitimate canvas components, not just retried duplicates — silent data
  loss that the `sdip.canvas.elements.created` counter alone can't reveal,
  since a dropped create looks identical to nobody having tried at all.

Alerts route through the `sdip-alerts` contact point, a webhook whose URL
comes from `SDIP_ALERT_WEBHOOK_URL` (set it in `.env`, alongside
`GRAFANA_ADMIN_USER`/`GRAFANA_ADMIN_PASSWORD`). Left unset, it defaults to a
placeholder that nothing listens on — rules still evaluate and show as
firing in Grafana's Alerting UI (and via `/api/prometheus/grafana/api/v1/rules`),
they just have nowhere to deliver to until you point it at a real Slack,
Teams, or PagerDuty webhook.

## Notes

- Everything here uses local, single-node storage (`docker volume`s) — there's
  no retention or durability story beyond what fits on disk. This is for
  looking at telemetry during development, not for running as a production
  observability backend.
- The collector only forwards what it receives: with no logging
  instrumentation in the backend yet, the Loki pipeline is wired up but idle.
- `docker compose -f observability/docker-compose.yaml down -v` tears
  everything down, including the stored data.
