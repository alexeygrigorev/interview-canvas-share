# System Design Interview Platform

A browser-based collaborative workspace for conducting live system-design
interviews. An interviewer creates a session and shares a link; candidates and
other interviewers join and work together on the same infinite canvas in real
time — placing architecture components, connecting them with arrows, adding
labels and notes, and drawing freehand. Edits are broadcast over WebSockets so
every participant sees updates immediately, and the final canvas is preserved
for later review.

- **Backend** — FastAPI (Python 3.12), SQLAlchemy over SQLite or PostgreSQL,
  JWT auth, WebSocket realtime updates. Lives in `backend/`.
- **Frontend** — TanStack Start / React + Vite. Lives in `frontend/`.
- **Spec** — `docs/spec.md`. **API contract** — `openapi.yaml`.
- **End-to-end tests** — Playwright against the compose stack. Lives in `e2e/`.

## Run with Docker

The `Dockerfile` is a two-stage build: the frontend is compiled with Node and
the resulting static bundle is copied into the Python image, so a single
container serves both the API and the UI.

### Build

From the repository root:

```sh
docker build -t sdip:latest .
```

### Run

```sh
docker run --rm -p 8000:8000 \
  -v sdip-data:/data \
  -e SDIP_DATABASE_URL=sqlite:////data/sdip.db \
  --name sdip sdip:latest
```

The app listens on port `8000` inside the container. Open
<http://localhost:8000> for the UI and <http://localhost:8000/docs> for the
interactive API documentation. If port 8000 is already taken on your machine,
map a different host port, for example `-p 8100:8000`.

The `-v sdip-data:/data` flag keeps your data. It stores the SQLite database in
a named Docker volume outside the container, so sessions and canvases survive
restarts and you pick up where you left off every time you run the container.
Without it the database lives inside the container and is thrown away the
moment the container is removed, so every run starts from the seed data again.

Note the four slashes in `sqlite:////data/sdip.db` — that is an absolute path
to `/data/sdip.db`, the mounted volume. Three slashes would make it relative
and write inside the container instead.

The volume persists until you delete it explicitly. To inspect it or start over
from a clean database:

```sh
docker volume ls                # list volumes
docker volume rm sdip-data      # wipe the data and reseed on next run
```

To run it in the background and follow the logs:

```sh
docker run -d -p 8000:8000 \
  -v sdip-data:/data \
  -e SDIP_DATABASE_URL=sqlite:////data/sdip.db \
  --name sdip sdip:latest
docker logs -f sdip
docker rm -f sdip   # stop and remove (the volume survives)
```

The seeded demo users (`avery@northwind.dev`, `jordan@northwind.dev`,
`priya@northwind.dev`) all use the password `demo-password`; log in through the
UI or with `POST /v1/auth/login`.

### Run with Docker Compose

`docker-compose.yaml` wires the app to a PostgreSQL container so both start with
one command — the app waits for the database healthcheck before booting, then
creates its tables and seeds the demo data:

```sh
docker compose up --build
```

Open <http://localhost:8100>. Stop with `docker compose down`; add `-v` to wipe
the database and reseed on the next start.

The database is not published to the host — the app reaches it over the compose
network. Uncomment the `ports` block under `postgres` to connect with `psql`
from your machine.

Every value has a working default, so no `.env` file is required. Override any
of them in the environment or an `.env` file next to the compose file:

| Variable | Default |
| --- | --- |
| `APP_PORT` | `8100` — host port the UI and API are published on |
| `POSTGRES_USER` / `POSTGRES_PASSWORD` / `POSTGRES_DB` | `sdip` |
| `SDIP_JWT_SECRET` | the local development secret — **set this outside local development** |

```sh
APP_PORT=9000 SDIP_JWT_SECRET=some-long-random-string docker compose up --build
```

### Run against PostgreSQL

