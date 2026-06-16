# Course Builder — LLM Provider & Model Recommendation

**Use Claude as the spine, tiered by asset difficulty, and hold a cross-provider verifier in reserve.**

| Role in the pipeline | Model | Price (in / out per 1M) | Why |
|---|---|---|---|
| **Course Content + core-5 generation** | **Claude Opus 4.8** | $5 / $25 | Make-or-break quality; depth-first. At POC volume the cost is rounding error. |
| **Light-4 assets, formatting, LLM-as-judge** | **Claude Sonnet 4.6** | $3 / $15 | Balanced workhorse; 1M context; same SDK, same JSON contract. |
| **Adversarial verifier (fallback lever)** | **DeepSeek V4**, GPT-5.4, *or* Gemini 3.1 Pro | $0.14 / $0.28 · $2.50 / $15 · $2 / $12 | A *different* model family kills the same-model blind spot your Phase 1 plan already flags. DeepSeek is a different family **and** the cheapest — a strong fit for this role. |

**Why Claude and not the cheapest option:** at the team's real scope the development sprint runs **~$100–165** and a full 500-section production run stays **under ~$1,000** on the recommended stack (see §6) — with the cheapest provider only ~$700 below that. So price is not the deciding factor yet; fit and iteration speed are. Claude wins on fit for three reasons specific to *this* project: (1) the repo is **already wired to the Anthropic SDK** (`llm.py`, `learning_scripts/`, default `claude-opus-4-8`), so switching is pure rework for zero POC benefit; (2) Anthropic's native **Citations** maps almost 1:1 onto your claim-level attribution + "verifier locates the passage" design; (3) Claude leads public **function-calling / tool-use** reliability benchmarks (tau-bench), which underwrites your tool-use primitive.

**The one place a second provider earns its keep** is the *adversarial verifier* — your own Phase 1 plan calls a "diverse-model verifier" the fallback if same-model spot-checks miss things. That's a quality lever, not a cost one; wire it only if spot-checks show misses.

**On open-weight (DeepSeek / Qwen):** far cheaper than any frontier model and callable via hosted OpenAI-compatible APIs (no self-hosting). They belong in the **verifier** and **light-4 / at-scale** roles — *not* on the structured-generation spine, because of a measured strict-schema-adherence gap that collides with `integrity.py`. See §2a and §4.

---

## 1. What the Course Builder actually demands from an LLM

Derived from `Course_Builder_Phase1_Plan.md` (§C–F) and the artifact samples — these are the requirements every candidate is judged against:

| # | Requirement | Source in the plan | Weight |
|---|---|---|---|
| R1 | **Grounded generation** — write *only* from supplied source excerpts + the domain-model slice, not model memory | §C, §D ("generating from supplied verified sources, not model memory") | **Critical** |
| R2 | **Structured output** — clean prose **plus** a parallel `claims[]` array with `source_id`s, schema-valid v0.2 | §E asset shape | **Critical** |
| R3 | **Claim-level source attribution** the writer emits and a verifier confirms + locates the passage | §E, §F | **Critical** |
| R4 | **Adversarial verification** — a second, independent pass that hunts unsupported claims | §F ("you did NOT write this; find claims the source doesn't support") | High |
| R5 | **Domain accuracy** — FRM finance: dates, figures, named events, regulatory facts | §A (Lehman case), rubric §G | High |
| R6 | **Tool use** + **LLM-as-judge** for the eval harness | learning_scripts `c_tool_use.py`; §G | Medium |
| R7 | **Moderate context** — DM slice + 3–6 curated sources per prompt (not 1M-scale) | §D | Low/Med |
| R8 | **Cost telemetry & a cheap path for the easy assets** (model-mix is an explicit Phase 4 lever) | §D, §H, §N | Med (later) |

**Read-out:** this is a *faithfulness-and-structure* workload, not a long-context or raw-reasoning-ceiling workload. The deciding capabilities are **instruction-following / faithfulness (R1)**, **reliable structured output (R2/R3)**, and **tool reliability (R6)** — not who has the biggest context window or the top math score.

---

## 2. The candidate set (and what was excluded)

**Considered — frontier API families capable of all of R1–R6:**
- **Anthropic Claude** (Opus 4.8 / Sonnet 4.6 / Haiku 4.5)
- **OpenAI GPT-5.x** (GPT-5.5 / GPT-5.4 / GPT-5.4-mini / -nano)
- **Google Gemini 3.x** (3.1 Pro / 3.5 Flash / 3.1 Flash-Lite)
- **Open-weight via hosted APIs** (DeepSeek V4 Flash/Pro, Qwen3-Max) — capable for *specific roles*; see §2a

