# Melanin Technologies — Client Hosting Platform

Host Next.js and static HTML sites for clients, each in their own K8s namespace with a custom domain and auto-TLS. Structured for seamless migration to AWS EKS.

---

## Directory Structure

```
k8s/clients/
├── 00-bootstrap.yaml        # nginx-ingress + cert-manager ClusterIssuers (run once)
├── onboard-client.sh        # one-command client provisioning
├── aws-migration.yaml       # EKS/ALB drop-in + migration guide
└── template/
    └── client-site.yaml     # per-client manifest template

k8s/melanin-website/
├── website.yaml             # our own site (preview/staging/production deployments)
└── melanin-ingress.yaml     # our own domain ingress (reference implementation)
```

---

## One-Time Cluster Bootstrap

```bash
# 1. Install nginx-ingress
helm upgrade --install ingress-nginx ingress-nginx \
  --repo https://kubernetes.github.io/ingress-nginx \
  --namespace ingress-nginx --create-namespace \
  --set controller.service.type=LoadBalancer

# 2. Install cert-manager
helm upgrade --install cert-manager cert-manager \
  --repo https://charts.jetstack.io \
  --namespace cert-manager --create-namespace \
  --set crds.enabled=true

# 3. Apply ClusterIssuers
kubectl apply -f k8s/clients/00-bootstrap.yaml

# 4. Get your LoadBalancer IP (point your DNS here)
kubectl get svc -n ingress-nginx ingress-nginx-controller
```

---

## Onboard a New Client

```bash
./k8s/clients/onboard-client.sh \
  --slug acme \
  --domain acme.com \
  --image ghcr.io/melanin-tech/acme-website:latest \
  --type nextjs   # or: static
```

This creates:
- Namespace `client-acme`
- Deployment, Service, Ingress, ConfigMap
- TLS cert auto-provisioned by cert-manager

**DNS instructions** (printed by the script):
```
A record:    acme.com        →  <LoadBalancer IP>
CNAME:       www.acme.com    →  acme.com
```
TLS cert provisions automatically within 1-2 minutes of DNS propagation.

---

## Custom Domain — How It Works

```
Client browser
    │  GET https://acme.com
    ▼
LoadBalancer IP  (your VPS or AWS ALB)
    │  Host: acme.com
    ▼
nginx-ingress  (routes by Host header)
    │
    ▼
Service: website  (namespace: client-acme)
    │
    ▼
Pod: Next.js or nginx (static HTML)
```

cert-manager handles TLS automatically via Let's Encrypt HTTP-01 challenge.

---

## Supported Site Types

| Type | Image base | Notes |
|------|-----------|-------|
| `nextjs` | `node:20-alpine` + Next.js standalone | PORT env var respected |
| `static` | `nginx:alpine` | Serve from `/usr/share/nginx/html` |

---

## Update a Client Site

```bash
# Build and push new image
docker build -t ghcr.io/melanin-tech/acme-website:v2 .
docker push ghcr.io/melanin-tech/acme-website:v2

# Rolling update (zero downtime)
kubectl set image deployment/website website=ghcr.io/melanin-tech/acme-website:v2 \
  -n client-acme
```

---

## Migrate to AWS EKS

See `aws-migration.yaml` for full steps. Summary:

1. Create EKS cluster with `eksctl`
2. Install AWS Load Balancer Controller
3. Push images to ECR
4. In `client-site.yaml`, swap:
   - `ingressClassName: nginx` → `ingressClassName: alb`
   - cert-manager annotations → ALB + ACM annotations
5. Re-run `onboard-client.sh` against the EKS cluster
6. Update DNS A records to ALB hostname

All Namespace, Deployment, Service, and ConfigMap manifests are **identical** between local and AWS — only the Ingress block changes.

---

## Melanin Technologies Own Site

We host ourselves the same way we host clients — `melanin-website` namespace, same ingress pattern.

```bash
kubectl apply -f k8s/melanin-website/melanin-ingress.yaml
```

DNS: point `melanin-tech.com` A record to the LoadBalancer IP.
