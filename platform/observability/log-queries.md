# LogQL reference

All application logs are single-line JSON written to stdout. Promtail parses `level`, `trace_id`,
`route`, `status` and `duration_ms` into labels or structured fields.

```logql
# All TaskFlow logs
{app="taskflow"}

# Errors for one release environment
{app="taskflow", environment="prod"} | json | level=~"ERROR|CRITICAL"

# Follow one request across application and ingress logs
{app=~"taskflow|nginx"} | json | trace_id="REPLACE_WITH_TRACE_ID"

# Slow API calls (duration is in milliseconds)
{app="taskflow"} | json | duration_ms > 500

# 5xx requests by route
sum by (route) (
  count_over_time({app="taskflow"} | json | status=~"5.." [5m])
)

# Failed readiness checks
{app="taskflow"} | json | message="readiness.database_failed"
```

Use `trace_id` from the `X-Trace-ID` response header to correlate a user-visible failure with
Prometheus metrics, Loki logs and the Argo Rollouts analysis run.
