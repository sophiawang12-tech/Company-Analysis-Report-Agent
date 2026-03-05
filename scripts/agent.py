"""
Company Analysis Report Agent
============================
Strategic intelligence analysis for any target company.

Usage:
  Single company: python scripts/agent.py --company "Company Name" --config references/strategy_dimensions.md
  Batch mode:     python scripts/agent.py --file companies.txt --config references/strategy_dimensions.md
"""

from __future__ import annotations
import os
import json
import time
import re
import datetime
import argparse
from typing import Any

import anthropic

try:
    from notion_client import Client as NotionClient
    from notion_markdown import convert as md_to_notion_blocks
    HAS_NOTION = True
except ImportError:
    NotionClient = None  # type: ignore[assignment,misc]
    md_to_notion_blocks = None  # type: ignore[assignment]
    HAS_NOTION = False

# Configuration (API keys from environment only)
API_KEY = os.environ.get("ANTHROPIC_API_KEY", "")
NOTION_TOKEN = os.environ.get("NOTION_TOKEN", "")
SEARCH_MODEL = "claude-sonnet-4-5"
SYNTHESIS_MODEL = "claude-opus-4-5"
SLEEP = 20.0
MAX_RETRIES = 10
RETRY_BASE_WAIT = 60


def load_dimensions(config_path):
    """Load analysis dimensions from a markdown configuration file."""
    dimensions = []
    current_dim = None

    if not config_path or not os.path.exists(config_path):
        return [
            {"key": "market_positioning", "label": "1. Market Positioning", "desc": "Target market, core customers, brand positioning."},
            {"key": "supply_chain", "label": "2. Supply Chain Resilience", "desc": "Supply chain structure, supplier relationships, disruption strategies."},
            {"key": "digital_transformation", "label": "3. Digital Transformation", "desc": "Digital tools, cloud, data analytics, AI and automation."},
            {"key": "financial_health", "label": "4. Financial Health", "desc": "Revenue, profitability, cash flow, key investments."},
        ]

    with open(config_path, "r", encoding="utf-8") as f:
        lines = f.readlines()

    for line in lines:
        line = line.strip()
        if line.startswith("## "):
            if current_dim:
                dimensions.append(current_dim)
            label = line[3:].strip()
            key = re.sub(r"[^a-z0-9]", "_", label.lower()).strip("_")
            current_dim = {"key": key, "label": label, "desc": ""}
        elif line.startswith("Description:") and current_dim:
            current_dim["desc"] = line.replace("Description:", "").strip()

    if current_dim:
        dimensions.append(current_dim)

    return dimensions


def generate_search_queries(client, company, dimension):
    """Generate tailored search queries for a specific dimension using LLM."""
    prompt = f"""You are an expert search query generator.

Target: {company}
Topic: {dimension['label']}
Definition: {dimension['desc']}

Generate 3 highly effective Google search queries to find specific information about this topic for this company.
Focus on finding facts, names, dates, and metrics.
Return ONLY the 3 queries, one per line, no numbering or bullets."""

    try:
        resp = api_call_with_retry(lambda: client.messages.create(
            model=SEARCH_MODEL,
            max_tokens=150,
            messages=[{"role": "user", "content": prompt}],
        ))
        content = getattr(resp.content[0], "text", "")
        queries = [q.strip() for q in content.split("\n") if q.strip()]
        return queries[:3]
    except Exception as e:
        print(f"   Query generation failed for {dimension['key']}: {e}")
        return [f"{company} {dimension['label']} {dimension['desc'][:50]}"]


KNOWN_DOMAINS = {
    "deutsche bank": "db.com",
    "jpmorgan": "jpmorganchase.com",
    "jp morgan": "jpmorganchase.com",
    "hsbc": "hsbc.com",
    "barclays": "barclays.com",
    "goldman sachs": "goldmansachs.com",
    "morgan stanley": "morganstanley.com",
    "citigroup": "citi.com",
    "citi": "citi.com",
    "ubs": "ubs.com",
}