**Excluded, with reason (per your "only capable models" instruction):**
- **Other open-weight families not separately priced here** (Kimi K2.5, Llama 4, Mistral). Kimi K2.5 tops IFEval (~94); all are viable at-scale cost-floor options behind the JSON contract. DeepSeek and Qwen are the representative open-weight picks evaluated in §2a — the same role logic applies to these.
- **OpenAI/Anthropic "pro/reasoning-max" tiers** (GPT-5.5-pro $30/$180, Claude Fable 5 $10/$50). Overkill — this workload doesn't need a frontier *reasoning* ceiling, and the price is 6–36× the right tool. Not cost-justified.
- **Web-search / deep-research products.** Your grounding is from *supplied* sources, not the open web, so Google-Search-grounding and OpenAI deep-research add nothing here (see R1).

### 2a. Open-weight (DeepSeek / Qwen) — capable, but role-specific

Cheaper than any frontier model, and callable via hosted OpenAI-compatible APIs (DeepSeek first-party; Qwen via Alibaba Model Studio; both also on OpenRouter / Together / Fireworks) — **no self-hosting required**. First-class for *some* roles, with one capability caveat that decides *which*:

- **Strict structured output (R2/R3) is the gap.** A 2026 comparison puts DeepSeek JSON-mode at **~5–12% schema mismatch** vs **<0.1%** (OpenAI strict outputs) and **<0.2%** (Anthropic tool use); DeepSeek guarantees valid JSON *syntax*, not strict *schema* conformance, and `strict: true` has had a malformed-arguments bug. Treat the exact % as directional — the architectural point (no first-class constrained decoding) is the real signal. This collides with the v0.2 `claims[]` contract that `integrity.py` enforces, so it argues against open-weight on the **structured-generation spine**.
- **Data governance.** DeepSeek's first-party API and Qwen / DashScope route data to servers in China — a possible IP / compliance concern for proprietary FRM content. Mitigate by running the open weights on a Western host (Together / Fireworks) — a genuine advantage of open weights (you choose where they run), at the cost of an extra vendor and the loss of the cheapest first-party rates.

**Where they fit well:** the **diverse adversarial verifier** (different family kills the same-model blind spot; verdict output is small, so schema risk is low — DeepSeek V4 is arguably the best verifier pick, cheaper than GPT / Gemini) and the **light-4 / high-volume tier at Phase 4 scale** (the absolute cost floor; pair with a validator + retry). **Where they don't:** the core grounded-generation spine at POC stage, where the strict-schema gap costs more engineering than the ~$40 sprint saves.

---

## 3. Capability comparison (mapped to the requirements)

| Capability | Claude (Opus 4.8 / Sonnet 4.6) | OpenAI (GPT-5.5 / 5.4) | Gemini (3.1 Pro / 3.5 Flash) |
|---|---|---|---|
| **R1 Faithful/grounded generation** | Strong; literal instruction-following on 4.8 | Strong; 5.x follows structured prompts well | Strong |
| **R2 Structured output (JSON schema)** | ✅ `output_config.format`, strict tool schemas | ✅ strict structured outputs (very reliable) | ✅ structured output |
| **Strict-schema enforcement³** | ✅ first-class (<0.2% fail) | ✅ first-class (<0.1% fail) | ✅ first-class |
| **R3 Source attribution** | ✅ **native Citations** (cited spans w/ refs) — closest fit to claim-level design¹ | Via structured fields (you build it) | Via structured fields; Search-grounding is web-oriented |
| **R4/R6 Tool-use & function-call reliability** | ✅ **leads tau-bench** for function-call accuracy² | ✅ very strong; great computer-use | ✅ strong; wins abstract/scientific reasoning² |
| **R5 Domain accuracy (finance)** | High | High (5.4 strong at structured reasoning) | High |
| **R7 Context window** | 1M (Opus/Sonnet), 200K (Haiku) | large; gpt-5.5 has separate long-context pricing | 1M (Pro) |
| **Cheap tier for light-4 / high volume** | Haiku 4.5 $1/$5 | **gpt-5.4-mini $0.75/$4.50; nano $0.20/$1.25** | **Flash-Lite $0.25/$1.50** |
| **Cost levers** | Batch −50%, prompt caching (reads ~0.1×) | Batch −50%, cached input −90% | Batch −50%, context caching |
| **Already integrated in this repo** | ✅ yes (`llm.py`, learning_scripts, default model) | ✗ | ✗ |

