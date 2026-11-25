# Toolkit Radar

**An evidence-driven AI research engine for evaluating application integration opportunities at scale.**

Built for the Composio AI Product Ops Intern take-home assignment.

## Overview

Evaluating applications for integration requires more than determining whether an API exists. Authentication mechanisms, access restrictions, API capabilities, MCP availability and implementation feasibility all influence integration decisions.

Toolkit Radar automates this research process across 100 applications spanning 10 categories and transforms the findings into an interactive product intelligence dashboard.

## Key Features

- Automated web research through the Composio SDK and Tavily.
- Structured research using Gemini.
- Source-linked evidence for research claims.
- Separate semantic verification stage.
- Corrective research driven by verification feedback.
- Conservative handling of unsupported classifications.
- Resumable batch execution with SQLite persistence.
- Interactive application explorer and opportunity analysis.
- Research quality benchmarks and an AI-assisted accuracy audit.

## Architecture

```text
Application Registry
        |
        v
Discovery Engine
(Composio + Tavily)
        |
        v
Document Retrieval
(HTTPX + Playwright)
        |
        v
Research Agent
(Gemini + Pydantic)
        |
        v
Verification Agent
        |
        +---- Unsupported findings
        |           |
        |           v
        |     Corrective Discovery
        |           |
        |           v
        |     Research Again
        |
        v
Result Sanitization
        |
        v
SQLite Persistence
        |
        v
Analytics Engine
        |
        v
Interactive HTML Dashboard
```

## Research Methodology

### 1. Discovery

The discovery engine generates targeted search queries covering authentication, API access, API capabilities and MCP availability.

Search execution is performed through Composio's Tavily integration. Official documentation is prioritized using domain matching, relevance scoring and topic coverage.

### 2. Document Retrieval

HTTPX retrieves source documents, with Playwright providing a browser-based fallback when necessary. Extracted content is cleaned and divided into identifiable passages.

### 3. Structured Research

Gemini analyzes the retrieved passages and produces structured research records validated using Pydantic schemas.

Each application is evaluated across:

- Product description
- Authentication methods
- API access requirements
- API protocols
- API breadth
- Representative operations
- MCP availability and ownership
- Integration feasibility
- Implementation blockers

### 4. Verification and Corrective Research

A separate LLM invocation evaluates research claims against their cited evidence.

Unsupported findings generate targeted corrective search queries. The research pipeline retrieves additional documentation and reassesses the application.

The strongest evaluated attempt is selected, and unsupported classifications are removed or marked unknown before publication.

### 5. Persistence and Analytics

SQLite stores application records, research results, verification feedback and attempt history.

The analytics engine aggregates research findings into authentication patterns, API distributions, MCP coverage, category-level insights and integration opportunities.

## Research Quality Evaluation

The pipeline was developed through iterative benchmarking rather than relying exclusively on its initial output.

A paired benchmark covering Slack, GitHub and Stripe produced the following field completeness results:

| Application | Baseline | V4 |
|---|---:|---:|
| Slack | 33.33% | 83.33% |
| GitHub | 66.67% | 50.00% |
| Stripe | 16.67% | 83.33% |
| Average | 38.89% | 72.22% |

Overall field completeness improved by 33.33 percentage points, approximately 85.7% relative to the baseline.

Completeness is not equivalent to factual accuracy. A separate AI-assisted evidence audit evaluates selected classifications and documents remaining errors and unresolved findings.

The benchmark sample is small and should not be interpreted as representative of all 100 applications.

The project also includes 22 automated regression tests covering schemas, verification, pipeline behavior and persistence.

## Technology Stack

| Component | Technology |
|---|---|
| Research orchestration | Python, asyncio |
| Search integration | Composio SDK, Tavily |
| Language model | Gemini 3.1 Flash Lite |
| Schema validation | Pydantic |
| Document retrieval | HTTPX, BeautifulSoup, Playwright |
| Persistence | SQLite |
| Report generation | Jinja2 |
| Frontend | HTML, CSS, JavaScript |
| Testing | Pytest |