SQLite is the zero-setup default; PostgreSQL is supported for anything with more
than one writer or a need to keep data outside the app. Start a database:

```sh
docker run -d \
  --name interview-canvas-db \
  -e POSTGRES_USER=sdip \
  -e POSTGRES_PASSWORD=sdip \
  -e POSTGRES_DB=sdip \
  -p 5432:5432 \
  -v interview-canvas-pgdata:/var/lib/postgresql/data \
  postgres:16-alpine
```

The app creates its tables and seeds the demo data on first start, so there is
no migration step. Put both containers on the same Docker network so the app can
reach the database by container name:

```sh
docker network create sdip-net
docker network connect sdip-net interview-canvas-db

docker run --rm -p 8000:8000 \
  --network sdip-net \
  -e SDIP_DATABASE_URL=postgresql://sdip:sdip@interview-canvas-db:5432/sdip \
  --name sdip sdip:latest
```

No `-v` is needed here — the data now lives in the database container's
`interview-canvas-pgdata` volume. Running outside Docker, point at the published
port instead:

```sh
SDIP_DATABASE_URL=postgresql://sdip:sdip@localhost:5432/sdip make run
```

`postgres://` and `postgresql://` URLs are both accepted and routed to the
installed psycopg 3 driver, so a URL copied from a hosted provider works as is.
To wipe the database and start over from the seed data:

```sh
docker rm -f interview-canvas-db
docker volume rm interview-canvas-pgdata
```

### Configuration

All settings are environment variables passed with `-e`:

| Variable | Default | Purpose |
| --- | --- | --- |
| `SDIP_DATABASE_URL` | `sqlite:///./sdip.db` | Any SQLAlchemy database URL — SQLite or PostgreSQL |
| `SDIP_JWT_SECRET` | `local-development-secret-change-me` | JWT signing secret — **set this outside local development** |
| `SDIP_ACCESS_TOKEN_MINUTES` | `60` | Access token lifetime |
| `SDIP_CORS_ORIGINS` | localhost dev origins | Comma-separated allowed origins |
| `SDIP_STATIC_DIR` | `app/static` | Directory the frontend bundle is served from |
| `SDIP_DB_POOL_SIZE` | `5` | PostgreSQL connection pool size (ignored on SQLite) |
| `SDIP_DB_MAX_OVERFLOW` | `10` | Extra PostgreSQL connections allowed under burst |
| `SDIP_DB_POOL_RECYCLE` | `1800` | Seconds before a pooled connection is reopened |

Set `SDIP_JWT_SECRET` to a real secret before running this anywhere but your
own machine:

```sh
docker run --rm -p 8000:8000 \
  -v sdip-data:/data \
  -e SDIP_DATABASE_URL=sqlite:////data/sdip.db \
  -e SDIP_JWT_SECRET=some-long-random-string \
  --name sdip sdip:latest
```

If you would rather keep the database as a plain file in the project directory
instead of a named volume, bind-mount a host directory:

```sh
docker run --rm -p 8000:8000 \
  -v "$(pwd)/data:/data" \
  -e SDIP_DATABASE_URL=sqlite:////data/sdip.db \
  --name sdip sdip:latest
```

## Deploy to AWS