def api_call_with_retry(call_fn):
    for attempt in range(1, MAX_RETRIES + 1):
        try:
            return call_fn()
        except anthropic.RateLimitError:
            if attempt == MAX_RETRIES:
                raise
            wait = RETRY_BASE_WAIT * attempt
            print(f"   Rate limit hit, waiting {wait}s (attempt {attempt}/{MAX_RETRIES})...")
            time.sleep(wait)
    raise RuntimeError("Exceeded max retries")


def build_layer3(company, domain):
    return [
        f"site:{domain} strategy strategic plan vision 2025",
        f"{company} CEO interview strategic outlook 2025",
        f"{company} annual report investor presentation strategy 2024",
    ]


def run_search(client, queries, context=""):
    query_list = "\n".join(f"- {q}" for q in queries)
    prompt = f"""You are a strategic intelligence researcher.

Execute each search query. For each, return 3 bullet points maximum.
Be concise. Focus only on: program names, tools, key metrics, people names, vendor names.
{f"Context: {context}" if context else ""}

Queries:
{query_list}

Format:
### [query]
- key finding 1
- key finding 2
- key finding 3
"""
    resp = api_call_with_retry(lambda: client.messages.create(
        model=SEARCH_MODEL,
        max_tokens=1500,
        tools=[{"type": "web_search_20250305", "name": "web_search"}],
        messages=[{"role": "user", "content": prompt}],
    ))

    text_parts = []
    sources = []

    for block in resp.content:
        if hasattr(block, "text"):
            text_parts.append(block.text)
        if getattr(block, "type", "") == "web_search_tool_result":
            try:
                content = block.content
                if isinstance(content, list):
                    for item in content:
                        url = getattr(item, "url", "")
                        title = getattr(item, "title", "")
                        if url and not any(s["url"] == url for s in sources):
                            sources.append({"url": url, "title": title, "query": queries[0] if queries else ""})
            except Exception:
                pass

    return "\n\n".join(text_parts), sources


