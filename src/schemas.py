from datetime import datetime, timezone
from enum import Enum

from pydantic import BaseModel, Field, HttpUrl


class AuthMethod(str, Enum):
    OAUTH2 = "oauth2"
    API_KEY = "api_key"
    BASIC = "basic"
    BEARER_TOKEN = "bearer_token"
    OTHER = "other"
    NONE = "none"
    UNKNOWN = "unknown"


class AccessType(str, Enum):
    FREE = "free"
    TRIAL = "trial"
    PAID = "paid"
    ADMIN_APPROVAL = "admin_approval"
    PARTNER_GATED = "partner_gated"
    UNKNOWN = "unknown"


class APIType(str, Enum):
    REST = "rest"
    GRAPHQL = "graphql"
    RPC = "rpc"
    SDK = "sdk"
    CLI = "cli"
    OTHER = "other"
    UNKNOWN = "unknown"


class APIBreadth(str, Enum):
    BROAD = "broad"
    MODERATE = "moderate"
    LIMITED = "limited"
    UNKNOWN = "unknown"


class MCPStatus(str, Enum):
    OFFICIAL = "official"
    COMMUNITY = "community"
    NOT_FOUND = "not_found"
    UNKNOWN = "unknown"


class Buildability(str, Enum):
    READY = "ready"
    CONDITIONAL = "conditional"
    BLOCKED = "blocked"
    UNKNOWN = "unknown"


class VerificationStatus(str, Enum):
    PENDING = "pending"
    SUPPORTED = "supported"
    CONTRADICTED = "contradicted"
    INSUFFICIENT = "insufficient_evidence"


class AppInput(BaseModel):
    id: int = Field(ge=1)
    name: str = Field(min_length=1)
    category: str
    website_hint: str


class Evidence(BaseModel):
    source_url: HttpUrl
    excerpt: str = Field(min_length=1)
    source_title: str = ""
    retrieved_at: datetime
    official_source: bool = False


class Claim(BaseModel):
    field: str
    statement: str
    evidence: list[Evidence] = Field(default_factory=list)

    verification_status: VerificationStatus = (
        VerificationStatus.PENDING
    )

    verification_reason: str = ""


class ResearchResult(BaseModel):
    app: AppInput

    description: str = ""

    auth_methods: list[AuthMethod] = Field(
        default_factory=lambda: [AuthMethod.UNKNOWN]
    )

    access_types: list[AccessType] = Field(
        default_factory=lambda: [AccessType.UNKNOWN]
    )

    access_details: str = ""

    api_types: list[APIType] = Field(
        default_factory=lambda: [APIType.UNKNOWN]
    )

    api_breadth: APIBreadth = APIBreadth.UNKNOWN

    example_operations: list[str] = Field(
        default_factory=list
    )

    mcp_status: MCPStatus = MCPStatus.UNKNOWN
    mcp_url: HttpUrl | None = None

    buildability: Buildability = Buildability.UNKNOWN

    blockers: list[str] = Field(default_factory=list)
    verdict_reason: str = ""

    claims: list[Claim] = Field(default_factory=list)

    research_attempt: int = Field(default=1, ge=1)

    research_errors: list[str] = Field(
        default_factory=list
    )

    researched_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc)
    )