¹ Anthropic Citations and structured-output JSON are **mutually exclusive in a single call** — so in practice you'd attribute via structured `claims[].source_id` in the *writer* call, and can use Citations in the *verifier* call where it shines (locate the supporting passage). Worth a Sprint-1 spike to decide which.
² Quality/benchmark claims are **directional**, drawn from 2026 third-party aggregators (BenchLM, BFCL/tau-bench leaderboards, RAG leaderboards) — treat as tie-breakers, not gospel. Your own rubric (§G) is the real arbiter.
³ Open-weight (DeepSeek / Qwen) lags here — DeepSeek JSON-mode shows ~5–12% schema mismatch (no first-class constrained decoding). This is the main reason they're scoped to the verifier / light / scale roles, not the structured-generation spine. See §2a.

**Bottom line on capability:** all three families clear the bar for R1–R6. The differentiators that matter *for this project* are Claude's **Citations fit (R3)** + **tool reliability (R6)** + **existing integration**, against the others' edge in **raw cheap-tier pricing**.

---

## 4. Pricing — current, authoritative (per 1M tokens, paid tier, standard)

**Sources:** Anthropic figures are the cached Claude-API reference (2026-05-26); OpenAI and Gemini figures are the official pricing docs, fetched 2026-06-11 (linked in §8). Prices move fast in 2026 — re-check before any scale commitment.

### Frontier "generation / verification" tier

| Model | Input | Output | Context | Notes |
|---|---|---|---|---|
| **Claude Opus 4.8** | $5.00 | $25.00 | 1M | 128K max output |
| **Claude Sonnet 4.6** | $3.00 | $15.00 | 1M | 64K max output |
| OpenAI GPT-5.5 | $5.00 | $30.00 | short-ctx; $10/$45 long-ctx | cached input $0.50 |
| OpenAI GPT-5.4 | $2.50 | $15.00 | — | cached $0.25; previous flagship |
| Google Gemini 3.1 Pro | $2.00 (≤200K) | $12.00 (≤200K) | 1M | $4/$18 above 200K; *Preview* |
| DeepSeek V4 Pro *(open-weight, hosted)* | $1.74 | $3.48 | — | promo discount active; cache hit −90%; strict-schema gap §2a |
| Qwen3-Max *(open-weight, hosted)* | $1.20 | $6.00 | — | batch $0.60/$3.00; strict-schema gap §2a |

### Cheap "light-asset / high-volume" tier

| Model | Input | Output | Notes |
|---|---|---|---|
| **Claude Haiku 4.5** | $1.00 | $5.00 | 200K context |
| OpenAI GPT-5.4-mini | $0.75 | $4.50 | |
| OpenAI GPT-5.4-nano | $0.20 | $1.25 | cheapest credible OpenAI |
| Google Gemini 3.5 Flash | $1.50 | $9.00 | "frontier intelligence built for speed" |
| Google Gemini 3.1 Flash-Lite | $0.25 | $1.50 | **absolute cost floor at the frontier vendors** |
| DeepSeek V4 Flash *(open-weight, hosted)* | $0.14 | $0.28 | **lowest overall**; cache hit −90%; strict-schema gap §2a |

**All five frontier vendors offer Batch (−50%) and prompt/context caching** — both directly applicable here (your sources + DM are a *stable prefix* reused across all 9 asset prompts in a run, so caching is a real win regardless of provider).

---

## 5. Reading the price table for *this* workload

- **Cheapest "Pro / generation" tier:** Qwen3-Max ($1.20 in / $6 out) ≈ DeepSeek V4 Pro ($1.74/$3.48) ≈ Gemini 3.1 Pro ($2/$12) < GPT-5.4 ($2.50/$15) < Sonnet 4.6 ($3/$15) < Opus 4.8 / GPT-5.5 ($5/$25–30).
- **Cheapest light-asset tier:** DeepSeek V4 Flash ($0.14/$0.28) ≪ GPT-5.4-nano ($0.20/$1.25) ≈ Gemini Flash-Lite ($0.25/$1.50) ≪ Haiku 4.5 ($1/$5).
- So if cost were the *only* axis, an **all-DeepSeek** stack is the floor by a wide margin. It isn't the only axis — the strict-schema gap (§2a) pushes open-weight toward the verifier / light / scale roles, and at the team's scale the absolute dollar gap (~$700 between the recommended stack and DeepSeek across 500 sections) is small relative to the reliability/eng cost it buys (next section).

