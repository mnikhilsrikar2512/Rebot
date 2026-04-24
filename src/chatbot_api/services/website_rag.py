from __future__ import annotations

import re
from collections import Counter, deque
from dataclasses import dataclass
from math import sqrt
from urllib.parse import urljoin, urlparse

import httpx


@dataclass
class WebsiteEvidence:
    domain_type: str | None
    current_page: str | None
    snippets: list[str]
    weak_context: bool


@dataclass
class WebsiteChunk:
    tenant_id: str
    url: str
    text: str
    vector: Counter[str]


class WebsiteRAGService:
    def __init__(self) -> None:
        self._chunks_by_tenant: dict[str, list[WebsiteChunk]] = {}

    def clear_tenant(self, tenant_id: str) -> None:
        self._chunks_by_tenant.pop(tenant_id, None)

    def stats(self, tenant_id: str) -> dict[str, int]:
        chunks = self._chunks_by_tenant.get(tenant_id, [])
        urls = {chunk.url for chunk in chunks}
        return {"pages_indexed": len(urls), "chunks_indexed": len(chunks)}

    def _tokenize(self, text: str) -> Counter[str]:
        tokens = re.findall(r"[a-zA-Z]{2,}", (text or "").lower())
        return Counter(tokens)

    def _cosine(self, a: Counter[str], b: Counter[str]) -> float:
        if not a or not b:
            return 0.0
        keys = set(a.keys()) & set(b.keys())
        dot = sum(a[k] * b[k] for k in keys)
        norm_a = sqrt(sum(v * v for v in a.values()))
        norm_b = sqrt(sum(v * v for v in b.values()))
        if norm_a == 0 or norm_b == 0:
            return 0.0
        return dot / (norm_a * norm_b)

    def _extract_text(self, html: str) -> str:
        no_script = re.sub(r"<script[\s\S]*?</script>", " ", html, flags=re.IGNORECASE)
        no_style = re.sub(r"<style[\s\S]*?</style>", " ", no_script, flags=re.IGNORECASE)
        text = re.sub(r"<[^>]+>", " ", no_style)
        text = re.sub(r"\s+", " ", text)
        return text.strip()

    def _extract_links(self, html: str, base_url: str) -> list[str]:
        links = re.findall(r'href=["\']([^"\']+)["\']', html, flags=re.IGNORECASE)
        normalized: list[str] = []
        parsed_base = urlparse(base_url)
        for link in links:
            if link.startswith("#"):
                continue
            url = urljoin(base_url, link)
            parsed = urlparse(url)
            if parsed.scheme not in {"http", "https"}:
                continue
            if parsed.hostname != parsed_base.hostname:
                continue
            normalized.append(url)
        return normalized

    def _normalize_allowed_hosts(self, allowed_domains: list[str], website_url: str) -> set[str]:
        hosts: set[str] = set()
        for raw in allowed_domains:
            item = (raw or "").strip().lower()
            if not item:
                continue
            if "://" in item:
                parsed = urlparse(item)
                if parsed.hostname:
                    hosts.add(parsed.hostname.lower())
            else:
                hosts.add(item)
        parsed_start = urlparse(website_url)
        if parsed_start.hostname:
            hosts.add(parsed_start.hostname.lower())
        return hosts

    def _host_allowed(self, host: str, allowed_hosts: set[str]) -> bool:
        host = (host or "").lower()
        if not host:
            return False
        for allowed in allowed_hosts:
            if host == allowed or host.endswith(f".{allowed}"):
                return True
        return False

    def _chunk_text(self, text: str, size: int = 700, overlap: int = 80) -> list[str]:
        content = (text or "").strip()
        if not content:
            return []
        chunks: list[str] = []
        start = 0
        while start < len(content):
            end = min(len(content), start + size)
            chunks.append(content[start:end])
            if end >= len(content):
                break
            start = max(0, end - overlap)
        return chunks

    def _fetch_html(self, url: str, timeout: float = 8.0) -> str:
        with httpx.Client(timeout=timeout, follow_redirects=True) as client:
            response = client.get(url)
            response.raise_for_status()
            return response.text

    def seed_runtime_context(self, tenant_id: str, page_url: str | None, rag_context: str | None) -> None:
        text = (rag_context or "").strip()
        if not text:
            return
        url = (page_url or "runtime://context").strip() or "runtime://context"
        chunks = self._chunks_by_tenant.setdefault(tenant_id, [])
        chunks.append(
            WebsiteChunk(
                tenant_id=tenant_id,
                url=url,
                text=text[:1800],
                vector=self._tokenize(text),
            )
        )

    def ingest_site(
        self,
        tenant_id: str,
        website_url: str,
        allowed_domains: list[str] | None = None,
        max_pages: int = 8,
        max_depth: int = 1,
    ) -> dict[str, int]:
        start = website_url.strip()
        if not start:
            return {"pages_indexed": 0, "chunks_indexed": 0}

        allowed_hosts = self._normalize_allowed_hosts(allowed_domains or [], start)
        start_host = (urlparse(start).hostname or "").lower()
        if not self._host_allowed(start_host, allowed_hosts):
            return {"pages_indexed": 0, "chunks_indexed": 0}

        visited: set[str] = set()
        queue: deque[tuple[str, int]] = deque([(start, 0)])
        chunks: list[WebsiteChunk] = []

        while queue and len(visited) < max_pages:
            url, depth = queue.popleft()
            if url in visited:
                continue
            host = (urlparse(url).hostname or "").lower()
            if not self._host_allowed(host, allowed_hosts):
                continue
            visited.add(url)
            try:
                html = self._fetch_html(url)
            except Exception:
                continue

            text = self._extract_text(html)
            for part in self._chunk_text(text):
                chunks.append(
                    WebsiteChunk(
                        tenant_id=tenant_id,
                        url=url,
                        text=part,
                        vector=self._tokenize(part),
                    )
                )

            if depth < max_depth:
                for link in self._extract_links(html, url):
                    if link not in visited:
                        queue.append((link, depth + 1))

        if chunks:
            self._chunks_by_tenant[tenant_id] = chunks
        return self.stats(tenant_id)

    def search(self, tenant_id: str, query: str, top_k: int = 3) -> list[str]:
        chunks = self._chunks_by_tenant.get(tenant_id, [])
        if not chunks:
            return []
        query_vec = self._tokenize(query)
        scored = [(self._cosine(query_vec, chunk.vector), chunk.text) for chunk in chunks]
        scored.sort(key=lambda item: item[0], reverse=True)
        return [text for score, text in scored[:top_k] if score > 0]


website_rag_service = WebsiteRAGService()


def collect_website_evidence(
    tenant_id: str,
    query: str,
    domain_type: str | None,
    current_page: str | None,
    rag_context: str | None,
) -> WebsiteEvidence:
    website_rag_service.seed_runtime_context(tenant_id, current_page, rag_context)
    snippets = website_rag_service.search(tenant_id=tenant_id, query=query, top_k=3)
    if not snippets and rag_context:
        text = rag_context.strip()
        if text:
            snippets = [text[:1200]]

    return WebsiteEvidence(
        domain_type=(domain_type or "").strip().lower() or None,
        current_page=(current_page or "").strip() or None,
        snippets=snippets,
        weak_context=not bool(snippets),
    )
