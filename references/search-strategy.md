# Strategic Search Architecture

This document outlines the search strategy used by the Company Analysis Report Agent. The strategy is **domain-agnostic** and **configuration-driven**, adapting based on dimensions defined in `strategy_dimensions.md`.

---

## The 3-Layer Search Model

### Layer 1 — Signal Search (Broad & Fast)

**Purpose**: Gauge overall information density and identify high-level strategic themes.

- Uses the **first dimension** from your config to generate broad search queries
- Determines if there is enough public information for detailed analysis
- Produces a density map scoring information richness (High/Medium/Low)

### Layer 2 — Dimension Search (Deep & Specific)

**Purpose**: Systematically gather evidence for each configured dimension.

- For every dimension, the agent generates **3 targeted search queries** via LLM
- Queries combine: Company Name + Dimension Topic + specific aspects
- Time-scoped (e.g., 2024 2025) to filter outdated information
- Fact-seeking: nouns (partners, tools, metrics) rather than general descriptions

### Layer 3 — Source-Targeted Search (Authoritative)

**Purpose**: Retrieve ground truth from high-authority sources.

- **Official Domain** (`site:company.com`): Strategic keywords on company website
- **Executive Voice**: CEO interviews, speeches, letters
- **Investor Materials**: Annual reports, investor presentations, transcripts

---

## Configuration-Driven Workflow

1. **You define** dimensions in `strategy_dimensions.md`
2. **Agent generates** tailored search queries per dimension
3. **Agent synthesizes** a report with dedicated sections per dimension

---

## Information Gaps as Findings

Absence of evidence is evidence. If Layers 2 and 3 find no information on a dimension, the agent records an **Information Gap** and analyzes why (low transparency, early adoption, internal-only, etc.).