`deploy/aws/sdip-stack.yaml` is a CloudFormation template that stands up the
whole thing on one EC2 instance: a VPC with a single public subnet, an Elastic
IP, a security group open only on 80 and 443, and an instance that clones this
repository on boot and starts `docker-compose.prod.yaml`. That compose file adds
[Caddy](https://caddyserver.com/) in front of the app, which obtains and renews
a Let's Encrypt certificate automatically and proxies HTTPS and WebSocket
traffic to the app container. Neither the app nor PostgreSQL is published to the
host, so Caddy's ports are the only way in.

One instance and one app container is a deliberate ceiling, not an oversight.
`ConnectionManager` in `backend/app/routers/realtime.py` holds WebSocket
connections in process memory, so a second replica would put participants of the
same interview into separate rooms — their edits would reach the database but
never each other. See *Scaling past one instance* below.

### Environments: dev and production

Two independent copies of everything below are deployed — same template, two
`--stack-name`s, each with its own VPC, EC2 instance, PostgreSQL volume, and
CloudFront distribution:

| Environment | Stack name | Domain | GitHub environment | Deploys |
| --- | --- | --- | --- | --- |
| dev | `sdip` | https://dev.interviews.aisl.click | `dev` | automatic — every push to `main` (see "Continuous deployment") |
| production | `sdip-prod` | https://interviews.aisl.click | `production` | manual only — a human runs "Promote dev to production" from the Actions tab (see "Promote to production" below). There is no automatic path to production. |

They share nothing but the `aisl.click` Route53 hosted zone (each owns its own
record) and the account's GitHub OIDC provider (only one stack sets
`CreateGitHubOidcProvider=true`; the other passes `false` and reuses it).
Compute, database, and CloudFront are fully separate per stack, so redeploying,
resizing, or deleting one cannot touch the other.

There is intentionally no parent/nested stack joining the two: the reason for a
second copy is that each can be changed or torn down independently, and a
nested stack would only add coupling neither needs. What keeps it legible
instead:

- **Naming is the source of truth** — `sdip` is always dev, `sdip-prod` is
  always production. Never repurpose one of these names for the other.
- **Stack tags** — every resource in each stack carries `Environment` (`dev` /
  `production`) and `Project=sdip`, set with `--tags` on
  `aws cloudformation deploy`. Visible in the CloudFormation and Cost Explorer
  consoles without opening either template.
- **Separate GitHub deploy roles per stack** — each stack's `GitHubEnvironment`
  parameter matches its own name (`dev` / `production`), so each has its own
  `GitHubDeployRole` trusting only its own environment's OIDC subject. The two
  are not interchangeable: a token minted for the `dev` environment cannot
  assume the production role, and vice versa.
- **This table** — update it whenever a stack's domain, deploy status, or name
  changes.

`GitHubDeployRole` variables live at the GitHub *environment* level, not the
repository level, so `deploy-dev` and `promote` each pick up their own
stack's role/instance/document/URL automatically from the `environment:` they
declare (`AWS_REGION` is the one exception — same region for both, so it stays
a repository variable). `dev`'s environment-scoped variables are the
repository-level ones already set (see "Continuous deployment"); `production`
has its own, set once with the `sdip-prod` stack's own
`GitHubVariablesCommand` output, `--env production`.

Look up either stack's current parameters and outputs any time:

```sh
aws cloudformation describe-stacks --stack-name sdip      --query 'Stacks[0].Outputs' --output table   # dev
aws cloudformation describe-stacks --stack-name sdip-prod --query 'Stacks[0].Outputs' --output table   # production
```

### What you need first

- A domain you can add an A record to.
- AWS credentials with permission to create VPC, EC2, and IAM resources.
- This repository reachable over HTTPS without credentials. The instance clones
  it on boot and has no secrets, so a private repository needs a deploy key
  installed by hand.

### Deploy

```sh
aws cloudformation deploy \
  --template-file deploy/aws/sdip-stack.yaml \
  --stack-name sdip \
  --capabilities CAPABILITY_IAM \
  --parameter-overrides \
      DomainName=interviews.example.com \
      TlsEmail=you@example.com \
      RepoUrl=https://github.com/alexeygrigorev/interview-canvas-share.git
```

Nothing in the template is region-specific — the subnet takes the first
availability zone of whatever region you deploy into, and the AMI resolves from
an SSM public parameter that exists everywhere — so the region comes from your
CLI configuration, or from an explicit `--region`. Choose the one closest to the
people interviewing: every canvas edit round-trips through this single instance,
so its distance from participants is felt directly as lag.

