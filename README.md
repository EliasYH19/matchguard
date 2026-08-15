# MatchGuard

Anti-cheat verification as a service, for online and LAN-hosted gaming
tournaments.

**Cloud Computing, Final Project, August 2026**
**Author: Elias**

---

## The idea

Most anti-cheat (Vanguard, EAC, BattlEye, etc.) is baked into a specific
game client and useless to a community organizer running, say, a regional
Rocket League LAN or an online chess bracket. MatchGuard is the anti-cheat
layer those organizers don't otherwise have access to: buy a package,
create a tournament, players register and upload a quick system/process
snapshot, and MatchGuard checks it against known cheat-tool signatures and
file hashes. Clean players get a digital certificate, flagged ones show up
on the organizer's dashboard before round one starts.

It is **not** trying to be a kernel-level anti-cheat driver, that's out of
scope for a five-week module. It's a verification/paperwork layer that a
grassroots tournament can actually plug in.

## Architecture

```
                     ┌─────────────────────┐
   browser  ───────► │   frontend (nginx)   │
                     │  static HTML/CSS/JS  │
                     └──────────┬───────────┘
                                │  /api/* reverse-proxied
                 ┌──────────────┴───────────────┐
                 ▼                               ▼
      ┌────────────────────┐          ┌────────────────────┐
      │ tournament-service  │          │   scan-service      │
      │  (Flask REST API)   │◄────────►│  (Flask REST API)   │
      │  tournaments,       │  REST    │  evidence upload,   │
      │  packages, purchases,│ callback │  hashing, keyword   │
      │  registrations       │          │  scan, flagged feed │
      └─────────┬───────────┘          └──────────┬──────────┘
                │                                  │
                │           Azure Blob Storage      │
                └─────────────────┬─────────────────┘
                                  │
                                  ▼
                       ┌────────────────────┐
                       │  notify-function     │
                       │  (Azure Function,     │
                       │   serverless)         │
                       │  generates & stores   │
                       │  verification certs   │
                       └────────────────────┘
```

Two independently deployable Flask microservices (own Dockerfile, own
`requirements.txt`, own SQLite database), a static frontend served by
nginx, Azure Blob Storage for evidence/banners/certificates, and one Azure
Function that turns a scan verdict into a signed certificate. Everything
talks over REST.

| Piece | Tech | Why |
|---|---|---|
| `frontend/` | plain HTML/CSS/JS + nginx | no build step, matches how we built the earlier lab exercises, easy to host anywhere static |
| `services/tournament-service/` | Flask + SQLite | owns tournaments/packages/purchases/registrations |
| `services/scan-service/` | Flask + SQLite | owns evidence upload, hashing, signature scanning, flagged feed |
| `serverless/notify-function/` | Azure Functions (Python) | generates verification certificates, the required serverless component |
| Azure Blob Storage | `azure-storage-blob` SDK | stores tournament banners, scan evidence, certificates |
| Docker | one `Dockerfile` per service/frontend | containerizes everything |
| Kubernetes | `k8s/*.yaml` | orchestrates the three containers plus secret and ingress |

### Pages (6, nav has 5 + tournament detail reached by click)

1. **Home** (`index.html`): pitch, how it works
2. **Packages** (`packages.html`): Bronze/Silver/Gold pricing, pulled live from `/api/packages`
3. **Tournaments** (`tournaments.html`): browse + create a tournament (with banner upload)
4. **Tournament detail** (`tournament.html?id=...`): purchase, register players, submit scans
5. **Organizer Dashboard** (`dashboard.html`): flagged-player feed across tournaments
6. **About** (`about.html`): architecture write-up, sample files, author/contact

## Running it locally

You need Docker + Docker Compose installed (same tools from the labs).

```bash
git clone <your-repo-url> matchguard
cd matchguard
docker compose up --build
```

- Frontend: http://localhost:8080
- tournament-service: http://localhost:5001/api/health
- scan-service: http://localhost:5002/api/health

No `AZURE_STORAGE_CONNECTION_STRING` needed to try it out, both services
fall back to writing uploaded files to a local folder
(`services/*/local_blob_storage/`) and serve them back over HTTP, so the
whole flow (create tournament, purchase, register, upload scan, see
verdict and certificate, check dashboard) works out of the box.

Two ready-made sample uploads live in `docs/sample-uploads/`:

- `clean-system-log.txt` comes back **CLEAR**
- `suspicious-system-log.txt` comes back **FLAGGED** (matches `cheatengine`, `aimbot`, `injector.dll`)

## Connecting real Azure Blob Storage

Same steps as the "Create a blob storage in Azure" lab exercise:

1. Go to **portal.azure.com**, search **Storage accounts**, click **Create**.
2. Pick a resource group, give it a globally unique name (e.g. `matchguardstorage`), region close to you, **Standard** performance, **LRS** redundancy, then **Review + create**.
3. Once it's deployed, open the storage account, go to **Containers**, and create three private containers: `tournament-banners`, `scan-evidence`, `certificates` (the app also auto-creates them on first upload if you skip this step).
4. In the left menu: **Security + networking**, then **Access keys**, then **Show** next to key1, then copy the **Connection string**.
5. Base64-encode it and paste it into `k8s/azure-secret.yaml`:
   ```bash
   echo -n '<your connection string>' | base64
   ```
6. For local Docker Compose instead of Kubernetes, just export it before `docker compose up`:
   ```bash
   export AZURE_STORAGE_CONNECTION_STRING="<your connection string>"
   docker compose up --build
   ```

From that point on every upload goes to the real Azure Storage account
instead of the local fallback folder.

## Deploying the serverless function

