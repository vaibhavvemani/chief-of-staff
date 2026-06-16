# Grounding Sources for Phase 1

These files are the curated grounding sources for `m1_s1` ("Nature of Financial Risk").
Each `g*.md` file is intended to become a registered grounding source in the
hand-authored Domain Model for S1.7.

| ID | File | Coverage |
|---|---|---|
| g1 | `g1.md` | Risk vs uncertainty; Knightian uncertainty; measurable risk |
| g2 | `g2.md` | Credit risk; borrower/counterparty failure; credit exposure |
| g3 | `g3.md` | Liquidity risk; funding stress; stress testing; contingency funding |
| g4 | `g4.md` | Market risk; operational risk; major risk-category comparison |
| g5 | `g5.md` | Lehman Brothers case facts; leverage; repo funding; liquidity stress |

## How To Use These In S1.7

When authoring the Domain Model, register these source IDs under
`grounding_sources`. The `id` values should remain stable because generated
content and verifier claims will later cite them.

Suggested Domain Model categories:

- `FOUNDATIONAL CONCEPTS`: g1
- `BANKING RISK TAXONOMY`: g2, g3, g4
- `CRISIS CASES`: g5