`CAPABILITY_IAM` is required because the stack creates an instance role granting
Session Manager access — that is what lets you get a shell without opening port
22 or managing a key pair. Add `KeyName` and `SshCidr` parameters only if you
want conventional SSH as a fallback.

Then read the Elastic IP out of the stack and point your domain at it:

```sh
aws cloudformation describe-stacks --stack-name sdip \
  --query 'Stacks[0].Outputs' --output table
```

Certificate issuance fails until that A record resolves, which is normal on a
first deploy — Caddy keeps retrying and the site comes up on its own once DNS
propagates.

### The DNS record is not part of the stack

The template allocates the Elastic IP and outputs it, but never creates the A
record. That is deliberate: a `AWS::Route53::RecordSet` would need a hosted
zone id and would assume the domain is hosted in Route53 in this same account,
and plenty of domains live at a registrar or at Cloudflare instead.

The cost of that choice is that the record's lifecycle is yours, at both ends.
Create it after the stack comes up, and **delete it after you delete the
stack** — the Elastic IP goes back into the AWS pool on release, so a record
left behind eventually points at a stranger's server.

With the zone in Route53, both directions are one call:

```sh
zone=$(aws route53 list-hosted-zones-by-name --dns-name example.com \
  --query 'HostedZones[0].Id' --output text)
ip=$(aws cloudformation describe-stacks --stack-name sdip \
  --query "Stacks[0].Outputs[?OutputKey=='ElasticIp'].OutputValue" --output text)

# UPSERT to create or repoint it; DELETE, with the same values, to remove it.
aws route53 change-resource-record-sets --hosted-zone-id "$zone" --change-batch "{
  \"Changes\": [{\"Action\": \"UPSERT\", \"ResourceRecordSet\": {
    \"Name\": \"interviews.example.com.\", \"Type\": \"A\", \"TTL\": 60,
    \"ResourceRecords\": [{\"Value\": \"$ip\"}]}}]}"
```

A `DELETE` change must repeat the record's current name, type, TTL and value
exactly, so read it back with `list-resource-record-sets` before removing it
rather than retyping it from memory.

### Delete the stack

Deleting takes the instance, its root volume, and the database on that volume
with it. Nothing is backed up for you, so dump first if the data matters:

```sh
aws ssm start-session --target "$(aws cloudformation describe-stacks \
  --stack-name sdip --query "Stacks[0].Outputs[?OutputKey=='InstanceId'].OutputValue" \
  --output text)"
# on the instance:
cd /opt/sdip && sudo docker compose -f docker-compose.prod.yaml exec -T postgres \
  pg_dump -U sdip sdip | gzip > /tmp/sdip.sql.gz
```

Then, in order:

```sh
# 1. the DNS record, which the stack does not own (see above)
# 2. the stack itself
aws cloudformation delete-stack --stack-name sdip
aws cloudformation wait stack-delete-complete --stack-name sdip
# 3. the deploy variables, or every later push fails against a dead instance
gh variable delete SDIP_INSTANCE_ID
gh variable delete SDIP_DEPLOY_DOCUMENT
gh variable delete AWS_DEPLOY_ROLE_ARN
gh variable delete SDIP_PUBLIC_URL
```

Deleting `SDIP_INSTANCE_ID` alone is enough to make CI skip the deploy job
again; the rest is tidiness. The account's GitHub OIDC provider survives if
this stack did not create it (`CreateGitHubOidcProvider=false`), since it is
shared with every other repository that deploys into the account.

### HTTPS without a domain, via CloudFront

Browsers will not open a `wss://` WebSocket without a valid certificate, and
certificate authorities only issue for domains you can prove you control. If you
have no domain, CloudFront is the way out: every distribution comes with a free
`*.cloudfront.net` hostname and a browser-trusted certificate.

