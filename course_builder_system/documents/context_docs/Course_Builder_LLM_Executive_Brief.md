# Course Builder — AI Provider Decision Brief

## What we're deciding

The Course Builder system uses large language models (LLMs) through vendor APIs to automatically generate educational course content — learning objectives, explanations, case studies, assessments — from curated source material. We need to select which AI vendor(s) to build on.

This decision affects **quality, cost, and how fast the team can ship.** We're making it now because the system is about to move from a skeleton to a live AI-powered pipeline.

---

## Our recommendation

> **Build on Anthropic Claude. Use a tiered model strategy within Claude. Reserve a second-provider option for quality verification only.**

| Role | Provider & Model | Why this tier |
|---|---|---|
| Core content generation (high-stakes assets) | **Anthropic — Claude Opus 4.8** | Highest quality where it matters most |
| Supporting content (summaries, formatting, eval) | **Anthropic — Claude Sonnet 4.6** | Cost-efficient for lighter assets |
| Adversarial quality check (optional, standby) | **DeepSeek V4** or **OpenAI GPT-5.4** | Independent second opinion, wired only if needed |

**Development cost: ~$100–165** for the full Phase 1 build-and-test sprint (all prompt tuning and testing). **Production cost: ~$600–1,000** to generate all 5 courses (~500 sections). See the breakdown below — cost stays modest at every stage and only becomes a real lever well beyond this scale.

---

## Options considered

Four provider families were evaluated:

| Provider | Best model(s) | Input / Output cost (per 1M tokens) | Tier |
|---|---|---|---|
| **Anthropic (Claude)** | Opus 4.8, Sonnet 4.6, Haiku 4.5 | $5 / $25 → $1 / $5 | Frontier |
| **OpenAI (ChatGPT)** | GPT-5.5 (flagship), GPT-5.4, GPT-5.4-mini / nano | $5 / $30 → $0.20 / $1.25 | Frontier |
| **Google (Gemini)** | Gemini 3.1 Pro, 3.5 Flash, Flash-Lite | $2 / $12 → $0.25 / $1.50 | Frontier |
| **Open-weight (DeepSeek / Qwen)** | DeepSeek V4 Flash / V4 Pro, Qwen3-Max | $0.14 / $0.28 → $1.74 / $3.48 | Budget |

*All four families are technically capable of the task. The differences that matter are in fit, reliability, and integration cost — not raw capability.*

*Pricing current as of June 2026 (per 1M tokens, standard tier); verify against vendor pricing pages before procurement. OpenAI's current flagship is GPT-5.5 ($5/$30); GPT-5.4 ($2.50/$15) is the previous-generation value tier.*

---

## Option breakdown — pros, cons, and fit

### Option A — Anthropic Claude *(recommended)*

**What it is:** Anthropic's API gives access to Claude models, including the current top-of-line Opus 4.8 and the mid-tier Sonnet 4.6. It's already integrated in the codebase.

| Pros | Cons |
|---|---|
| Already wired into the codebase — no integration work | Priced at a premium vs. Gemini on the pro tier ($5/$25 input/output vs $2/$12) |
| Native **Citations** feature maps directly onto our source-attribution design (a core product requirement) | Pricier on output than the previous-gen GPT-5.4 ($15) and Gemini ($12) — though it now **undercuts** the current GPT-5.5 flagship ($30) |
| Leads industry benchmarks for function-call / tool-use reliability — critical for our pipeline | Cheap tier (Haiku) is slightly more expensive than OpenAI's nano / Google's Flash-Lite |
| Single SDK, consistent API contract across all tiers | |
| Strong policy on faithfulness and instruction-following — directly relevant to our "generate only from supplied sources" requirement | |

**Verdict:** The strongest fit for this specific project given existing integration, Citations fit, and tool-use reliability. Not the absolute cheapest, but cost is not the deciding factor at POC scale.

---

### Option B — OpenAI (ChatGPT API)

**What it is:** OpenAI's API gives access to the GPT-5.x model family — from GPT-5.5 (top-of-line) down to the very cheap nano tier. Well-established, extensive tooling.

| Pros | Cons |
|---|---|
| Previous-gen GPT-5.4 ($2.50/$15) undercuts Opus — a cheaper near-frontier option | No existing integration — migration cost with no POC benefit |
| Best-in-class strict structured output reliability (<0.1% schema failure) | Cached-input pricing model differs from ours — less straightforward to apply |
| Cheapest credible nano tier ($0.20/$1.25) for high-volume light assets | No native equivalent to Anthropic Citations; attribution design needs to be hand-built |
| Batch API (-50%) and strong caching available | Current flagship GPT-5.5 ($5/$30) is **pricier on output** than Opus 4.8 ($5/$25) |

**Verdict:** The best pick *if we were starting greenfield on the OpenAI ecosystem* or needed the absolute cheapest light tier. Ruled out as the spine because switching costs exceed any POC savings, and Citations fit is genuinely valuable.

---

### Option C — Google Gemini

**What it is:** Google's Gemini 3.x family, accessed via Google AI / Vertex AI. Gemini 3.1 Pro is a frontier model; Flash-Lite is among the cheapest available per-token.

| Pros | Cons |
|---|---|
| **Lowest frontier cost** — Pro at $2/$12 (≤200K context); Flash-Lite at $0.25/$1.50 | No existing integration — migration cost |
| 1M context window on Pro — but Google adds a long-context premium above 200K ($4/$18); Claude Opus is flat-priced across its full 1M | Grounding feature is optimised for *web search*, not our supplied-source design |
| Leads benchmarks on abstract and scientific reasoning tasks | No native source-attribution primitive comparable to Citations |
| Flash-Lite is the cheapest frontier model for high-volume work | |
| Batch (-50%) and context caching available | |

