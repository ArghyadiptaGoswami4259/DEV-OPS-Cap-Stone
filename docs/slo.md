# Service-level objectives

| SLI | PromQL | SLO | Canary threshold | Alert |
|---|---|---:|---:|---|
| Availability | `1 - 5xx requests / total requests` | 99.5% over 30 days | canary 5xx ratio < 2% | > 5% for 5 min |
| Latency | p95 of `taskflow_http_request_duration_seconds_bucket` | 95% of requests < 500 ms | canary p95 < 500 ms | > 500 ms for 10 min |
| Readiness | `min(taskflow_ready)` | 1 on all serving replicas | > 0 for three measurements | < 1 for 2 min |
| Durability | successful daily Velero/RDS backups | 1 validated backup per day | n/a | backup job failure |
| Recovery | measured restore time | RPO <= 60 min, RTO <= 30 min | n/a | DR drill overdue |

## Error budget

A 99.5% availability SLO over 30 days permits about 3h 36m of equivalent total downtime. A
critical alert consumes budget and requires an incident record. Canary analysis uses stricter
thresholds than the steady-state SLO so a bad revision is rejected before it consumes the full
error budget.

## Instrumentation

- `taskflow_http_requests_total{method,route,status}` - bounded route labels from FastAPI templates.
- `taskflow_http_request_duration_seconds_bucket{method,route}` - p50/p95/p99 histograms.
- `taskflow_http_requests_in_flight` - saturation.
- `taskflow_ready` and `taskflow_build_info` - dependency health and release identity.
- Structured JSON logs include `trace_id`, `request_id`, `route`, `status` and `duration_ms`.
