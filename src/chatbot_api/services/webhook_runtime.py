from __future__ import annotations

import hashlib
import hmac
import json
import queue
import threading
import time
import urllib.request
from dataclasses import dataclass
from typing import Any


@dataclass
class WebhookSubscription:
    event: str
    callback_url: str
    secret: str


@dataclass
class WebhookJob:
    tenant_id: str
    event: str
    payload: dict[str, Any]
    callback_url: str
    secret: str
    attempt: int = 0


class WebhookRuntime:
    def __init__(self) -> None:
        self._subs: dict[str, list[WebhookSubscription]] = {}
        self._dead_letters: list[dict[str, Any]] = []
        self._queue: queue.Queue[WebhookJob] = queue.Queue()
        self._lock = threading.Lock()
        self._worker_started = False
        self.max_attempts = 3

    def register(self, tenant_id: str, event: str, callback_url: str, secret: str) -> None:
        with self._lock:
            self._subs.setdefault(tenant_id, []).append(
                WebhookSubscription(event=event, callback_url=callback_url, secret=secret)
            )
        self._ensure_worker()

    def list_dead_letters(self, tenant_id: str) -> list[dict[str, Any]]:
        with self._lock:
            return [item for item in self._dead_letters if item.get("tenant_id") == tenant_id]

    def dispatch(self, tenant_id: str, event: str, payload: dict[str, Any]) -> None:
        with self._lock:
            subs = list(self._subs.get(tenant_id, []))

        for sub in subs:
            if sub.event != event and sub.event != "*":
                continue
            self._queue.put(
                WebhookJob(
                    tenant_id=tenant_id,
                    event=event,
                    payload=payload,
                    callback_url=sub.callback_url,
                    secret=sub.secret,
                )
            )
        self._ensure_worker()

    def _ensure_worker(self) -> None:
        if self._worker_started:
            return
        self._worker_started = True
        thread = threading.Thread(target=self._worker_loop, name="webhook-worker", daemon=True)
        thread.start()

    def _worker_loop(self) -> None:
        while True:
            job = self._queue.get()
            try:
                self._deliver(job)
            finally:
                self._queue.task_done()

    def _deliver(self, job: WebhookJob) -> None:
        body = json.dumps(job.payload).encode("utf-8")
        signature = hmac.new(job.secret.encode("utf-8"), body, hashlib.sha256).hexdigest()
        req = urllib.request.Request(
            url=job.callback_url,
            data=body,
            method="POST",
            headers={
                "Content-Type": "application/json",
                "X-Webhook-Event": job.event,
                "X-Webhook-Signature": f"sha256={signature}",
            },
        )

        try:
            with urllib.request.urlopen(req, timeout=5) as resp:
                status_code = int(getattr(resp, "status", 200))
                if status_code >= 400:
                    raise RuntimeError(f"Webhook returned status {status_code}")
        except Exception as exc:
            if job.attempt + 1 >= self.max_attempts:
                with self._lock:
                    self._dead_letters.append(
                        {
                            "tenant_id": job.tenant_id,
                            "event": job.event,
                            "callback_url": job.callback_url,
                            "payload": job.payload,
                            "error": str(exc),
                            "attempts": job.attempt + 1,
                            "failed_at": time.time(),
                        }
                    )
                return

            backoff_seconds = 0.5 * (2 ** job.attempt)
            time.sleep(backoff_seconds)
            self._queue.put(
                WebhookJob(
                    tenant_id=job.tenant_id,
                    event=job.event,
                    payload=job.payload,
                    callback_url=job.callback_url,
                    secret=job.secret,
                    attempt=job.attempt + 1,
                )
            )


webhook_runtime = WebhookRuntime()