```sh
aws cloudformation deploy \
  --template-file deploy/aws/sdip-stack.yaml \
  --stack-name sdip \
  --capabilities CAPABILITY_IAM \
  --parameter-overrides \
      DomainName= \
      EnableCloudFront=true \
      TlsEmail=you@example.com \
      RepoUrl=https://github.com/alexeygrigorev/interview-canvas-share.git
```

Leaving `DomainName` empty tells the bootstrap to configure Caddy as a plain
HTTP server on `:80` for any `Host`, since CloudFront is terminating TLS
instead. `EnableCloudFront=true` then also narrows port 80 to the
`com.amazonaws.global.cloudfront.origin-facing` prefix list, so the origin stops
answering the public internet and the only route in is HTTPS through CloudFront.
Read the URL from the `CloudFrontUrl` stack output; the distribution takes a few
minutes to reach every edge.

Two things to understand about this mode:

- **It is not end-to-end encryption.** Viewer-to-CloudFront is HTTPS, but
  CloudFront-to-origin is plain HTTP across the public internet, because the
  origin has no certificate to present. A real domain with Caddy issuing its own
  certificate is strictly better. This exists for when there is no domain.
- **`CloudFrontPrefixListId` is region specific.** The default is the eu-west-1
  ID. In another region, look yours up:

  ```sh
  aws ec2 describe-managed-prefix-lists \
    --filters Name=prefix-list-name,Values=com.amazonaws.global.cloudfront.origin-facing \
    --query 'PrefixLists[].PrefixListId' --output text
  ```

The distribution disables caching entirely and forwards every method, header,
cookie and query string to the origin. That is deliberate: the app is fully
dynamic and authenticated, and the `Upgrade` and `Sec-WebSocket-*` headers have
to survive the trip or the realtime canvas silently stops syncing.

### Your own domain on CloudFront

Want CloudFront's HTTPS *and* a real hostname instead of `*.cloudfront.net`?
CloudFront only accepts certificates from `us-east-1`, no matter which region
the distribution or the rest of the stack live in, so the certificate is a
separate stack in that region:

```sh
aws cloudformation deploy \
  --region us-east-1 \
  --template-file deploy/aws/sdip-domain.yaml \
  --stack-name sdip-domain \
  --parameter-overrides \
      DomainName=interviews.example.com \
      HostedZoneId=<your Route53 hosted zone ID>
```

`HostedZoneId` must be a Route53 zone in this account: CloudFormation creates
the validation record and waits for ACM to issue the certificate, which
usually takes a few minutes. Feed the `CertificateArn` output into the main
stack alongside `EnableCloudFront=true`:

```sh
aws cloudformation deploy \
  --template-file deploy/aws/sdip-stack.yaml \
  --stack-name sdip \
  --capabilities CAPABILITY_IAM \
  --parameter-overrides \
      DomainName= \
      EnableCloudFront=true \
      CloudFrontDomainName=interviews.example.com \
      CloudFrontCertificateArn=<CertificateArn output above> \
      CloudFrontHostedZoneId=<your Route53 hosted zone ID> \
      TlsEmail=you@example.com \
      RepoUrl=https://github.com/alexeygrigorev/interview-canvas-share.git
```

`CloudFrontHostedZoneId` is optional and only saves you a manual step: when
set, the stack creates the alias A record for you. Leave it empty to point
DNS at the `CloudFrontUrl` output by hand instead. Either way, set
`SDIP_PUBLIC_URL` to the `CloudFrontDomainUrl` output so CI's post-deploy
smoke test checks the right host.

### Changing the bootstrap replaces the instance

Any edit to the template's `UserData` — including switching `DomainName` between
empty and set — changes the instance's launch configuration, so CloudFormation
replaces the instance rather than updating it in place. **That destroys the
PostgreSQL volume with it.** Check `aws cloudformation deploy
--no-execute-changeset` and inspect the change set for `Replacement` before
applying an update to a stack holding data you care about, and take a dump
first:

