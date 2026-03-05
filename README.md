# Company Analysis Report Agent

A Claude-based skill that runs strategic intelligence analysis on any target company. It uses a multi-layer web search strategy to gather public information, synthesizes findings into structured Markdown/JSON reports, and optionally **pushes the results directly to a Notion database or page**.

## Purpose

- **Competitive intelligence**: Analyze competitors' strategy, positioning, and public disclosures
- **Configurable dimensions**: Define your own analysis focus (e.g., Market Positioning, Supply Chain, Digital Transformation, Financial Health)
- **Source traceability**: All findings include references with URLs
- **Batch mode**: Process multiple companies in one run
- **Notion Integration**: Automatically append generated reports to your Notion workspace for easy sharing and archiving

## Requirements

- Python 3.9+
- [Anthropic API key](https://console.anthropic.com/) (required)
- [Notion API token](https://www.notion.so/my-integrations) (optional, for pushing reports to Notion)

## Installation

```bash
# Clone the repository
git clone https://github.com/sophiawang12-tech/Company-Analysis-Report-Agent.git
cd Company-Analysis-Report-Agent

# Create virtual environment (recommended)
python3 -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Set API key (required)
export ANTHROPIC_API_KEY=sk-ant-...
```

## Configuration

### 1. Analysis Dimensions

Edit `references/strategy_dimensions.md` to define what the agent analyzes. Each dimension has a title and description that drives the search queries.

Example:

```markdown
## 1. Market Positioning
Description: Analyze the company's target market, core customers, and brand positioning.

## 2. Digital Transformation
Description: Evaluate AI, cloud, and automation investments.
```

### 2. Companies List (Batch Mode)

Create a `companies.txt` file with one company name per line:

```
Deutsche Bank
HSBC
JPMorgan Chase
# Barclays  <- lines starting with # are skipped
```

## Usage

### Single Company

```bash
python scripts/agent.py \
  --company "Deutsche Bank" \
  --config references/strategy_dimensions.md \
  --output ./reports
```

### Batch Mode

```bash
python scripts/agent.py \
  --file companies.txt \
  --config references/strategy_dimensions.md \
  --output ./reports \
  --delay 15
```

## Notion Integration

This agent can automatically append the generated analysis reports to a specific Notion page. This is useful for building a centralized competitive intelligence database.

### Setup

1. **Get your Notion API Token**:
   - Go to [My Integrations](https://www.notion.so/my-integrations).
   - Create a new "Internal Integration".
   - Copy the "Internal Integration Secret" (starts with `secret_...`).

2. **Connect the Integration to your Page**:
   - Open the Notion page where you want reports to appear.
   - Click the `...` menu in the top right corner.
   - Click **Connections** (or "Add connections").
   - Search for and select your new integration.
   - *Note: If you skip this step, the agent will fail with a 404 or 403 error.*

### Usage

Set your token as an environment variable and pass the page URL (or ID) to the script:

```bash
# 1. Set the token
export NOTION_TOKEN=secret_your_token_here...

# 2. Run with --notion-page
python scripts/agent.py \
  --company "Even Realities" \
  --config references/strategy_dimensions.md \
  --notion-page "https://www.notion.so/your-workspace/Competitor-Analysis-1234567890abcdef"
```

The report will be appended to the bottom of the page, formatted with proper headings, bullet points, and links.

## Output

Reports are saved to `./reports/` (or your `--output` path):

- `<company_slug>_<date>.md` — Human-readable report with Executive Summary, dimension sections, key differentiators, benchmarks, and references
- `<company_slug>_<date>.json` — Structured data for further processing

## Deployment as Claude Skill

1. Copy this repository into your Claude/Cursor skills folder, e.g.:
   ```
   .claude/skills/competitive-intel/
   ├── SKILL.md
   ├── scripts/
   │   └── agent.py
   └── references/
       ├── strategy_dimensions.md
       └── search-strategy.md
   ```

2. Ensure `ANTHROPIC_API_KEY` is set in the environment where the agent runs.

3. Invoke via natural language: *"analyse Deutsche Bank"* or *"batch analyse companies.txt"*.

## How It Works

1. **Layer 1 — Signal Search**: Uses the first dimension to gauge information density.
2. **Layer 2 — Dimension Search**: For each dimension, generates 3 targeted search queries via LLM and executes web search.
3. **Layer 3 — Source-Targeted Search**: Searches the company's official site, executive interviews, and investor materials.
4. **Synthesis**: Claude Opus produces a structured JSON report, rendered to Markdown with a source bibliography.

## Rate Limits

- Each company uses ~30,000–50,000 input tokens.
- Default: 20s sleep between API calls, 15s between companies in batch.
- If you hit rate limits, increase `--delay` to 30 or 60.

## Troubleshooting

| Issue | Solution |
|-------|----------|
| `ANTHROPIC_API_KEY not set` | `export ANTHROPIC_API_KEY=sk-ant-...` |
| Rate limit exceeded | Increase `--delay` |
| JSON parse error | Re-run; occasional Opus output issues |
| Notion 403 | Add your integration to the page via Connections |

## License

MIT
