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

`sdip` and `sdip-prod` each run on their own EC2 instance
(`t4g.small`, 2GB RAM) with Postgres and the app already on it — running a
full second copy of this stack on each is real, avoidable memory pressure on
an already-small box. Since every trace and metric already carries
`deployment.environment` (`SDIP_ENVIRONMENT`, wired in `backend/app/telemetry.py`)
as a resource attribute, one shared stack works instead: it's the label the
provisioned dashboard filters and splits on (see below), so dev and
production stay visually distinct even sharing storage.

Run the stack on **one** instance only (recommend `sdip`/dev — it's the one
CI already deploys to automatically, and the lower-stakes box to experiment
on). That instance's own app reaches it over the Docker network as usual
(`http://otel-collector:4318`). The *other* instance's app has no Docker
network in common with it — they're separate hosts — so it has to reach the
collector over the network by IP instead:

```
# On the instance NOT hosting the stack, in its .env:
OTEL_EXPORTER_OTLP_ENDPOINT=http://<elastic-ip-of-the-hosting-instance>:4318
```

That only works once the hosting instance's security group allows inbound
4318 (and 4317, if using gRPC) from the other instance's Elastic IP
specifically — OTLP has no auth of its own, so this is the only thing
stopping anyone else on the internet from writing traces and metrics into
your stack. Don't open it to `0.0.0.0/0`.

Everything else (Grafana, Prometheus, Tempo, Loki query APIs) stays bound to
the host's loopback interface only (see below) — reach those over an SSM
port-forward or SSH tunnel, never by opening more inbound ports:

```sh
aws ssm start-session --target <instance-id> \
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