```sh
aws cloudformation describe-change-set --change-set-name <arn> \
  --query 'Changes[].ResourceChange.{Id:LogicalResourceId,Replacement:Replacement}' \
  --output table
```

### Running before you have a domain

Caddy accepts an `http://` site address as an explicit instruction to serve
without TLS and skip certificate issuance entirely, so you can bring the stack
up on the bare Elastic IP while DNS is still pending:

```sh
sed -i 's|^SDIP_DOMAIN=.*|SDIP_DOMAIN=http://203.0.113.10|' /opt/sdip/.env
docker compose -f docker-compose.prod.yaml up -d
```

The app is fully functional this way — the page and its WebSocket are both plain
HTTP from the same origin, so nothing is blocked as mixed content. It is only
appropriate for verifying a deployment: access tokens and the guest session
cookie cross the network in the clear. Switch `SDIP_DOMAIN` back to a hostname
and restart to get HTTPS.

### Watch the first boot

The stack reports `CREATE_COMPLETE` as soon as the instance launches, not when
the app is serving traffic. Building the frontend bundle and starting the
containers takes several minutes more. To follow it:

```sh
aws ssm start-session --target <InstanceId from the stack outputs>
sudo tail -f /var/log/sdip-bootstrap.log
```

The JWT signing secret and the database password are generated on the instance
during that boot and written only to `/opt/sdip/.env` with mode `600`. They are
not stack parameters, so they never appear in the template, the stack events, or
the instance metadata. Regenerating `SDIP_JWT_SECRET` logs everyone out, which
is the intended effect if you ever need to revoke every issued token.

### Ship a new version

```sh
cd /opt/sdip
sudo git pull
sudo docker compose -f docker-compose.prod.yaml up -d --build
```

Rebuilding restarts the app container, which drops open WebSockets. Clients
reconnect about a second later and reload the canvas from the database, so an
interview in progress sees a brief "Reconnecting" badge rather than losing work.

These are the same steps the stack's `<stack>-deploy` SSM document runs, so a
push to `main` can do it for you — see "Continuous deployment" below.

### Back up

The PostgreSQL volume lives on the instance's root EBS volume, and deleting the
stack terminates the instance and that volume with it. Nothing is backed up for
you. At minimum, dump the database before any risky change:

```sh
sudo docker compose -f docker-compose.prod.yaml exec -T postgres \
  pg_dump -U sdip sdip | gzip > "sdip-$(date +%F).sql.gz"
```

For anything you care about, put that on a cron job writing to S3, or move the
database to RDS by pointing `SDIP_DATABASE_URL` at it and dropping the
`postgres` service from the compose file.

### What it costs

About $19/month in `eu-west-1` at list price: $13.43 for the `t4g.small`
instance, $1.76 for 20 GiB of gp3, and $3.65 for the public IPv4 address. Data
transfer for a handful of concurrent interviews is negligible. Instance and
storage rates vary by region; the IPv4 charge does not.

`EnableCloudFront=true` adds nothing meaningful: CloudFront's always-free tier
covers 1 TB of egress and 10 million requests per month, which a handful of
interviews will not approach.

### Scaling past one instance

When one box is no longer enough, the fix is contained to `broadcast_message` in
`backend/app/routers/realtime.py:56`: replace the in-process fan-out with
PostgreSQL `LISTEN`/`NOTIFY` — no new infrastructure, since the database is
already there — or with Redis pub/sub. Only once every replica can reach every
connection does adding replicas become safe.

## Run locally without Docker

