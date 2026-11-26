# Rollback runbook

## Automatic canary rollback

1. Confirm `kubectl get rollout taskflow -n <namespace>` is `Degraded`.
2. Inspect `kubectl get analysisrun -n <namespace>` and the failed metric.
3. Verify stable ReplicaSet pods are Ready and `taskflow_ready` is 1 in Grafana.
4. Preserve the failed digest, Git SHA, AnalysisRun YAML and alert timestamps as evidence.

No manual action is normally needed: Argo Rollouts aborts and scales the canary down.

## Explicit rollback

```bash
bash infra/scripts/rollback.sh taskflow-prod
git revert <promotion-commit>          # restore the previous digest in Git
git push origin <current-branch>
argocd app sync taskflow-prod
kubectl argo rollouts status taskflow -n taskflow-prod
```

If the release included a schema migration, do not revert the image alone. Check the Alembic
revision, restore the compatible database snapshot/PITR point if needed, and then promote the
compatible image digest. For a bad Terraform change, restore the previous versioned state or
revert the Terraform commit and apply a reviewed plan.