## Local Setup

### Prerequisites

- Python 3.12
- Composio API key
- Gemini API key
- Tavily API key and configured Composio connected account

### Installation

```bash
git clone https://github.com/21f1006600/composio-toolkit-radar
cd toolkit-radar

python -m venv .venv
```

Activate the virtual environment.

Windows:

```powershell
.venv\Scripts\Activate.ps1
```

Linux or macOS:

```bash
source .venv/bin/activate
```

Install dependencies:

```bash
pip install -r requirements.txt
python -m playwright install chromium
```

### Environment Configuration

Create a `.env` file using `.env.example` as a reference.

```env
COMPOSIO_API_KEY=
GEMINI_API_KEY=
TAVILY_API_KEY=
TAVILY_AUTH_CONFIG_ID=
TAVILY_CONNECTED_ACCOUNT_ID=
```

Configure the Tavily integration in Composio and ensure the connected account is active and authorized for the configured user.

Never commit API credentials.

## Running the Research Pipeline

Validate the application registry:

```bash
python main.py validate
```

Initialize the database:

```bash
python main.py init
```

Run a small research batch:

```bash
python main.py run --limit 3 --concurrency 2 --attempts 2
```

Run the complete research batch:

```bash
python main.py run --concurrency 2 --attempts 2 --retry-failed
```

Check progress:

```bash
python main.py status
```

Completed applications are skipped during subsequent runs, allowing interrupted research to resume.

## Generate the Dashboard

```bash
python -m src.analytics
python -m src.report
```

Serve the generated dashboard locally:

```bash
python -m http.server 8000 --directory docs
```

Open `http://localhost:8000` in a browser.

The generated report is a standalone HTML application and does not require a running backend.

## Running Tests

```bash
python -m pytest -q
```

The regression suite does not require live research API calls.

## Repository Structure

```text
toolkit-radar/
├── data/
│   ├── apps.json
│   ├── manual_accuracy.json
│   └── quality_benchmark_v*.json
├── src/
│   ├── config.py
│   ├── schemas.py
│   ├── discovery.py
│   ├── researcher.py
│   ├── verifier.py
│   ├── pipeline.py
│   ├── storage.py
│   ├── batch.py
│   ├── analytics.py
│   └── report.py
├── templates/
│   └── index.html
├── tests/
├── docs/
│   └── index.html
├── main.py
├── requirements.txt
├── .env.example
└── README.md
```

## Engineering Decisions

**Evidence passage identifiers:** Replaced model-generated quotations with references to extracted passages to reduce quotation mismatches.

**Separate verification stage:** Introduced semantic evaluation independently of the initial research invocation.

**Corrective discovery:** Converted verification failures into actionable search queries rather than repeatedly prompting the model with unchanged context.

**SQLite persistence:** Enabled resumable execution without introducing unnecessary database infrastructure.

**Controlled concurrency and retries:** Balanced research throughput against external API rate limits and transient service failures.

**Static dashboard:** Eliminated hosting and backend dependencies for the published case study.

## Limitations

- Research quality depends on accessible and current public documentation.
- Official-domain detection is heuristic and can miss legitimate vendor-owned domains.
- Research and verification use the same model family, allowing correlated errors.
- Product subscription pricing does not necessarily establish API-specific access requirements.
- Integration feasibility is documentation-based, not proof of successful authenticated API execution.
- Unknown MCP status does not establish that an MCP server does not exist.
- External API quotas and transient failures can affect throughput.
- The evaluation sample is limited, and automated verification does not replace independent human review.

## Future Improvements

- Deterministic evidence mapping for individual classification values.
- Cross-attempt merging of verified findings.
- Independent verification using a different model family.
- Authenticated API capability testing.
- Expanded human-reviewed evaluation datasets.

## Acknowledgements

Built using Composio, Tavily and Google Gemini for the Composio AI Product Ops take-home assignment.