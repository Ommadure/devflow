# Deploying DevFlow

The production layout from [ADR 0008](adr/0008-hosting-neon-oracle-vercel.md) and
[ADR 0009](adr/0009-own-a1-vm-and-client-ip.md). Everything is free. About an hour the
first time, most of it waiting for builds.

| Piece | Where | Cost |
| --- | --- | --- |
| API, Taskiq worker + scheduler, Redis, HTTPS (Caddy) | an Oracle Always Free **A1 (ARM)** VM, DevFlow's own | $0 |
| Postgres + pgvector | Neon, free | $0 |
| Frontend | Vercel, free, with a `/api/v1` rewrite to the VM | $0 |
| HTTPS hostname for the VM | DuckDNS, free | $0 |

Pick **Singapore** wherever there's a region choice (Oracle `ap-singapore-1`, Neon
`AWS ap-southeast-1`), so every piece sits in one place. Secrets go into each provider's
dashboard and the VM's env file only — never into the repo or a chat.

```
browser ──https──▶ Vercel (static app; /api/v1/* rewritten) ──https──▶ Caddy on the VM ──▶ api
                                                                                    worker, scheduler ──▶ Redis (VM)
                                                                       api, worker ──TLS──▶ Neon
```

---

## 1. Neon (Postgres)
1. [console.neon.tech](https://console.neon.tech) → **New project** `devflow`, Postgres 16,
   region **AWS Asia Pacific (Singapore)**.
2. **Connect** → with **Connection pooling on**, copy the string (its host contains
   `-pooler`): that's `DATABASE_URL`. Turn pooling **off** and copy again: that's
   `DATABASE_DIRECT_URL` (migrations need a direct connection).
3. Nothing else to do: the first migration runs `CREATE EXTENSION vector` itself, and the
   API disables asyncpg's statement cache on the pooled host by itself.

## 2. The Oracle A1 VM
Your Oracle account (Singapore home region, Pay As You Go with a $1 budget alert) is the
one ReviewPilot already uses.

1. **Compute → Instances → Create instance**, named `devflow`.
2. **Image:** Canonical **Ubuntu 24.04** (the aarch64 build is picked automatically for an
   Ampere shape).
3. **Shape:** **Ampere → VM.Standard.A1.Flex, 2 OCPU, 12 GB**. That is half the Always
   Free A1 allowance (4 OCPU / 24 GB), leaving the rest for ReviewPilot to move onto later.
   DevFlow itself needs ~750 MB, so anything from 1 OCPU / 6 GB up is fine.
   - **"Out of host capacity"** is common for A1 in Singapore. Try each availability
     domain / fault domain, try again at a different hour, or start smaller
     (1 OCPU / 6 GB) and resize later (**Edit → Shape**, a reboot).
4. **Networking:** keep "Assign a public IPv4 address" on.
5. **SSH keys:** "Generate a key pair for me" → **save the private key**, then on your laptop:
   ```bash
   mv ~/Downloads/ssh-key-*.key ~/.ssh/devflow-vm.key && chmod 600 ~/.ssh/devflow-vm.key
   ```
6. Create it and copy its **Public IP address**.
7. **Open ports 80 and 443:** instance page → **Subnet → Security List → Add Ingress Rules**:
   source `0.0.0.0/0`, TCP, destination port `80`; and the same for `443`. (If the VM
   shares ReviewPilot's VCN and subnet, these rules already exist.)

## 3. A hostname: DuckDNS
Let's Encrypt needs a name, not a bare IP.
1. [duckdns.org](https://www.duckdns.org) → add the subdomain **`devflow-om`** and set it
   to the VM's IP (**update ip**).
2. The API is now `https://devflow-om.duckdns.org`. Using another name? Change it in
   `frontend/vercel.json` (the rewrite) and `API_DOMAIN` below.

## 4. Set up the VM
From your laptop, in the repository folder:
```bash
scp -i ~/.ssh/devflow-vm.key deploy/oracle/bootstrap.sh ubuntu@<vm-ip>:
```
```bash
ssh -i ~/.ssh/devflow-vm.key ubuntu@<vm-ip> 'bash bootstrap.sh'
```
It installs Docker, opens 80/443 in the VM's own firewall, turns on automatic security
updates and prints a **deploy key**. Add it on GitHub: `Ommadure/devflow` → **Settings →
Deploy keys → Add deploy key**, title `oracle-vm`, **Allow write access unchecked**.

Log in again (so the docker group applies) and clone:
```bash
ssh -i ~/.ssh/devflow-vm.key ubuntu@<vm-ip>
```
```bash
git clone github-devflow:Ommadure/devflow.git ~/devflow && cd ~/devflow && cp deploy/oracle/.env.production.example deploy/oracle/.env.production && nano deploy/oracle/.env.production
```

Fill in the file (git-ignored; `deploy.sh` makes it readable by you only):

| Variable | Value |
| --- | --- |
| `API_DOMAIN` | `devflow-om.duckdns.org` |
| `DATABASE_URL`, `DATABASE_DIRECT_URL` | the two Neon strings from step 1, pasted as-is |
| `JWT_SECRET` | run `python3 -c "import secrets; print(secrets.token_urlsafe(48))"` on the VM |
| `CORS_ORIGINS` | the Vercel domain from step 6 (fill in after step 6, then re-run `deploy.sh`) |
| `GEMINI_API_KEY` | your Gemini key |
| `GITHUB_TOKEN` | optional: a GitHub token with **no scopes** |

## 5. Start it
```bash
~/devflow/deploy/oracle/deploy.sh
```
The first build takes several minutes (it downloads the embedding model into the image).
Caddy then fetches the certificate by itself. Check it:
```bash
curl -s https://devflow-om.duckdns.org/ready
```
Expect `{"status":"ok","checks":{"database":"ok","redis":"ok"}}`. After an idle spell the
first check takes a few seconds while Neon wakes up.

## 6. Vercel (frontend)
1. [vercel.com/new](https://vercel.com/new) → **Import** `Ommadure/devflow` as a **new
   project** named `devflow-om`.
2. **Root Directory:** `frontend`. `frontend/vercel.json` sets the framework, the build,
   the `/api/v1` rewrite and the security headers (CSP included).
3. No environment variables: the frontend has none (the API is same-origin through the
   rewrite, and nothing secret may ever be a `VITE_` variable).
4. Deploy. In **Settings → Domains** copy the production domain, e.g.
   `https://devflow-om.vercel.app` — not a per-deployment link, which sits behind Vercel's
   login. **Settings → Deployment Protection:** Vercel Authentication only for previews.
5. Put that domain in `CORS_ORIGINS` on the VM (no trailing slash) and run `deploy.sh`.
   It is also what the refresh endpoint's Origin check accepts: until it's set, signing in
   works but a page reload signs you out.

## 7. Check it end to end
1. Open the Vercel URL, create an account, reload: still signed in.
2. Create a snippet; within seconds its search badge goes from pending to ready. Search
   "stop a function from firing too often" for a debounce snippet: a semantic match.
3. Explain the snippet: tokens stream in (SSE through Vercel's rewrite and Caddy).
4. API Tester: send `GET https://api.github.com/zen`.
5. On the VM, the worker log shows the embedding job:
   ```bash
   docker compose -f ~/devflow/deploy/oracle/compose.yaml logs --tail 50 worker
   ```

## Operating it
- **Deploy an update:** merge to `main`, then run `~/devflow/deploy/oracle/deploy.sh` on
  the VM. Migrations run when the API starts, so keep them additive.
- **Backfill embeddings** (after importing data, or to retry failures):
  ```bash
  docker compose -f ~/devflow/deploy/oracle/compose.yaml exec api python scripts/backfill_embeddings.py --include-failed
  ```
- **Logs:** `docker compose -f ~/devflow/deploy/oracle/compose.yaml logs -f api worker scheduler`
  (JSON lines, rotated at 3 × 10 MB per service).
- **Scheduler:** exactly one. A second scheduler container would run every cron job twice.
- **Rotating `JWT_SECRET`:** edit the env file, run `deploy.sh`. Access tokens die within
  15 minutes; refresh sessions survive (they're random tokens in the database).
- **If the VM is lost:** it holds nothing that matters — data is in Neon, and Redis holds
  only queues, rate-limit counters and caches. Repeat steps 2–5 and update DuckDNS.
- **Security:** SSH is key-only, OS updates install themselves, only 22/80/443 are open,
  and the API container is reachable only through Caddy.