**Verdict:** The strongest *cost* case of the three frontier providers — a legitimate choice if this decision were purely dollars. Ruled out as the spine because we're not cost-constrained at POC, the integration is greenfield, and its grounding story doesn't fit our use case. **Strong candidate for the adversarial verifier role** at Phase 4 scale if cost becomes a factor.

---

### Option D — Open-weight models (DeepSeek / Qwen)

**What it is:** Open-weight models (published weights, usable via hosted APIs with no self-hosting required) from DeepSeek and Alibaba's Qwen. Callable via OpenAI-compatible endpoints on DeepSeek first-party, Alibaba Model Studio, or Western hosts like Together / Fireworks.

| Pros | Cons |
|---|---|
| **Dramatically cheaper** — DeepSeek V4 Flash is $0.14/$0.28, the lowest price of any capable model | **Strict schema adherence gap**: ~5–12% mismatch rate vs <0.2% for frontier APIs. Our pipeline enforces strict JSON schemas; failures cascade into errors |
| Hosted APIs — no infrastructure to run | First-party APIs route data through servers in China — a potential IP / compliance concern for proprietary course content |
| Different model family = valuable for adversarial verification (avoids "same-model blind spot") | ~98% cache discount on V4 Flash (cache-hit $0.0028 vs $0.14 miss) helps, but doesn't fix the schema issue |
| Fine for tasks where output schema is loose (e.g., verdicts, summaries) | Narrower SDK / framework support than the frontier vendors — see "Tooling, SDK & ecosystem fit" below |

**Verdict:** **The cost floor by a wide margin**, and genuinely the right choice for the *adversarial verification* role — different model family reduces blind spots, and the verdict output is simple enough that the schema gap barely matters. Ruled out as the generation spine because the schema-mismatch rate collides with our data integrity checks, and at POC scale the cost savings are in the tens of dollars — not worth the reliability risk.

---

## Tooling, SDK & ecosystem fit

Raw capability is comparable across all four families. The bigger differentiator for a system like ours — which leans on **structured JSON output, tool/function calls, source attribution, and standard agent frameworks** — is how cleanly each vendor plugs into that tooling.

| Capability we rely on | Anthropic (Claude) | OpenAI | Google (Gemini) | DeepSeek / Qwen |
|---|---|---|---|---|
| First-party SDKs | 7 languages (Python, TS, Java, Go, Ruby, C#, PHP) | Python, TS (+ broad community) | Python, TS + Vertex AI | Python only; leans on its OpenAI-compatible endpoint |
| LangChain / LlamaIndex | First-party integrations | First-party (the de-facto standard others copy) | First-party integrations | Present, but feature support is uneven |
| Structured / strict JSON | Native strict structured outputs | Best-in-class strict mode | Supported | **Inconsistent** — community workaround libraries exist to add it |
| Function calling / tool use | Industry-leading reliability; native tool runner + **MCP** | Strong | Supported | Flash supports it; **reasoner (R1) does not** — limits agent use |
| Source attribution | Native **Citations** (maps to our requirement) | Hand-built | Hand-built (grounding is web-search-oriented) | Hand-built |
| Batch / caching | Batch API (-50%), prompt caching | Batch, caching | Batch (-50%), context caching | ~98% cache discount on V4 Flash |

**Takeaway.** Anthropic and OpenAI have the deepest, most reliable tooling surfaces; Gemini is close behind on first-party SDKs. **DeepSeek is the clear outlier** — it works (through an OpenAI-compatible endpoint), but ships fewer first-party SDKs, has uneven structured-output support, and its reasoning model can't do function calling at all. That's acceptable for the simple, loosely-structured *verifier* role we'd assign it, but it's another reason it can't be the generation spine, where strict schemas and tool use are non-negotiable.

---

## Cost perspective

Costs fall in two phases — **development** (building and testing the system) and **production** (generating real courses). Both are modest.

**The unit cost.** Generating one course section means producing **9 separate assets** — learning objectives, explanation, case study, assessment, and so on — then running an independent verification pass on each. That's roughly **220,000 tokens of input and 33,000 of output per section**. At the recommended (tiered Claude) pricing, **~$1.65 per section**.

### Development (Phase 1, ~3 weeks)

Development means generating and re-generating sections repeatedly while tuning the prompts for all 9 asset types — realistically **50–100 full runs** across the sprint.

| Stack | Light iteration (~50 runs) | Heavy iteration (~100 runs) |
|---|---|---|
| **Tiered Claude *(recommended)*** | ~$83 | ~$165 |
| All Opus 4.8 (max quality) | ~$98 | ~$195 |
| All Gemini (cheapest frontier) | ~$43 | ~$85 |

**Budget ~$100–165 for the development phase** on the recommended stack (less with caching enabled).

### Production — 5 courses × ~100 sections (~500 sections)

Includes a ~20% allowance for the human-review "request changes" re-runs built into the pipeline.

| Stack | Estimated cost | With batch & caching |
|---|---|---|
| All Opus 4.8 (max quality) | ~$1,170 | ~$700 |
| **Tiered Claude *(recommended)*** | ~$990 | **~$600** |
| Gemini Pro + Flash-Lite | ~$510 | ~$310 |
| DeepSeek (cheapest, +reliability work) | ~$300 | ~$180 |
---