class CompetitiveIntelAgent:
    def __init__(self, company, config_path=None, domain=""):
        self.company = company
        self.domain = domain or self._resolve_domain(company)
        self.client = anthropic.Anthropic(api_key=API_KEY)
        self.layer1_text = ""
        self.density = {}

        self.dimensions_config = load_dimensions(config_path)
        self.dimensions_keys = [d["key"] for d in self.dimensions_config]
        self.findings = {d["key"]: "" for d in self.dimensions_config}
        self.all_sources = []

        print(f"\n{'='*58}")
        print(f"  Strategic Analysis Agent")
        print(f"  Target : {company}")
        print(f"  Domain : {self.domain}")
        print(f"  Config : {config_path or 'Default'}")
        print(f"{'='*58}\n")

    def _resolve_domain(self, company):
        key = company.lower()
        for pattern, dom in KNOWN_DOMAINS.items():
            if pattern in key:
                return dom
        slug = re.sub(r"[^a-z0-9]", "", key.split()[0])
        return f"{slug}.com"

    def _add_sources(self, new_sources):
        for s in new_sources:
            url = s.get("url", "").strip()
            if url and not any(x["url"] == url for x in self.all_sources):
                self.all_sources.append(s)

    def run_layer1(self):
        print("Layer 1: Signal Search...")
        first_dim = self.dimensions_config[0]
        queries = generate_search_queries(self.client, self.company, first_dim)

        text, sources = run_search(self.client, queries)
        self.layer1_text = text
        self._add_sources(sources)
        print(f"   {len(text):,} chars, {len(sources)} sources")
        time.sleep(SLEEP)

        self.density = {d["key"]: 1 for d in self.dimensions_config}
        time.sleep(SLEEP)

        for d in self.dimensions_config:
            print(f"   {d['label']}")

    def run_layer2(self):
        print("\nLayer 2: Dimension Search...")
        for dim in self.dimensions_config:
            print(f"   {dim['label']}")
            queries = generate_search_queries(self.client, self.company, dim)
            text, sources = run_search(self.client, queries, context=f"Dimension: {dim['label']}")
            self.findings[dim["key"]] += text
            self._add_sources(sources)
            time.sleep(SLEEP)
        print("   Layer 2 complete")

    def run_layer3(self):
        print("\nLayer 3: Source-Targeted Search...")
        text, sources = run_search(self.client, build_layer3(self.company, self.domain))
        for dim in self.dimensions_config:
            self.findings[dim["key"]] += f"\n\n[Source-targeted]\n{text}"
        self._add_sources(sources)
        print("   Layer 3 complete")
        time.sleep(SLEEP)

    def synthesize(self):
        print("\nSynthesis: Generating structured report (Claude Opus)...")
        findings_trimmed = {d: t[:1200] for d, t in self.findings.items()}

        dim_structure = {}
        for d in self.dimensions_config:
            dim_structure[d["key"]] = {
                "summary": "2-3 sentences",
                "key_facts": ["fact 1", "fact 2"],
                "information_gap": "what is missing",
                "strategic_implication": "implication for competitor",
            }
            if "champion" in d["key"].lower():
                dim_structure[d["key"]]["champion_names"] = ["Name1", "Name2"]

        prompt = f"""You are a senior strategic intelligence analyst.

Target company: {self.company}

## Research Findings (per dimension):
{json.dumps(findings_trimmed, ensure_ascii=False, indent=2)}

## Task:
Produce a strategic intelligence report based on the provided dimensions.
For each dimension provide:
- summary: 2-3 sentences, key takeaway
- key_facts: 4-6 bullet points with specific names, numbers, dates, tools
- information_gap: what is NOT publicly available
- strategic_implication: 1-2 sentences analysis

Ratings:
- overall_transparency_level: high | medium | low
- overall_maturity: pioneer | advanced | developing | early

Return ONLY valid JSON, no markdown fences:
{{
  "company": "{self.company}",
  "report_date": "{datetime.date.today().isoformat()}",
  "overall_transparency_level": "...",
  "overall_maturity": "...",
  "executive_summary": "4 sentences overview",
  "dimensions": {json.dumps(dim_structure)},
  "key_differentiators": ["3-5 distinctive things"],
  "benchmarks_vs_competitors": ["3-5 actionable comparisons"],
  "search_metadata": {{
    "density_map": {json.dumps(self.density)},
    "information_richness_overall": "high|medium|low"
  }}
}}"""

        resp = api_call_with_retry(lambda: self.client.messages.create(
            model=SYNTHESIS_MODEL,
            max_tokens=5000,
            messages=[{"role": "user", "content": prompt}],
        ))
        raw = getattr(resp.content[0], "text", "{}") if resp.content else "{}"
        raw = re.sub(r"^```json?\s*", "", raw.strip())
        raw = re.sub(r"\s*```$", "", raw.strip())

        try:
            report = json.loads(raw)
        except json.JSONDecodeError as e:
            print(f"   JSON parse error: {e}")
            report = {"raw_output": raw, "parse_error": str(e)}

        report["sources"] = self.all_sources
        report["_config_dimensions"] = self.dimensions_config
        print("   Synthesis complete")
        return report

    def run(self):
        t0 = time.time()
        self.run_layer1()
        self.run_layer2()
        self.run_layer3()
        report = self.synthesize()
        report["_timing_seconds"] = round(time.time() - t0)
        print(f"\nDone in {report['_timing_seconds']}s")
        return report