The backend uses [uv](https://docs.astral.sh/uv/) for dependency management:

```sh
make sync   # install backend dependencies
make run    # start the API with auto-reload on http://127.0.0.1:8091
make test   # run the backend test suite
```

Override the bind address with `make run HOST=0.0.0.0 PORT=8080`.

The frontend dev server runs separately:

```sh
cd frontend
npm install
npm run dev
```

See `backend/README.md` for more backend detail.

## Tests

Four suites, in the order CI runs them:

| Suite | Lives in | Needs | Command |
| --- | --- | --- | --- |
| Backend | `backend/tests` | uv | `make test` |
| Frontend unit | `frontend/src/**/*.test.ts` | Node | `make frontend-test` |
| Integration | `integration/tests` | the running stack | `make up && make integration` |
| End-to-end | `e2e/tests` | the running stack, Chromium | `make e2e` |

The first two run in-process and need no services. The last two exercise a real
deployment, so they catch what the unit suites structurally cannot: the built
image, the frontend bundle it serves, PostgreSQL, and the WebSocket gateway.

### Integration tests

`integration/` drives the deployed API over HTTP and WebSocket without importing
a line of the backend — login, the session lifecycle, guest links and cookies,
canvas persistence, and realtime fan-out between two connected clients.

```sh
make up            # docker compose up -d --build --wait
make integration
make down
```

Point them at any deployment with `SDIP_BASE_URL`. See `integration/README.md`.

### End-to-end tests

`e2e/` holds Playwright tests that drive the compose deployment through a real
browser: the interviewer logs in, creates a session, shares the join link, a
second client joins as the candidate and edits the canvas, and the interviewer's
screen is checked for that edit.

```sh
make e2e
```

Playwright brings the stack up with `docker compose up --build` and stops it
afterwards, reusing a deployment that is already running on the app port. See
`e2e/README.md` for configuration and how to run it headed or in the debugger.

## CI/CD

`.github/workflows/ci.yml` runs on every pull request and on pushes to `main`:

```
Backend tests  ─┐
                ├─► Integration and E2E tests ─► Deploy to production
Frontend tests ─┘        (compose stack)          (main, if configured)
```

- **Backend tests** run the suite twice — once on SQLite, once against a
  PostgreSQL service container — so the PostgreSQL-only paths (`JSONB` columns,
  the advisory locks around seeding) are covered.
- **Frontend tests** run the unit tests, `tsc --noEmit`, and the production
  build, which is the same build the Dockerfile performs.
- **Integration and E2E** build the image, bring up `docker-compose.yaml` once,
  and run both suites against that one deployment. Integration goes first: it
  fails in seconds with an API-level message, where a browser failure needs its
  trace to explain itself. On failure the job prints the stack logs and uploads
  the Playwright report and traces as an artifact.

The two unit jobs run in parallel; the stack job waits for both, since the image
build is the expensive part of the run and nothing can pass while a unit suite
is red.

### Continuous deployment

This section describes the mechanism once per stack; both `sdip` (dev) and
`sdip-prod` (production) use it identically, just with different
`GitHubEnvironment`/instance/document values — see "Environments" above.

The `deploy-dev` job is skipped unless the repository has `SDIP_INSTANCE_ID`
set, so the pipeline is CI-only until you configure it. It reproduces "Ship a
new version" above without SSH: GitHub authenticates to AWS with OIDC and asks
Systems Manager to run the stack's deploy document on the instance.

There are no long-lived AWS keys anywhere. GitHub mints a short-lived OIDC
token per job, AWS exchanges it for temporary credentials, and the trust policy
decides who may make that exchange.

**Create the role.** It is part of the CloudFormation stack — redeploy with
your repository name, and the template creates the account's GitHub OIDC
provider (set `CreateGitHubOidcProvider=false` if the account already has one),
the deploy document, and the role:

```sh
aws cloudformation deploy \
  --template-file deploy/aws/sdip-stack.yaml \
  --stack-name sdip \
  --capabilities CAPABILITY_IAM \
  --parameter-overrides \
      GitHubRepository=alexeygrigorev/interview-canvas-share \
      DomainName=interviews.example.com \
      TlsEmail=you@example.com \
      RepoUrl=https://github.com/alexeygrigorev/interview-canvas-share.git
```

**Point the workflow at it.** The stack's `GitHubVariablesCommand` output is
the exact command to run; it expands to:

```sh
gh variable set AWS_REGION           --body eu-west-1
gh variable set AWS_DEPLOY_ROLE_ARN  --body arn:aws:iam::123456789012:role/sdip-GitHubDeployRole-...
gh variable set SDIP_DEPLOY_DOCUMENT --body sdip-deploy
gh variable set SDIP_INSTANCE_ID     --body i-0123456789abcdef0
gh variable set SDIP_PUBLIC_URL      --body https://interviews.example.com   # optional
```

`SDIP_INSTANCE_ID` is the on/off switch; `SDIP_PUBLIC_URL` is optional and only
adds a `/health` poll after the deploy. The `production` environment must exist
in the repository — create it, and add required reviewers there if you want a
human gate before each deploy.

**What the role can do.** Only two things, and neither is shell access:

| Action | Scoped to |
| --- | --- |
| `ssm:SendCommand` | this instance, and only the `<stack>-deploy` document |
| `ssm:GetCommandInvocation` | `*` — SSM defines no resource types for it |

The deployment steps live in the SSM document inside the template, not in the
workflow, and that is the whole point. Granting `SendCommand` on the AWS-owned
`AWS-RunShellScript` document — the usual shortcut — would let anything holding
this role run arbitrary commands as root on the instance. Here the only input
is the commit SHA, and the document's `allowedPattern` rejects anything that is
not one, so the worst a stolen token can do is redeploy some commit of this
repository. Changing *what* a deploy does means changing the template, which is
reviewed and versioned like the rest of the infrastructure.

The trust policy pins the token's subject to
`repo:<owner>/<repo>:environment:<GitHubEnvironment>` — `dev` for `sdip`,
`production` for `sdip-prod`. That claim is the environment form — **not**
`ref:refs/heads/main` — because the job declares an `environment:`. Using the
ref form is the usual cause of "Not authorized to perform
sts:AssumeRoleWithWebIdentity" on a first deploy. Pinning the environment also
means a fork's pull request cannot assume either role: forks cannot reach a
protected environment, and the audience check keeps unrelated workflows out
entirely.

Deploys are serial by design: the workflow's concurrency group does not cancel
in-flight runs on `main`, so a half-finished rebuild is never interrupted.

### Promote to production

There is no automatic path to production — `deploy-dev` only ever touches
`sdip`. Shipping to `sdip-prod` is the separate
`.github/workflows/promote.yml` workflow, triggered by hand from the Actions
tab (`workflow_dispatch`, no other trigger). It does not build anything new:
it reads `SDIP_DEV_DEPLOYED_SHA` — the commit `deploy-dev` last confirmed
healthy on dev — and runs the exact same SSM deploy document against the
`sdip-prod` instance, so what ships to production is always a build that
already ran on dev, never an untested commit.

```sh
gh workflow run promote.yml
gh run watch    # or follow it in the Actions tab
```

`SDIP_DEV_DEPLOYED_SHA` is a plain repository variable, written by the last
step of `deploy-dev` only after its own smoke test passes — so a dev deploy
that never came up healthy is never eligible for promotion. Set it by hand if
you ever need to promote a specific commit outside that flow:

```sh
gh variable set SDIP_DEV_DEPLOYED_SHA --body <commit-sha>
```

The `promote` job declares `environment: production`, so it authenticates as
`sdip-prod`'s own `GitHubDeployRole` — a separate role from `sdip`'s, trusting
only the `production` OIDC subject, scoped to only the `sdip-prod-deploy`
document and the `sdip-prod` instance. It cannot touch dev, and `deploy-dev`'s
role cannot touch production.

Want an explicit approval click in front of the run, on top of it already
being manual? Add required reviewers to the `production` environment in the
repository's Settings → Environments — `promote` will then pause for sign-off
before it runs.
