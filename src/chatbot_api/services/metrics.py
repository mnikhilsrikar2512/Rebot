from __future__ import annotations

from collections import defaultdict
from threading import Lock


class MetricsStore:
    def __init__(self) -> None:
        self._lock = Lock()
        self.total_requests = 0
        self.total_errors = 0
        self.path_counts: dict[str, int] = defaultdict(int)
        self.status_counts: dict[int, int] = defaultdict(int)
        self.tenant_request_counts: dict[str, int] = defaultdict(int)
        self.tenant_error_counts: dict[str, int] = defaultdict(int)
        self.tenant_latency_ms_total: dict[str, float] = defaultdict(float)
        self.tenant_latency_samples: dict[str, int] = defaultdict(int)

    def record(self, *, path: str, status_code: int, latency_ms: float, tenant_id: str | None) -> None:
        with self._lock:
            self.total_requests += 1
            self.path_counts[path] += 1
            self.status_counts[int(status_code)] += 1
            is_error = int(status_code) >= 400
            if is_error:
                self.total_errors += 1

            if tenant_id:
                self.tenant_request_counts[tenant_id] += 1
                self.tenant_latency_ms_total[tenant_id] += float(latency_ms)
                self.tenant_latency_samples[tenant_id] += 1
                if is_error:
                    self.tenant_error_counts[tenant_id] += 1

    def snapshot(self, tenant_id: str | None = None) -> dict:
        with self._lock:
            base = {
                "total_requests": self.total_requests,
                "total_errors": self.total_errors,
                "path_counts": dict(self.path_counts),
                "status_counts": {str(k): v for k, v in self.status_counts.items()},
            }
            if tenant_id:
                samples = self.tenant_latency_samples.get(tenant_id, 0)
                avg_latency_ms = (
                    round(self.tenant_latency_ms_total.get(tenant_id, 0.0) / samples, 2)
                    if samples > 0
                    else 0.0
                )
                base["tenant"] = {
                    "tenant_id": tenant_id,
                    "requests": self.tenant_request_counts.get(tenant_id, 0),
                    "errors": self.tenant_error_counts.get(tenant_id, 0),
                    "avg_latency_ms": avg_latency_ms,
                }
            return base

    def prometheus_text(self) -> str:
        with self._lock:
            lines: list[str] = []
            lines.append("# HELP chatbot_requests_total Total API requests")
            lines.append("# TYPE chatbot_requests_total counter")
            lines.append(f"chatbot_requests_total {self.total_requests}")

            lines.append("# HELP chatbot_errors_total Total API errors")
            lines.append("# TYPE chatbot_errors_total counter")
            lines.append(f"chatbot_errors_total {self.total_errors}")

            lines.append("# HELP chatbot_requests_by_path_total Requests grouped by path")
            lines.append("# TYPE chatbot_requests_by_path_total counter")
            for path, count in sorted(self.path_counts.items()):
                safe_path = path.replace('"', '\\"')
                lines.append(f'chatbot_requests_by_path_total{{path="{safe_path}"}} {count}')

            lines.append("# HELP chatbot_requests_by_status_total Requests grouped by status code")
            lines.append("# TYPE chatbot_requests_by_status_total counter")
            for status_code, count in sorted(self.status_counts.items()):
                lines.append(f'chatbot_requests_by_status_total{{status="{status_code}"}} {count}')

            lines.append("# HELP chatbot_tenant_requests_total Requests per tenant")
            lines.append("# TYPE chatbot_tenant_requests_total gauge")
            for tenant_id, count in sorted(self.tenant_request_counts.items()):
                safe_tenant = str(tenant_id).replace('"', '\\"')
                lines.append(f'chatbot_tenant_requests_total{{tenant_id="{safe_tenant}"}} {count}')

            lines.append("# HELP chatbot_tenant_errors_total Errors per tenant")
            lines.append("# TYPE chatbot_tenant_errors_total gauge")
            for tenant_id, count in sorted(self.tenant_error_counts.items()):
                safe_tenant = str(tenant_id).replace('"', '\\"')
                lines.append(f'chatbot_tenant_errors_total{{tenant_id="{safe_tenant}"}} {count}')

            lines.append("# HELP chatbot_tenant_avg_latency_ms Average latency per tenant in ms")
            lines.append("# TYPE chatbot_tenant_avg_latency_ms gauge")
            for tenant_id, samples in sorted(self.tenant_latency_samples.items()):
                avg = (self.tenant_latency_ms_total.get(tenant_id, 0.0) / samples) if samples > 0 else 0.0
                safe_tenant = str(tenant_id).replace('"', '\\"')
                lines.append(f'chatbot_tenant_avg_latency_ms{{tenant_id="{safe_tenant}"}} {round(avg, 2)}')

            return "\n".join(lines) + "\n"


metrics_store = MetricsStore()
