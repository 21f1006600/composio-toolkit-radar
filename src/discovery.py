import asyncio
import hashlib
import json
import logging
import time

from dataclasses import dataclass, asdict
from datetime import datetime, timezone
from urllib.parse import urlparse, urldefrag

import httpx
from bs4 import BeautifulSoup
from composio import Composio
from playwright.async_api import async_playwright

from src.config import (
    COMPOSIO_API_KEY,
    TAVILY_CONNECTED_ACCOUNT_ID,
    COMPOSIO_USER_ID,
    TAVILY_TOOL_VERSION,
    SEARCH_RESULTS_PER_QUERY,
    MAX_DOCUMENTS_PER_APP,
    SEARCH_CACHE_TTL,
    MAX_DOCUMENT_CHARS,
    CACHE_DIR,
    REQUEST_TIMEOUT,
    MAX_CONCURRENCY,
)

from src.schemas import AppInput


logger = logging.getLogger(__name__)


# ==========================================
# Data Models
# ==========================================

@dataclass
class SearchHit:
    title: str
    url: str
    snippet: str
    score: float
    query: str
    topic: str


@dataclass
class Document:
    url: str
    title: str
    content: str
    official_source: bool
    retrieval_method: str
    retrieved_at: str
    topic: str
    search_score: float


# ==========================================
# Discovery Engine
# ==========================================

