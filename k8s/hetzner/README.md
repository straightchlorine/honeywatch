# honeywatch on Hetzner k3s

Kustomize manifests deployed by ArgoCD. Everything for this workload lives in this repo; the platform fleet repo holds only cross-cutting concerns (Headscale ACL tags, sealed-secrets controller). Bootstrap is a one-shot `kubectl apply`.

## Layout

| File | Purpose |
|---|---|
| `namespace.yaml` | Namespace `honeywatch` |
| `dashboard.yaml` | Dashboard Deployment + Service (image: `ghcr.io/straightchlorine/honeywatch/dashboard`, tracked by Image Updater) |
| `egress.yaml` | Tailscale egress sidecar: ServiceAccount + Role + RoleBinding + Deployment + `honeypot-api` Service. DNATs cluster traffic to the honeypot VPS via Headscale |
| `middleware.yaml` | Traefik `RateLimit` middleware (60 req/min per IP, burst 20) |
| `ingress.yaml` | Ingress for `honey.piotrkrzysztof.dev` (LE TLS, `/api/*` -> honeypot-api, `/` -> dashboard) |
| `secret.yaml` | SealedSecret `honeywatch-egress` holding `TS_AUTHKEY` + `HONEYPOT_TS_IP`. Generated during bootstrap (see below) |
| `kustomization.yaml` | Joins the above; carries the Image Updater write-back target for the dashboard tag |
| `argocd-app.yaml` | ArgoCD Application (not part of the kustomization; for `kubectl apply` bootstrap) |

No plaintext IPs in the repo: `HONEYPOT_TS_IP` lives inside the SealedSecret.

## Topology

```
Internet
   |  honey.piotrkrzysztof.dev (Traefik + LE TLS + RateLimit)
   |--- /api/*  ->  svc/honeypot-api  ->  ts-egress pod  == Headscale ==>  honeypot VPS :5000
   \--- /       ->  svc/dashboard
```

## Bootstrap (one-time, per cluster)

1. **Honeypot VPS joins the tailnet.**
   ```bash
   # on the honeypot VPS
   curl -fsSL https://tailscale.com/install.sh | sh
   sudo tailscale up \
       --login-server=https://vpn.codextechnologies.org \
       --advertise-tags=tag:honeypot
   tailscale ip -4   # note this address -> $TS_DEST_IP
   ```
   Approve the `tag:honeypot` tag via headplane if needed.

2. **Mint a reusable pre-auth key** for the egress sidecar:
   ```bash
   kubectl -n headscale exec deploy/headscale -- \
     headscale preauthkeys create \
       --user piotrkrzysztof \
       --reusable \
       --expiration 8760h \
       --tags tag:honeywatch-egress
   # -> $TS_AUTHKEY
   ```

3. **Seal both values into a single Secret** named `honeywatch-egress` and commit:
   ```bash
   kubectl -n honeywatch create secret generic honeywatch-egress \
       --from-literal=TS_AUTHKEY="$TS_AUTHKEY" \
       --from-literal=HONEYPOT_TS_IP="$TS_DEST_IP" \
       --dry-run=client -o yaml \
     | kubeseal --cert ~/code/fleet/.sealed-secrets-cert.pem -o yaml \
     > k8s/hetzner/secret.yaml
   ```
   Uncomment `- secret.yaml` in `kustomization.yaml`.

4. **Bootstrap the Application** (once per cluster):
   ```bash
   kubectl apply -f k8s/hetzner/argocd-app.yaml
   ```
   ArgoCD now tracks this repo's `k8s/hetzner/` path. Push to `master` and it reconciles. ArgoCD must have read access to this repo (public on GitHub, no credentials needed) and Image Updater must have a writable Git credential for it (configure once in the `argocd-image-updater` ConfigMap in fleet).

5. **Verify:**
   ```bash
   kubectl -n honeywatch get pods
   curl -s https://honey.piotrkrzysztof.dev/api/stats
   ```

## Image Updater

The dashboard image is released by `.github/workflows/release.yml` with both `{{version}}` and `latest` tags on each `v*.*.*` push. The Application annotations in `argocd-app.yaml` tell Image Updater to:

- watch `ghcr.io/straightchlorine/honeywatch/dashboard`
- accept any `X.Y.Z` tag (semver)
- commit the new tag into `k8s/hetzner/kustomization.yaml` under `images:`
- ArgoCD picks up the commit and rolls out

The ingestor and API are not published to the cluster, so they're not in the image list.