See `serverless/notify-function/README.md` for the full walkthrough
(`func azure functionapp publish ...`). Once deployed, set
`NOTIFY_FUNCTION_URL` on `scan-service` (env var locally, or the
`matchguard-config` ConfigMap in `k8s/scan-service.yaml`) to the function's
URL and key. Leave it blank and `scan-service` generates the same
certificate itself, which is handy while you're still setting the function up.

## Deploying to Kubernetes / Azure Kubernetes Service

```bash
# build & push your images somewhere your cluster can pull from
docker build -t <registry>/matchguard/tournament-service:latest services/tournament-service
docker build -t <registry>/matchguard/scan-service:latest services/scan-service
docker build -t <registry>/matchguard/frontend:latest frontend
docker push <registry>/matchguard/tournament-service:latest
docker push <registry>/matchguard/scan-service:latest
docker push <registry>/matchguard/frontend:latest

# point the manifests at your images (edit the `image:` lines in k8s/*.yaml),
# then apply everything
kubectl apply -f k8s/namespace.yaml
kubectl apply -f k8s/azure-secret.yaml
kubectl apply -f k8s/tournament-service.yaml
kubectl apply -f k8s/scan-service.yaml
kubectl apply -f k8s/frontend.yaml
kubectl apply -f k8s/ingress.yaml

kubectl -n matchguard get pods -w
```

For AKS specifically: `az aks create` a cluster, `az aks get-credentials`
to point `kubectl` at it, install an nginx ingress controller
(`kubectl apply -f https://raw.githubusercontent.com/kubernetes/ingress-nginx/.../deploy.yaml`
or `helm install ingress-nginx ...`), then run the steps above.

## Hosting

The frontend is a static site (`frontend/` after the nginx `Dockerfile`
build). It can also be pushed straight to Netlify/Azure Static Web Apps if
you don't want to run it in the cluster; just point its `nginx.conf`
proxy rules at wherever `tournament-service`/`scan-service` end up publicly
reachable (Azure Container Apps, AKS with a public ingress, etc.).

## CI/CD

- `Jenkinsfile`: build, test, build images, push, deploy to AKS, same
  shape as the CI/CD lab (Jenkins building the Git project from Task 3).
- `.github/workflows/ci-cd.yml`: the same pipeline as a GitHub Actions
  workflow, so it also runs automatically on push/PR without needing a
  Jenkins server set up.
- `scripts/deploy_blue_green.sh`: blue/green demo for the frontend
  container, same exercise as the CI/CD lab's Task 3, just wired to this
  project (`./scripts/deploy_blue_green.sh up|green|switch|rollback|down`).

Git workflow used while building this: feature branches
(`feature/tournament-service`, `feature/scan-service`, `feature/frontend`,
`feature/k8s`, and so on), no direct commits to `main`, merged through
pull requests, same branching model as the CI/CD lab's Task 2.

## Running the tests

```bash
cd services/tournament-service && pip install -r requirements.txt
cd ../scan-service && pip install -r requirements.txt
pip install pytest
cd ../..
pytest tests/
```

Both service test files spin the Flask app up against a throwaway sqlite
database and a local blob folder (via `monkeypatch`), so they don't need a
real Azure account or a running Docker setup to pass.

I also ran a full manual pass myself before calling this done: started both
services, walked through create tournament, purchase, register player,
upload both sample scan files, confirmed the CLEAR/FLAGGED verdicts,
certificate generation, the cross-service scan-status callback, and the
flagged-players feed all worked, then repeated the same flow through the
actual browser UI (Playwright) against the nginx-style routing, covering
every page and the create/purchase/register/scan/dashboard flow with zero
console errors. Docker/Kubernetes themselves couldn't be spun up inside my
own sandbox (no Docker daemon available there), so double-check
`docker compose up --build` on your machine before submitting. The
Dockerfiles are intentionally minimal and standard, but that step I
couldn't execute myself.

## API reference (short version)

**tournament-service** (`:5001`)
| Method | Path | What |
|---|---|---|
| GET | `/api/health` | liveness check |
| GET | `/api/packages` | list Bronze/Silver/Gold |
| GET | `/api/tournaments` | list tournaments |
| POST | `/api/tournaments` | create one (multipart, optional `banner` file) |
| GET | `/api/tournaments/<id>` | tournament + resolved package |
| POST | `/api/tournaments/<id>/purchase` | pay for the package, activates the tournament |
| GET | `/api/tournaments/<id>/registrations` | list players |
| POST | `/api/tournaments/<id>/registrations` | register a player |
| PATCH | `/api/registrations/<id>/scan-status` | internal, called by scan-service |

**scan-service** (`:5002`)
| Method | Path | What |
|---|---|---|
| GET | `/api/health` | liveness check |
| POST | `/api/scans` | upload evidence (multipart), returns verdict |
| GET | `/api/scans/flagged?tournament_id=` | flagged feed for the dashboard |
| GET | `/api/scans/tournament/<id>` | all scans for a tournament |
| GET | `/api/scans/registration/<id>` | all scans for a player |

## Project structure

```
matchguard/
├── frontend/                  static site + nginx reverse proxy config
├── services/
│   ├── tournament-service/    Flask microservice #1
│   └── scan-service/          Flask microservice #2
├── serverless/notify-function/ Azure Function (serverless component)
├── k8s/                       Kubernetes manifests
├── tests/                     pytest suite for both services
├── docs/                      sample uploads, user stories, this write-up's extras
├── scripts/                   blue/green demo script
├── docker-compose.yml
├── Jenkinsfile
└── .github/workflows/ci-cd.yml
```

---

Built by **Elias** for the Cloud Computing final project, submitted August 2026.
