from datetime import datetime, timezone

from src.pipeline import ResearchPipeline

from src.schemas import (
    AppInput,
    ResearchResult,
    Claim,
    Evidence,
    AuthMethod,
    AccessType,
    APIType,
    APIBreadth,
    MCPStatus,
    Buildability,
    VerificationStatus,
)


def make_app():

    return AppInput(
        id=1,
        name="Example CRM",
        category="CRM",
        website_hint="https://example.com",
    )


def make_claim(
    field,
    statement,
    status=VerificationStatus.SUPPORTED,
):

    return Claim(
        field=field,
        statement=statement,
        verification_status=status,
        evidence=[
            Evidence(
                source_url="https://example.com/docs",
                excerpt="Example API documentation.",
                source_title="API Documentation",
                retrieved_at=datetime.now(timezone.utc),
                official_source=True,
            )
        ],
    )


def make_verdict(
    field,
    status="supported",
    unsupported_values=None,
):

    return {
        "field": field,
        "status": status,
        "reason": "Test verdict",
        "unsupported_values": unsupported_values or [],
        "corrective_query": "",
    }


def test_unsupported_access_is_removed():

    result = ResearchResult(
        app=make_app(),
        access_types=[AccessType.PAID],
        claims=[
            make_claim(
                "access_types",
                "Paid access is required.",
                VerificationStatus.INSUFFICIENT,
            )
        ],
    )

    feedback = {
        "field_verdicts": [
            make_verdict(
                "access_types",
                "insufficient_evidence",
                ["paid"],
            )
        ]
    }

    clean = ResearchPipeline.sanitize_result(
        result,
        feedback,
    )

    assert clean.access_types == [
        AccessType.UNKNOWN
    ]


def test_supported_authentication_is_preserved():

    result = ResearchResult(
        app=make_app(),
        auth_methods=[AuthMethod.OAUTH2],
        claims=[
            make_claim(
                "auth_methods",
                "OAuth2 is supported.",
            )
        ],
    )

    feedback = {
        "field_verdicts": [
            make_verdict("auth_methods")
        ]
    }

    clean = ResearchPipeline.sanitize_result(
        result,
        feedback,
    )

    assert clean.auth_methods == [
        AuthMethod.OAUTH2
    ]


def test_unsupported_list_value_is_removed():

    result = ResearchResult(
        app=make_app(),
        auth_methods=[
            AuthMethod.OAUTH2,
            AuthMethod.API_KEY,
        ],
        claims=[
            make_claim(
                "auth_methods",
                "OAuth2 is supported.",
            ),
            make_claim(
                "auth_methods",
                "API keys are supported.",
                VerificationStatus.INSUFFICIENT,
            ),
        ],
    )

    feedback = {
        "field_verdicts": [
            make_verdict(
                "auth_methods",
                "insufficient_evidence",
                ["api_key"],
            )
        ]
    }

    clean = ResearchPipeline.sanitize_result(
        result,
        feedback,
    )

    assert clean.auth_methods == [
        AuthMethod.OAUTH2
    ]


def test_missing_field_verdict_fails_closed():

    result = ResearchResult(
        app=make_app(),
        api_types=[APIType.REST],
        claims=[
            make_claim(
                "api_types",
                "REST API is supported.",
            )
        ],
    )

    clean = ResearchPipeline.sanitize_result(
        result,
        {"field_verdicts": []},
    )

    assert clean.api_types == [
        APIType.UNKNOWN
    ]


def test_mcp_without_url_is_unknown():

    result = ResearchResult(
        app=make_app(),
        mcp_status=MCPStatus.OFFICIAL,
        mcp_url=None,
        claims=[
            make_claim(
                "mcp_status",
                "Official MCP server exists.",
            )
        ],
    )

    feedback = {
        "field_verdicts": [
            make_verdict("mcp_status")
        ]
    }

    clean = ResearchPipeline.sanitize_result(
        result,
        feedback,
    )

    assert clean.mcp_status == MCPStatus.UNKNOWN
    assert clean.mcp_url is None


def test_ready_requires_verified_prerequisites():

    result = ResearchResult(
        app=make_app(),
        buildability=Buildability.READY,
        claims=[
            make_claim(
                "buildability",
                "Integration is ready.",
            )
        ],
    )

    feedback = {
        "field_verdicts": [
            make_verdict("buildability")
        ]
    }

    clean = ResearchPipeline.sanitize_result(
        result,
        feedback,
    )

    assert clean.buildability == Buildability.UNKNOWN


def test_attempt_ranking_prioritizes_fields():

    first = {
        "field_verdicts": [
            make_verdict("description")
        ],
        "support_rate": 0.95,
        "contradicted_claims": 0,
    }

    second = {
        "field_verdicts": [
            make_verdict("description"),
            make_verdict("auth_methods"),
        ],
        "support_rate": 0.85,
        "contradicted_claims": 0,
    }

    assert (
        ResearchPipeline.attempt_score(second)
        > ResearchPipeline.attempt_score(first)
    )


def test_sanitization_preserves_original_record():

    result = ResearchResult(
        app=make_app(),
        auth_methods=[AuthMethod.API_KEY],
    )

    clean = ResearchPipeline.sanitize_result(
        result,
        {"field_verdicts": []},
    )

    assert result.auth_methods == [
        AuthMethod.API_KEY
    ]

    assert clean.auth_methods == [
        AuthMethod.UNKNOWN
    ]