---

## 6. Cost model

> Re-estimated 2026-06-11 against the team's real scope: a development sprint with genuine iteration, and a production run of **5 courses × ~100 sections ≈ 500 sections**. (The earlier draft under-counted development re-runs and projected an oversized 1,000-section production run — corrected below. Instrument the real numbers via `llm.py` token logging in Sprint 1 and re-fit.)

### 6.1 Token budget per section (the unit cost)

One section = **9 assets**, each generated *then* adversarially verified:

| Pass | Calls | Input each | Output each | Subtotal |
|---|---|---|---|---|
| Generation | 9 assets | ~12K (instructions + DM slice + 3–6 sources) | ~0.5–6K (Course Content is the big one) | ~108K in / ~18K out |
| Verification | 9 checks | ~12K (asset + its sources) | ~1.5K (unsupported-claim list) | ~108K in / ~13K out |
| **Per section** | | | | **~220K in / ~33K out** |

Cost of **one clean section run**:

| Stack | $/section |
|---|---|
| **All Opus 4.8** | ~$1.95 |
| **Tiered Claude — Opus (heavy assets + verify) + Sonnet (light)** | **~$1.65** |
| Gemini 3.1 Pro (+ Flash-Lite on light assets) | ~$0.85 |
| DeepSeek V4 (Pro + Flash) | ~$0.50 |

### 6.2 Development sprint (Phase 1)

Dev cost = (full-run-equivalents) × (per-section cost). A real sprint tunes prompts across all 9 asset types, runs the full pipeline for integration, and re-tests on 2–3 sections — realistically **~50–100 full-run-equivalents** over ~3 weeks.

| Iteration intensity | Tiered Claude | All Opus 4.8 | All Gemini |
|---|---|---|---|
| Light (~50 runs) | ~$83 | ~$98 | ~$43 |
| Heavy (~100 runs) | ~$165 | ~$195 | ~$85 |

Prompt caching on the stable source/DM prefix knocks **~25–35% off input** → realistic sprint **~$60–130**. **Budget ~$100–165 for development.** (Still immaterial at the team-budget level.)

### 6.3 Production — 5 courses × ~100 sections (~500 sections)

Single clean pass, **plus a ~20% allowance** for the human-in-the-loop "changes" re-runs the orchestrator supports:

| Stack | Clean pass | +~20% revisions | + Batch (−50%) & caching |
|---|---|---|---|
| All Opus 4.8 | ~$975 | ~$1,170 | ~$700 |
| **Tiered Claude (recommended)** | ~$825 | ~$990 | **~$600** |
| Gemini Pro + Flash-Lite | ~$425 | ~$510 | ~$310 |
| DeepSeek V4 (+ schema-repair harness) | ~$250 | ~$300 | ~$180 |

