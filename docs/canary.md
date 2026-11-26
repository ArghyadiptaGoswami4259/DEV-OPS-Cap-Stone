# Advanced deployment strategy

The production strategy is a progressive Argo Rollouts canary, not a big-bang Deployment update.

1. Argo CD applies a new immutable image digest.
2. A PreSync Job runs `alembic upgrade head` after a TCP database readiness check.
3. Argo Rollouts creates a canary ReplicaSet while the stable ReplicaSet keeps serving.
4. At 20% weight, an `AnalysisTemplate` queries Prometheus three times at one-minute intervals:
   - canary 5xx ratio below 2%;
   - canary p95 latency below 500 ms;
   - canary readiness gauge above zero.
5. If all measurements pass, weight moves to 50%, analysis repeats, and only then moves to 100%.
6. A failed measurement sets the Rollout to `Degraded`, aborts promotion, and traffic returns to
   the stable ReplicaSet. The previous Git digest remains available for explicit rollback.

The shared `taskflow` Service sends traffic to all healthy pods according to replica weights.
Dedicated `taskflow-stable` and `taskflow-canary` Services give Prometheus separate metric jobs for
analysis. This avoids a service-mesh dependency while preserving reproducible canary decisions.

## Controlled drill

```bash
make canary-drill
kubectl get analysisrun -n taskflow-dev
kubectl describe analysisrun -n taskflow-dev
```

The script sets `APP_FAILURE_RATE=1.0` in a non-production ConfigMap, sends synthetic traffic to
`/api/v1/tasks`, and expects the error-rate analysis to fail. Its cleanup trap restores the flag,
removes the load generator and triggers a recovery revision. The application hard-disables failure
injection when `APP_ENVIRONMENT=prod`.
