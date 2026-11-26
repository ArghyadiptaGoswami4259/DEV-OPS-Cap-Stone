# Incident-response runbook

1. **Classify:** record severity, environment, release digest, first-seen time and user impact.
2. **Stabilize:** if a rollout is in progress, run `bash infra/scripts/rollback.sh <namespace>`.
3. **Correlate:** use `X-Trace-ID` from the failing response to query Loki, then inspect Grafana
   request rate, 5xx ratio, p95 latency, in-flight requests and readiness.
4. **Contain:** scale down a faulty non-stable ReplicaSet, rotate any exposed credential and
   revoke a compromised GitHub token or release signature trust.
5. **Recover:** promote the last known-good immutable digest through the approved workflow.
6. **Validate:** `/healthz`, `/readyz`, `/metrics`, CRUD smoke test, Argo CD Healthy/Synced and
   Alertmanager resolved notifications.
7. **Learn:** create a post-incident note with timeline, error-budget impact, root cause, detection
   gap and preventive CI/policy changes.

Useful commands:

```bash
kubectl get rollout,analysisrun,pods -n <namespace>
kubectl describe rollout taskflow -n <namespace>
kubectl logs -l app=taskflow -n <namespace> --tail=200
argocd app get taskflow-prod
velero backup get
```
