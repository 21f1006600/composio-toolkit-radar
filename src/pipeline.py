import asyncio
import json
import logging
import time

import httpx

from src.config import (
    MAX_RESEARCH_ATTEMPTS,
    MAX_CORRECTIVE_QUERIES,
    MAX_CORRECTIVE_DOCUMENTS,
    MAX_MERGED_DOCUMENTS,
    REQUEST_TIMEOUT,
)

from src.schemas import (
    AppInput,
    ResearchResult,
    AuthMethod,
    AccessType,
    APIType,
    APIBreadth,
    MCPStatus,
    Buildability,
    VerificationStatus,
)

from src.discovery import DiscoveryEngine
from src.researcher import ResearchAgent
from src.verifier import VerificationAgent

from dataclasses import asdict


logger = logging.getLogger(__name__)


class ResearchPipeline:

    def __init__(self):

        self.discovery = DiscoveryEngine()
        self.researcher = ResearchAgent()
        self.verifier = VerificationAgent()

    # ======================================
    # Corrective Document Discovery
    # ======================================

    async def corrective_discovery(
        self,
        app: AppInput,
        queries: list[str],
        previous_discovery: dict,
    ) -> dict:

        queries = list(dict.fromkeys(
            query.strip()
            for query in queries
            if query.strip()
        ))[:MAX_CORRECTIVE_QUERIES]

        logger.info(
            "Corrective discovery for %s: %d queries",
            app.name,
            len(queries),
        )

        existing_documents = previous_discovery.get(
            "documents", []
        )

        existing_urls = {
            document["url"]
            for document in existing_documents
        }

        errors = list(
            previous_discovery.get("errors", [])
        )

        search_results = await asyncio.gather(
            *[
                self.discovery.search(
                    query=query,
                    topic="corrective",
                )
                for query in queries
            ],
            return_exceptions=True,
        )

        new_hits = []

        for query, response in zip(
            queries, search_results
        ):

            if isinstance(response, Exception):

                errors.append(
                    f"Corrective search failed: "
                    f"{query}: {type(response).__name__}"
                )

                continue

            new_hits.extend(response)

        # Prefer official documentation.
        new_hits.sort(
            key=lambda hit: (
                self.discovery.is_official_source(
                    hit.url,
                    app.website_hint,
                ),
                hit.score,
            ),
            reverse=True,
        )

        selected_hits = []
        seen_urls = set(existing_urls)

        # First take the strongest candidate from each corrective query.
        first = []
        for query in queries:
            match = next((h for h in new_hits if h.query == query and h.url not in existing_urls), None)
            if match is not None:
                first.append(match)
        for hit in first + new_hits:

            url = self.discovery.normalize_url(
                hit.url
            )

            if url in seen_urls:
                continue

            seen_urls.add(url)
            selected_hits.append(hit)

            if (
                len(selected_hits)
                >= MAX_CORRECTIVE_DOCUMENTS
            ):
                break

        async with httpx.AsyncClient(
            timeout=REQUEST_TIMEOUT,
            follow_redirects=True,
            headers={
                "User-Agent": "ToolkitRadar/1.0"
            },
        ) as client:

            fetched = await asyncio.gather(
                *[
                    self.discovery.fetch_document(
                        client,
                        hit,
                        app,
                    )
                    for hit in selected_hits
                ],
                return_exceptions=True,
            )

        new_documents = []

        for hit, document in zip(
            selected_hits, fetched
        ):

            if isinstance(document, Exception):

                errors.append(
                    f"Corrective fetch failed: "
                    f"{hit.url}: "
                    f"{type(document).__name__}"
                )

                continue

            if document is None:
                continue

            new_documents.append(
                asdict(document)
            )

        # Prioritize newly discovered evidence.
        merged_documents = []
        merged_urls = set()

        for document in (
            new_documents + existing_documents
        ):

            url = document["url"]

            if url in merged_urls:
                continue

            merged_urls.add(url)
            merged_documents.append(document)

            if (
                len(merged_documents)
                >= MAX_MERGED_DOCUMENTS
            ):
                break

        logger.info(
            "Corrective discovery retrieved "
            "%d new documents; %d total retained",
            len(new_documents),
            len(merged_documents),
        )

        return {
            "app": app.name,
            "queries": previous_discovery.get(
                "queries", {}
            ),
            "corrective_queries": queries,
            "search_hits": [
                *previous_discovery.get(
                    "search_hits", []
                ),
                *[
                    asdict(hit)
                    for hit in new_hits
                ],
            ],
            "documents": merged_documents,
            "errors": errors,
        }

    # ======================================
    # Corrective Research Feedback
    # ======================================

    @staticmethod
    def format_feedback(
        feedback: dict
    ) -> str:

        instructions = (
            "The previous research contained "
            "unsupported or incomplete claims. "
            "Reassess all fields using the current "
            "documents. Do not repeat unsupported "
            "claims without new supporting evidence. "
            "Treat prior verifier decisions as "
            "feedback, not unquestionable facts. "
            "Exclude adjacent vendor products. "
            "Use unknown when evidence remains "
            "insufficient."
        )

        return json.dumps(
            {
                "instructions": instructions,
                "failed_claims": feedback.get(
                    "failed_claims", []
                ),
                "failed_fields": feedback.get(
                    "failed_fields", []
                ),
            },
            ensure_ascii=False,
        )

    # ======================================
    # Final Field Sanitization
    # ======================================

    @staticmethod
    def sanitize_result(
        result: ResearchResult,
        feedback: dict,
    ) -> ResearchResult:

        clean = result.model_copy(deep=True)

        defaults = {
            "description": "",
            "auth_methods": [AuthMethod.UNKNOWN],
            "access_types": [AccessType.UNKNOWN],
            "access_details": "",
            "api_types": [APIType.UNKNOWN],
            "api_breadth": APIBreadth.UNKNOWN,
            "example_operations": [],
            "mcp_status": MCPStatus.UNKNOWN,
            "mcp_url": None,
            "buildability": Buildability.UNKNOWN,
            "blockers": [],
            "verdict_reason": "",
        }

        field_verdicts = {
            verdict["field"]: verdict
            for verdict in feedback.get(
                "field_verdicts", []
            )
        }

        supported_fields = {
            claim.field
            for claim in clean.claims
            if (
                claim.verification_status
                == VerificationStatus.SUPPORTED
                and claim.evidence
            )
        }

        failed_claim_fields = {
            claim.field
            for claim in clean.claims
            if (
                claim.verification_status
                != VerificationStatus.SUPPORTED
            )
        }

        for field, default in defaults.items():

            current = getattr(clean, field)

            if current == default:
                continue

            verdict = field_verdicts.get(field)

            # Fail closed if field verification
            # is missing or evidence is insufficient.
            if (
                not verdict
                or field not in supported_fields
            ):

                setattr(clean, field, default)

                clean.research_errors.append(
                    f"Final sanitization: {field} "
                    f"reset due to missing support."
                )

                continue

            if (
                verdict["status"] == "supported"
                and not verdict.get(
                    "unsupported_values", []
                )
                and field not in failed_claim_fields
            ):
                continue

            unsupported = {
                str(value).strip().casefold()
                for value in verdict.get(
                    "unsupported_values", []
                )
            }

            # Remove individual list values only
            # when the verifier explicitly identifies
            # the unsupported values.
            if (
                isinstance(current, list)
                and unsupported
                and verdict["status"] != "supported"
            ):

                retained = [
                    value
                    for value in current
                    if str(
                        getattr(value, "value", value)
                    ).strip().casefold()
                    not in unsupported
                ]

                removed_count = (
                    len(current) - len(retained)
                )

                # Conservative fallback when exact
                # value matching cannot be established.
                if removed_count != len(unsupported):

                    setattr(clean, field, default)

                else:

                    setattr(
                        clean,
                        field,
                        retained or default,
                    )

            else:

                setattr(clean, field, default)

            clean.research_errors.append(
                f"Final sanitization applied: {field}"
            )

        # Enforce cross-field consistency.
        if clean.mcp_status in {
            MCPStatus.UNKNOWN,
            MCPStatus.NOT_FOUND,
        }:

            clean.mcp_url = None

        if (
            clean.mcp_status in {
                MCPStatus.OFFICIAL,
                MCPStatus.COMMUNITY,
            }
            and clean.mcp_url is None
        ):

            clean.mcp_status = MCPStatus.UNKNOWN

        if clean.buildability == Buildability.READY:

            if (
                clean.auth_methods
                == [AuthMethod.UNKNOWN]
                or clean.api_types
                == [APIType.UNKNOWN]
                or clean.access_types
                == [AccessType.UNKNOWN]
                or clean.api_breadth
                == APIBreadth.UNKNOWN
                or not clean.example_operations
                or clean.blockers
            ):

                clean.buildability = (
                    Buildability.UNKNOWN
                )

        if (
            clean.buildability
            == Buildability.UNKNOWN
        ):

            clean.verdict_reason = ""

        # Rebuild the verdict from sanitized information.
        # Never reuse unsupported pricing or access claims.

        verdict_templates = {
            Buildability.READY:
                "Documentation indicates that integration is feasible.",
            Buildability.CONDITIONAL:
                "Integration is feasible subject to documented requirements.",
            Buildability.BLOCKED:
                "Documented restrictions prevent practical integration.",
            Buildability.UNKNOWN:
                "",
        }

        if (
            clean.buildability in {
                Buildability.CONDITIONAL,
                Buildability.BLOCKED,
            }
            and not clean.blockers
        ):
            clean.buildability = Buildability.UNKNOWN

        clean.verdict_reason = verdict_templates[
            clean.buildability
        ]

        if clean.verdict_reason and clean.blockers:
            clean.verdict_reason += (
                " Requirements or restrictions: "
                + "; ".join(clean.blockers)
            )

        # Retain rejected claims in the attempt history,
        # not in the final published research record.

        clean.claims = [
            claim
            for claim in clean.claims
            if (
                claim.verification_status
                == VerificationStatus.SUPPORTED
                and claim.evidence
                and claim.field in defaults
                and getattr(clean, claim.field)
                != defaults[claim.field]
                and claim.field != "verdict_reason"
                and claim.field not in failed_claim_fields
            )
        ]

        return clean

    @staticmethod
    def quality_summary(result: ResearchResult) -> dict:
        fields = ("auth_methods", "api_types", "example_operations", "access_types",
                  "api_breadth", "mcp_status", "description", "buildability")
        unresolved = []
        for field in fields:
            value = getattr(result, field)
            values = value if isinstance(value, list) else [value]
            if not any(v and getattr(v, "value", v) != "unknown" for v in values):
                unresolved.append(field)
        return {"critical_fields": len(fields), "resolved": len(fields)-len(unresolved),
                "unresolved": unresolved, "submission_ready": not unresolved}

    # ======================================
    # Attempt Ranking
    # ======================================

    @staticmethod
    def attempt_score(
        feedback: dict,
        result: ResearchResult | None = None,
    ) -> tuple:

        supported_fields = 0

        for verdict in feedback.get(
            "field_verdicts", []
        ):

            if verdict["status"] != "supported":
                continue

            if verdict.get("unsupported_values"):
                continue

            if result is not None:

                value = getattr(
                    result,
                    verdict["field"],
                    None,
                )

                if value is None or value == "":
                    continue

                if isinstance(value, list):

                    known_values = [
                        item for item in value
                        if getattr(item, "value", item)
                        != "unknown"
                    ]

                    if not known_values:
                        continue

                elif getattr(value, "value", value) == "unknown":
                    continue

            supported_fields += 1

        return (
            supported_fields,
            feedback.get("support_rate", 0),
            -feedback.get("contradicted_claims", 0),
        )

    # ======================================
    # Main Pipeline
    # ======================================

    async def run(
        self,
        app: AppInput,
        initial_discovery: dict | None = None,
        initial_result: ResearchResult | None = None,
        initial_feedback: dict | None = None,
        max_attempts: int = MAX_RESEARCH_ATTEMPTS,
    ) -> dict:

        started = time.perf_counter()

        if max_attempts < 1:
            raise ValueError(
                "max_attempts must be at least 1"
            )

        if (
            initial_result is not None
            and initial_result.app.id != app.id
        ):

            raise ValueError(
                "Initial research app ID mismatch"
            )

        discovery_result = (
            initial_discovery
            if initial_discovery is not None
            else await self.discovery.discover(app)
        )

        history = []

        best_result = None
        best_feedback = None
        best_score = None

        feedback = {}
        pipeline_errors = []

        for attempt in range(
            1, max_attempts + 1
        ):

            logger.info(
                "Pipeline: %s attempt %d/%d",
                app.name,
                attempt,
                max_attempts,
            )

            try:

                if (
                    attempt == 1
                    and initial_result is not None
                    and initial_feedback is not None
                ):

                    verified = initial_result
                    feedback = initial_feedback

                else:

                    if attempt > 1:

                        discovery_result = (
                            await self.corrective_discovery(
                                app,
                                feedback.get(
                                    "corrective_queries",
                                    [],
                                ),
                                discovery_result,
                            )
                        )

                    researched = (
                        await self.researcher.research(
                            app=app,
                            discovery_result=(
                                discovery_result
                            ),
                            attempt=attempt,
                            feedback=(
                                self.format_feedback(
                                    feedback
                                )
                                if feedback else ""
                            ),
                        )
                    )

                    if not researched.claims:

                        raise RuntimeError(
                            "Research returned no claims: "
                            + "; ".join(
                                researched.research_errors
                            )
                        )

                    verified, feedback = (
                        await self.verifier.verify(
                            researched
                        )
                    )

                candidate = self.sanitize_result(
                    verified,
                    feedback,
                )

                quality = self.quality_summary(candidate)
                feedback["quality"] = quality
                priority_queries = {
                    "auth_methods": "official API authentication credentials tokens",
                    "api_types": "official API reference REST GraphQL RPC",
                    "example_operations": "official API endpoints create list update resources",
                    "access_types": "official API access pricing plans developer account",
                    "api_breadth": "official API reference resources CRUD operations",
                    "mcp_status": "official MCP server Model Context Protocol",
                    "description": "official developer API overview",
                    "buildability": "official API integration requirements restrictions",
                }
                extra = [f"{app.name} {priority_queries[f]}" for f in quality["unresolved"]]
                feedback["corrective_queries"] = list(dict.fromkeys(extra + feedback.get("corrective_queries", [])))
                feedback["needs_research"] = bool(extra or feedback.get("needs_research"))
                score = self.attempt_score(
                    feedback,
                    candidate,
                )

                history.append({
                    "attempt": attempt,
                    "documents": len(
                        discovery_result.get(
                            "documents", []
                        )
                    ),
                    "score": list(score),
                    "research": verified.model_dump(
                        mode="json"
                    ),
                    "verification": feedback,
                })

                if (
                    best_score is None
                    or score > best_score
                ):

                    best_score = score

                    best_result = verified.model_copy(
                        deep=True
                    )

                    best_feedback = feedback

                if not feedback.get(
                    "needs_research", True
                ):

                    logger.info(
                        "Verification completed "
                        "without further research"
                    )

                    break

            except Exception as exc:

                message = (
                    f"Attempt {attempt} failed: "
                    f"{type(exc).__name__}: {exc}"
                )

                logger.error(message)
                pipeline_errors.append(message)

                history.append({
                    "attempt": attempt,
                    "error": message,
                })

        if best_result is None:

            final_result = ResearchResult(
                app=app,
                research_errors=pipeline_errors,
            )

        else:

            final_result = self.sanitize_result(
                best_result,
                best_feedback,
            )

            final_result.research_errors.extend(
                pipeline_errors
            )

        return {
            "app": app.name,
            "attempts": len(history),
            "selected_attempt": (
                best_result.research_attempt
                if best_result else None
            ),
            "final_result": final_result.model_dump(
                mode="json"
            ),
            "final_verification": best_feedback,
            "history": history,
            "pipeline_errors": pipeline_errors,
            "execution_time": round(
                time.perf_counter() - started,
                2,
            ),
        }