def to_markdown(report):
    company = report.get("company", "")
    date = report.get("report_date", "")
    maturity = report.get("overall_maturity", "").upper()
    transparency = report.get("overall_transparency_level", "")

    lines = [
        f"# Strategic Analysis: {company}",
        f"*{date}  ·  Maturity: **{maturity}**  ·  Transparency: **{transparency}***",
        "", "---", "",
        "## Executive Summary", "",
        report.get("executive_summary", ""), "", "---", "",
    ]

    dims = report.get("dimensions", {})
    config_dims = report.get("_config_dimensions", [])
    iterator = config_dims if config_dims else [{"key": k, "label": k} for k in dims.keys()]

    for item in iterator:
        key = item["key"]
        label = item["label"]
        d = dims.get(key, {})
        if not d:
            continue

        lines += [f"## {label}", ""]
        lines += [f"**Summary:** {d.get('summary', '')}", "", "**Key Facts:**"]
        for fact in d.get("key_facts", []):
            lines.append(f"- {fact}")

        if "champion" in key.lower():
            names = d.get("champion_names", [])
            lines += ["", "**Identified Champions:**"]
            for name in (names if names else ["Not found"]):
                lines.append(f"- {name}")

        lines += [
            "",
            f"**Information Gap:** {d.get('information_gap', '')}",
            "",
            f"**Strategic Implication:** _{d.get('strategic_implication', '')}_",
            "", "---", "",
        ]

    diffs = report.get("key_differentiators", [])
    if diffs:
        lines += ["## Key Differentiators", ""]
        lines += [f"- {x}" for x in diffs]
        lines += ["", "---", ""]

    bench = report.get("benchmarks_vs_competitors", [])
    if bench:
        lines += ["## Benchmarks vs Competitors", ""]
        lines += [f"- {x}" for x in bench]
        lines += ["", "---", ""]

    meta = report.get("search_metadata", {})
    density = meta.get("density_map", {})
    lines += [
        "## Search Metadata", "",
        f"- Information richness: **{meta.get('information_richness_overall', '')}**",
        f"- Total sources collected: **{len(report.get('sources', []))}**",
        "", "**Dimension density:**",
    ]

    for item in iterator:
        key = item["key"]
        label = item["label"]
        s = density.get(key, 0)
        bar = "●" * int(s) + "○" * (2 - int(s)) if isinstance(s, int) else "??"
        lines.append(f"- {bar}  {label}")

    sources = report.get("sources", [])
    if sources:
        lines += ["", "---", "", "## References", ""]
        for i, s in enumerate(sources, 1):
            url = s.get("url", "")
            title = s.get("title", "") or url
            lines.append(f"{i}. [{title}]({url})")

    lines += ["", f"*Generated by Company Analysis Report Agent — {date}*"]
    return "\n".join(lines)


def save_outputs(report, company, out_dir):
    os.makedirs(out_dir, exist_ok=True)
    slug = re.sub(r"[^a-z0-9]+", "_", company.lower()).strip("_")
    date = report.get("report_date", datetime.date.today().isoformat())

    json_path = os.path.join(out_dir, f"{slug}_{date}.json")
    md_path = os.path.join(out_dir, f"{slug}_{date}.md")

    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(report, f, ensure_ascii=False, indent=2)
    with open(md_path, "w", encoding="utf-8") as f:
        f.write(to_markdown(report))

    return json_path, md_path


def extract_notion_page_id(url_or_id: str) -> str:
    clean = url_or_id.split("?")[0].rstrip("/")
    match = re.search(r"([a-f0-9]{32})", clean.replace("-", ""))
    return match.group(1) if match else url_or_id


def push_to_notion(report: dict[str, Any], page_id: str) -> None:
    if not HAS_NOTION:
        print("   notion-client / notion-markdown not installed, skipping Notion push")
        return
    if not NOTION_TOKEN:
        print("   NOTION_TOKEN not set, skipping Notion push")
        return

    company = report.get("company", "Unknown")
    print(f"   Pushing {company} to Notion page {page_id[:8]}...")
    notion = NotionClient(auth=NOTION_TOKEN)  # type: ignore[misc]
    md_text = to_markdown(report)

    divider = [{"type": "divider", "divider": {}}]
    blocks = md_to_notion_blocks(md_text)  # type: ignore[misc]

    all_blocks = divider + blocks
    for i in range(0, len(all_blocks), 100):
        chunk = all_blocks[i : i + 100]
        api_call_with_retry(lambda c=chunk: notion.blocks.children.append(block_id=page_id, children=c))
        time.sleep(0.5)

    print(f"   Notion push complete ({len(blocks)} blocks)")


