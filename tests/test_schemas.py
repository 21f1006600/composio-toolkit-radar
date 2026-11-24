import pytest
from pydantic import ValidationError

from src.schemas import (
    AppInput,
    ResearchResult,
    AuthMethod,
    Buildability,
    Claim,
    VerificationStatus,
)

from main import load_apps


@pytest.fixture
def sample_app():
    return AppInput(
        id=1,
        name="Salesforce",
        category="CRM and Sales",
        website_hint="salesforce.com",
    )


def test_dataset():
    apps = load_apps()
    assert len(apps) == 100
    assert len({app.id for app in apps}) == 100
    assert len({app.category for app in apps}) == 10


def test_default_research_result(sample_app):
    result = ResearchResult(app=sample_app)

    assert result.auth_methods == [AuthMethod.UNKNOWN]
    assert result.buildability == Buildability.UNKNOWN


def test_invalid_auth_method(sample_app):
    with pytest.raises(ValidationError):
        ResearchResult(
            app=sample_app,
            auth_methods=["invalid_auth"],
        )


def test_claim_starts_unverified():
    claim = Claim(
        field="auth_methods",
        statement="The application supports OAuth2",
    )

    assert claim.verification_status == VerificationStatus.PENDING


def test_invalid_app_id():
    with pytest.raises(ValidationError):
        AppInput(
            id=0,
            name="Example",
            category="CRM",
            website_hint="example.com",
        )