class DiscoveryEngine:

    def __init__(self):

        if not COMPOSIO_API_KEY:
            raise RuntimeError(
                "Missing Composio API key"
            )

        if not TAVILY_CONNECTED_ACCOUNT_ID:
            raise RuntimeError(
                "Missing Tavily connected account"
            )

        self.composio = Composio(
            api_key=COMPOSIO_API_KEY
        )

        self.cache_dir = CACHE_DIR / "search"

        self.cache_dir.mkdir(
            parents=True,
            exist_ok=True
        )

        self.semaphore = asyncio.Semaphore(
            MAX_CONCURRENCY
        )

    # ======================================
    # Search Query Generation
    # ======================================

    @staticmethod
    def generate_queries(
        app: AppInput
    ) -> dict[str, str]:

        name = app.name
        website = str(app.website_hint or "")

        if website and "://" not in website:
            website = "https://" + website

        domain = (
            urlparse(website).hostname or ""
        ).removeprefix("www.")

        site_filter = (
            f"site:{domain}" if domain else ""
        )

        return {
            "authentication": (
                f"{site_filter} {name} developer API "
                "authentication OAuth API key"
            ).strip(),

            "access": (
                f"{site_filter} {name} API access "
                "supported editions requirements permissions"
            ).strip(),

            "api_capabilities": (
                f"{site_filter} {name} developer API "
                "reference REST GraphQL endpoints"
            ).strip(),

            "mcp": (
                f"{name} official MCP server "
                "Model Context Protocol documentation GitHub"
            ),
        }

    # ======================================
    # URL Utilities
    # ======================================

    @staticmethod
    def normalize_url(url: str) -> str:

        return urldefrag(url.strip())[0]

    @staticmethod
    def is_official_source(
        url: str,
        website_hint: str
    ) -> bool:

        if not website_hint:
            return False

        hint = str(website_hint)

        if "://" not in hint:
            hint = "https://" + hint

        official_host = (
            urlparse(hint).hostname or ""
        ).lower().removeprefix("www.")

        source_host = (
            urlparse(url).hostname or ""
        ).lower()

        if not official_host:
            return False

        return (
            source_host == official_host
            or source_host.endswith(
                "." + official_host
            )
        )

    # ======================================
    # Search Cache
    # ======================================

    def _cache_path(self, query: str):

        cache_key = (
            f"discovery-v2:"
            f"{TAVILY_TOOL_VERSION}:"
            f"{SEARCH_RESULTS_PER_QUERY}:"
            f"{query}"
        )

        key = hashlib.sha256(
            cache_key.encode("utf-8")
        ).hexdigest()

        return self.cache_dir / f"{key}.json"

    def _read_cache(self, query: str):

        path = self._cache_path(query)

        if not path.exists():
            return None

        try:
            age = time.time() - path.stat().st_mtime

            if age > SEARCH_CACHE_TTL:
                return None

            data = json.loads(
                path.read_text(encoding="utf-8")
            )

            if not isinstance(data, list):
                return None

            return data

        except (OSError, json.JSONDecodeError):
            return None

    def _write_cache(self, query: str, data):

        path = self._cache_path(query)

        path.write_text(
            json.dumps(
                data,
                ensure_ascii=False,
                indent=2
            ),
            encoding="utf-8"
        )

    # ======================================
    # Composio-Powered Search
    # ======================================

    async def search(
        self,
        query: str,
        topic: str
    ) -> list[SearchHit]:

        cached = self._read_cache(query)

        if cached is not None:

            logger.info(
                "Cache hit: %s",
                query
            )

            results = cached

        else:

            logger.info(
                "Searching: %s",
                query
            )

            arguments = {
                "query": query,
                "max_results": (
                    SEARCH_RESULTS_PER_QUERY
                ),
                "search_depth": "basic",
                "include_answer": False,
            }

            # Restrict searches to vendor domains.
            for word in query.split():

                if word.startswith("site:"):

                    domain = word.removeprefix(
                        "site:"
                    )

                    if domain:
                        arguments[
                            "include_domains"
                        ] = [domain]

                    break

            async with self.semaphore:

                response = await asyncio.to_thread(
                    self.composio.tools.execute,
                    slug="TAVILY_SEARCH",
                    user_id=COMPOSIO_USER_ID,
                    connected_account_id=(
                        TAVILY_CONNECTED_ACCOUNT_ID
                    ),
                    version=TAVILY_TOOL_VERSION,
                    arguments=arguments,
                )

            if not response.get("successful"):

                raise RuntimeError(
                    response.get("error")
                    or "Search execution failed"
                )

            results = (
                response.get("data") or {}
            ).get("results")

            if not isinstance(results, list):

                raise RuntimeError(
                    "Unexpected search response format"
                )

            self._write_cache(
                query,
                results
            )

        hits = []

        for item in results:

            url = self.normalize_url(
                item.get("url") or ""
            )

            parsed_url = urlparse(url)

            if parsed_url.scheme not in (
                "http",
                "https"
            ):
                continue

            if not parsed_url.hostname:
                continue

            hits.append(
                SearchHit(
                    title=item.get("title") or "",
                    url=url,
                    snippet=item.get("content") or "",
                    score=float(
                        item.get("score") or 0
                    ),
                    query=query,
                    topic=topic,
                )
            )

        return hits

    # ======================================
    # HTML Content Extraction
    # ======================================

    @staticmethod
    def extract_content(html: str) -> str:

        soup = BeautifulSoup(
            html,
            "html.parser"
        )

        for tag in soup.select(
            "script, style, nav, footer, "
            "header, noscript"
        ):
            tag.decompose()

        main = (
            soup.find("main")
            or soup.find("article")
            or soup.body
            or soup
        )

        return main.get_text(
            separator="\n",
            strip=True
        )

    # ======================================
    # Playwright Browser Fallback
    # ======================================

    async def fetch_with_browser(
        self,
        url: str
    ) -> tuple[str, str]:

        async with self.semaphore:

            async with async_playwright() as playwright:

                browser = await playwright.chromium.launch(
                    headless=True
                )

                try:

                    page = await browser.new_page()

                    response = await page.goto(
                        url,
                        wait_until="domcontentloaded",
                        timeout=30000
                    )

                    if response and response.status >= 400:

                        raise RuntimeError(
                            f"HTTP {response.status}"
                        )

                    await page.wait_for_timeout(2000)

                    html = await page.content()

                    content = self.extract_content(
                        html
                    )

                    return content, page.url

                finally:

                    await browser.close()

    # ======================================
    # Document Retrieval
    # ======================================

    async def fetch_document(
        self,
        client: httpx.AsyncClient,
        hit: SearchHit,
        app: AppInput
    ) -> Document:

        content = ""
        final_url = hit.url
        method = "httpx"

        try:

            async with self.semaphore:

                response = await client.get(
                    hit.url
                )

                response.raise_for_status()

            content = self.extract_content(
                response.text
            )

            final_url = str(response.url)

        except httpx.HTTPError as exc:

            logger.warning(
                "HTTP retrieval failed for %s: %s",
                hit.url,
                type(exc).__name__
            )

        # Use browser fallback for thin content.
        if len(content) < 500:

            logger.info(
                "Using browser fallback: %s",
                hit.url
            )

            try:

                browser_content, browser_url = (
                    await self.fetch_with_browser(
                        hit.url
                    )
                )

                # Keep whichever extraction is richer.
                if len(browser_content) > len(content):

                    content = browser_content
                    final_url = browser_url
                    method = "playwright"

            except Exception as exc:

                logger.warning(
                    "Browser retrieval failed for %s: %s",
                    hit.url,
                    type(exc).__name__
                )

        if len(content) < 200:

            raise ValueError(
                "Insufficient document content"
            )

        return Document(
            url=final_url,
            title=hit.title,
            content=content[:MAX_DOCUMENT_CHARS],
            official_source=self.is_official_source(
                final_url,
                str(app.website_hint or "")
            ),
            retrieval_method=method,
            retrieved_at=datetime.now(
                timezone.utc
            ).isoformat(),
            topic=hit.topic,
            search_score=hit.score,
        )

    # ======================================
    # Discovery Pipeline Orchestration
    # ======================================

    async def discover(
        self,
        app: AppInput
    ) -> dict:

        logger.info(
            "Starting discovery for %s",
            app.name
        )

        queries = self.generate_queries(app)

        errors = []

        # Execute targeted searches concurrently.
        search_results = await asyncio.gather(
            *[
                self.search(query, topic)
                for topic, query in queries.items()
            ],
            return_exceptions=True
        )

        hits = []

        for topic, result in zip(
            queries,
            search_results
        ):

            if isinstance(result, Exception):

                errors.append(
                    f"Search {topic}: "
                    f"{type(result).__name__}"
                )

                logger.warning(
                    "Search failed for %s: %s",
                    topic,
                    type(result).__name__
                )

            else:

                hits.extend(result)

        # Prioritize official sources, then relevance.
        hits.sort(
            key=lambda hit: (
                self.is_official_source(
                    hit.url,
                    str(app.website_hint or "")
                ),
                not (urlparse(hit.url).hostname or "").startswith("community."),
                hit.score,
            ),
            reverse=True
        )

        # Select documents across all research topics.
        selected = []
        seen = set()

        for topic in queries:

            count = 0

            for hit in hits:

                if hit.topic != topic:
                    continue

                if hit.url in seen:
                    continue

                selected.append(hit)
                seen.add(hit.url)

                count += 1

                if count >= 2:
                    break

        selected = selected[
            :MAX_DOCUMENTS_PER_APP
        ]

        # Retrieve selected documents.
        async with httpx.AsyncClient(
            timeout=REQUEST_TIMEOUT,
            follow_redirects=True,
            headers={
                "User-Agent": "ToolkitRadar/1.0"
            },
        ) as client:

            fetched = await asyncio.gather(
                *[
                    self.fetch_document(
                        client,
                        hit,
                        app
                    )
                    for hit in selected
                ],
                return_exceptions=True
            )

        documents = []
        fetched_urls = set()

        for hit, result in zip(
            selected,
            fetched
        ):

            if isinstance(result, Exception):

                errors.append(
                    f"Fetch {hit.url}: "
                    f"{type(result).__name__}"
                )

            else:

                # Deduplicate redirected URLs.
                normalized_url = self.normalize_url(
                    result.url
                )

                if normalized_url in fetched_urls:
                    continue

                fetched_urls.add(normalized_url)

                documents.append(result)

        # Replace failed retrievals using remaining search hits, without new searches.
        if len(documents) < MAX_DOCUMENTS_PER_APP:
            attempted = {hit.url for hit in selected}
            remaining = [hit for hit in hits if hit.url not in attempted]
            async with httpx.AsyncClient(timeout=REQUEST_TIMEOUT, follow_redirects=True,
                                         headers={"User-Agent": "ToolkitRadar/1.0"}) as client:
                for hit in remaining:
                    if len(documents) >= MAX_DOCUMENTS_PER_APP:
                        break
                    if hit.url in attempted:
                        continue
                    attempted.add(hit.url)
                    try:
                        doc = await self.fetch_document(client, hit, app)
                        url = self.normalize_url(doc.url)
                        if url not in fetched_urls:
                            documents.append(doc)
                            fetched_urls.add(url)
                    except Exception as exc:
                        errors.append(f"Replacement fetch {hit.url}: {type(exc).__name__}")

        logger.info(
            "Discovery completed for %s: "
            "%d hits, %d documents, %d errors",
            app.name,
            len(hits),
            len(documents),
            len(errors)
        )

        return {
            "app": app.name,
            "queries": queries,
            "search_hits": [
                asdict(hit)
                for hit in hits
            ],
            "documents": [
                asdict(doc)
                for doc in documents
            ],
            "errors": errors,
        }