# Observability guide

## Metrics

The application exposes Prometheus text format at `/metrics`. A ServiceMonitor scrapes the stable
and canary Services every 15 seconds. The Grafana sidecar loads
`platform/observability/dashboard-configmap.yaml`, and the local Compose stack loads
`grafana-dashboard-taskflow.json` through provisioning.

PrometheusRule alerts cover 5xx ratio, p95 latency, readiness and repeated pod restarts. The Argo
Rollouts AnalysisTemplate reuses the same metric names with narrower canary thresholds.

## Logs

`app/logging.py` writes compact JSON to stdout; no secret values or request bodies are logged.
Promtail's CRI and JSON stages promote `level`, `trace_id`, `route` and `status` to structured
fields. See `platform/observability/log-queries.md` for ready-to-use LogQL.

## Traces and correlation

`app/tracing.py` accepts a valid W3C `traceparent`, generates a new span and returns
`X-Request-ID`, `X-Trace-ID` and `traceparent` headers. Use the trace ID to correlate:

1. user-facing response headers;
2. `{app="taskflow"} | json | trace_id="..."` in Loki;
3. request metrics in Grafana;
4. Argo Rollouts analysis runs during a promotion.

## Alert routing

Alertmanager groups by alert name and environment, repeats every four hours, suppresses warning
alerts when a matching critical alert is active, and sends resolved transitions to a webhook.
Replace the webhook URL with an approved incident-management endpoint before production use.