def load_companies(filepath):
    companies = []
    with open(filepath, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith("#"):
                companies.append(line)
    return companies


def run_batch(companies, output_dir, config_path=None, delay_between=15, notion_page=""):
    total = len(companies)
    results = []

    print(f"\n{'='*58}")
    print(f"  BATCH MODE: {total} companies")
    print(f"  Output: {output_dir}")
    print(f"{'='*58}")

    for i, company in enumerate(companies, 1):
        print(f"\n[{i}/{total}] Starting: {company}")
        print("-" * 58)

        try:
            agent = CompetitiveIntelAgent(company=company, config_path=config_path)
            report = agent.run()
            json_path, md_path = save_outputs(report, company, output_dir)

            results.append({
                "company": company,
                "status": "success",
                "maturity": report.get("overall_maturity", ""),
                "sources": len(report.get("sources", [])),
                "md_file": md_path,
                "time_s": report.get("_timing_seconds", 0),
            })
            if notion_page:
                push_to_notion(report, notion_page)

            print(f"\n  [{i}/{total}] {company} — done ({report.get('_timing_seconds')}s)")
            print(f"     MD: {md_path}")

        except Exception as e:
            print(f"\n  [{i}/{total}] {company} — FAILED: {e}")
            results.append({"company": company, "status": "failed", "error": str(e)})

        if i < total:
            print(f"\n  Waiting {delay_between}s before next company...")
            time.sleep(delay_between)

    print(f"\n{'='*58}")
    print("BATCH SUMMARY")
    print("=" * 58)
    for r in results:
        status = "OK" if r["status"] == "success" else "FAILED"
        if r["status"] == "success":
            print(f"  {status} {r['company']} | Sources: {r['sources']} | Time: {r['time_s']}s")
            print(f"     -> {r['md_file']}")
        else:
            print(f"  {status} {r['company']} — {r.get('error', '')}")
    print("=" * 58)
    return results


def main():
    parser = argparse.ArgumentParser(
        description="Company Analysis Report Agent — Strategic intelligence for any company",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python scripts/agent.py --company "Deutsche Bank" --config references/strategy_dimensions.md
  python scripts/agent.py --file companies.txt --config references/strategy_dimensions.md

companies.txt format (one company per line, # to skip):
  Deutsche Bank
  HSBC
  # JPMorgan Chase
        """,
    )
    parser.add_argument("--company", default="", help="Single company name")
    parser.add_argument("--file", default="", help="Batch input: path to txt file")
    parser.add_argument("--domain", default="", help="Override official website domain")
    parser.add_argument("--output", default="./reports", help="Output directory (default: ./reports)")
    parser.add_argument("--delay", type=int, default=15, help="Seconds between companies in batch mode")
    parser.add_argument("--notion-page", default="", help="Notion page URL or ID to append report")
    parser.add_argument("--config", default="", help="Path to dimensions config (references/strategy_dimensions.md)")

    args = parser.parse_args()
    notion_page = extract_notion_page_id(args.notion_page) if args.notion_page else ""

    if not API_KEY:
        raise SystemExit(
            "\nANTHROPIC_API_KEY is not set.\n"
            "Run: export ANTHROPIC_API_KEY=sk-ant-...\n"
        )

    if args.file:
        if not os.path.exists(args.file):
            raise SystemExit(f"File not found: {args.file}")
        companies = load_companies(args.file)
        if not companies:
            raise SystemExit(f"No valid company names in {args.file}")
        run_batch(companies, args.output, config_path=args.config or None, delay_between=args.delay, notion_page=notion_page)

    elif args.company:
        agent = CompetitiveIntelAgent(company=args.company, config_path=args.config or None, domain=args.domain)
        report = agent.run()
        json_path, md_path = save_outputs(report, args.company, args.output)

        if notion_page:
            push_to_notion(report, notion_page)

        meta = report.get("search_metadata", {})
        density = meta.get("density_map", {})

        print(f"\n{'='*58}")
        print("REPORT SUMMARY")
        print("=" * 58)
        print(f"  Company      : {report.get('company')}")
        print(f"  Maturity     : {report.get('overall_maturity', '').upper()}")
        print(f"  Transparency: {report.get('overall_transparency_level', '')}")
        print(f"  Sources     : {len(report.get('sources', []))}")
        print(f"  Time        : {report.get('_timing_seconds')}s")
        print("\n  Dimension density:")
        for d in report.get("_config_dimensions", []):
            s = density.get(d["key"], 0)
            bar = "●" * int(s) + "○" * (2 - int(s)) if isinstance(s, int) else "??"
            print(f"    {bar}  {d['label']}")
        print(f"\n  JSON: {json_path}")
        print(f"  MD  : {md_path}")
        print("=" * 58)

    else:
        parser.print_help()


if __name__ == "__main__":
    main()