Production is **batch-friendly** (course generation isn't interactive, so the −50% Batch API applies cleanly) and caching helps within each section's 9 calls. **Budget ~$1,000 for the full 500-section run on the recommended stack; expect ~$600 with Batch + caching on.**

**Read-out:** development is a couple hundred dollars; the entire 500-section production run is **under ~$1,000** on the recommended stack. The gap to the cheapest provider (~$300, DeepSeek) is **~$700** — only worth chasing if you scale well past 500 sections, and only after the schema-repair harness (§2a) is built. Keep the JSON contract provider-agnostic so that later swap is config, not a rewrite.

---

## 7. Recommendation & rationale

**Adopt a Claude-spine, tiered, with a held-in-reserve cross-provider verifier:**

1. **Generation — Course Content + core-5 → Claude Opus 4.8.** The make-or-break quality path; depth-first per §D. Cost is negligible at POC volume.
2. **Light-4 assets, formatting, LLM-as-judge → Claude Sonnet 4.6** (drop specific assets to **Haiku 4.5** if the rubric shows they're fine cheaper). Same SDK, same contract, real cost savings that scale.
3. **Adversarial verifier → start with Opus 4.8; escalate to a *different family* — DeepSeek V4 (cheapest, and the verdict output is simple enough that the strict-schema gap barely bites), or GPT-5.4 / Gemini 3.1 Pro — only if same-model spot-checks miss things.** Exactly the fallback your Phase 1 plan §L names, and the single highest-value reason to integrate a second key.
4. **Keep `llm.py` provider-shaped** (model id + prompt-hash cache already there) so the Phase-4 cost optimisation — including open-weight light-tier or a Gemini floor — is a config change.

### Why not the alternatives (surfaced, per your "show me the tradeoffs" preference)
- **All-Gemini (cheapest):** best raw $/token, and a legitimate choice if you were starting greenfield and cost-first. Rejected as the spine because (a) you're not cost-bound at POC, (b) it means abandoning the working Anthropic integration, and (c) its grounding strength is *web search*, which your supplied-source design doesn't use. **Excellent *verifier* candidate**, though.
- **All-OpenAI:** GPT-5.4 ($2.50/$15) is strong and undercuts Opus; strict structured outputs are first-rate; mini/nano are cheaper than Haiku. The best pick *if you preferred the OpenAI ecosystem*. Rejected as spine for the same integration + Citations-fit reasons. **Also a strong verifier candidate.**
- **All open-weight (DeepSeek / Qwen, cheapest by far):** the at-scale cost floor and a fine *verifier*. Rejected as the spine because of the measured strict-schema-adherence gap colliding with `integrity.py` (§2a) and the China-routing data-governance question — both of which bite hardest precisely on the complex `claims[]` generation step. The savings (~$700 across a 500-section production run) don't justify the reliability/eng cost until you scale well past that.
- **Single-model everything (no tiering):** simplest, and fine for Phase 1. You lose the easy cost savings on the light-4 and the blind-spot protection on verification — both cheap to add later, so not a Phase-1 blocker.

### What would change the recommendation
- If **Phase 4 volume** arrives and quality on the light-4 holds → push them to **DeepSeek V4 Flash ($0.14/$0.28, the floor) / Flash-Lite / nano**, behind a JSON-schema validator + retry to absorb open-weight's looser schema adherence (§2a).
- If the team **standardises on a non-Anthropic stack** elsewhere → switching is viable; the cost penalty is small. Budget the integration rework against zero POC benefit.
- If finance **factuality** proves hard → the cross-provider verifier moves from "fallback" to "default day one."

---

## 8. Sources

**Anthropic** — model IDs, context, and pricing from the bundled Claude-API reference (cached 2026-05-26): Opus 4.8 $5/$25, Sonnet 4.6 $3/$15, Haiku 4.5 $1/$5, Fable 5 $10/$50; Batch −50%, prompt caching, structured outputs, Citations, tool use.

**OpenAI** — [OpenAI API Pricing (official docs)](https://developers.openai.com/api/docs/pricing) · [openai.com/api/pricing](https://openai.com/api/pricing/) (fetched 2026-06-11): gpt-5.5 $5/$30, gpt-5.5-pro $30/$180, gpt-5.4 $2.50/$15, gpt-5.4-mini $0.75/$4.50, gpt-5.4-nano $0.20/$1.25; cached input −90%, Batch −50%.

**Google Gemini** — [Gemini Developer API pricing (official docs)](https://ai.google.dev/gemini-api/docs/pricing) (fetched 2026-06-11): Gemini 3.1 Pro $2/$12 (≤200K; $4/$18 above), 3.5 Flash $1.50/$9, 3.1 Flash-Lite $0.25/$1.50; Batch −50%, context caching, Google-Search grounding.

**Open-weight (DeepSeek / Qwen)** — [DeepSeek API pricing](https://api-docs.deepseek.com/quick_start/pricing) (V4 Flash $0.14/$0.28, V4 Pro $1.74/$3.48, cache hit −90%; fetched 2026-06-11) · [Qwen / Alibaba Model Studio pricing](https://www.alibabacloud.com/help/en/model-studio/model-pricing) (Qwen3-Max $1.20/$6.00, batch −50%). Strict structured-output reliability gap from [Structured Output / JSON-mode comparison, 2026](https://tokenmix.ai/blog/structured-output-json-guide) (DeepSeek ~5–12% schema mismatch vs <0.1% OpenAI / <0.2% Anthropic — directional). Both DeepSeek and Qwen route first-party-API data to servers in China; mitigate via a Western inference host for proprietary content.

**Capability / benchmark (directional)** — [BenchLM agent benchmarks](https://benchlm.ai/llm-agent-benchmarks) · [Function-calling leaderboard](https://awesomeagents.ai/leaderboards/function-calling-benchmarks-leaderboard/) · [RAG leaderboard](https://pricepertoken.com/leaderboards/rag): Anthropic leads tau-bench function-call accuracy; GPT-5.x strong on structured reasoning; Gemini 3.1 Pro wins abstract/scientific reasoning; IFEval (instruction-following) is the most RAG-relevant axis. Treat as tie-breakers; the Phase-1 rubric is the real judge.
