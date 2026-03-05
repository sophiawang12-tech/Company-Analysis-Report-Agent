---
name: competitive-intel
description: >
  Runs a strategic intelligence analysis for any target company. Produces a structured Markdown report
  based on dimensions defined in `references/strategy_dimensions.md`. Use when the user wants to
  analyse a competitor's strategy, generate a competitive intelligence report, or batch-analyse
  multiple companies. Triggers: "analyse [company]", "competitive intel on [company]", "batch analyse companies.txt".
---

# Company Analysis Report Agent

This skill runs a multi-layer web search strategy against a target company, then uses Claude to synthesize findings into a structured report based on configurable dimensions.

## Configuration

Edit `references/strategy_dimensions.md` to change analysis focus (e.g., Market Positioning, ESG, AI Transformation).

## Run Modes

- **Single company**: User names one company (e.g. "analyse Deutsche Bank")
- **Batch mode**: User provides a `.txt` file path or asks to process multiple companies

## Prerequisites

1. Set `ANTHROPIC_API_KEY` in environment
2. (Optional) Set `NOTION_TOKEN` and install `notion-client notion-markdown` for Notion integration

## Running the Script

**Single company:**
```bash
python scripts/agent.py --company "Company Name" --config references/strategy_dimensions.md --output ./reports
```

**Batch mode:**
```bash
python scripts/agent.py --file companies.txt --config references/strategy_dimensions.md --output ./reports
```

**Optional flags:**
| Flag | Default | Purpose |
|------|---------|---------|
| `--config` | none | Path to dimensions config file |
| `--domain` | auto | Override official website domain |
| `--output` | ./reports | Output directory |
| `--delay` | 15 | Seconds between companies (batch) |
| `--notion-page` | none | Notion page URL/ID to append report |

## Output

- `./reports/<slug>_<date>.md` — Readable report
- `./reports/<slug>_<date>.json` — Structured data

## Report Structure

- Executive Summary
- Sections per configured dimension
- Key Differentiators
- Benchmarks vs Competitors
- Search Metadata
- References (source URLs)
