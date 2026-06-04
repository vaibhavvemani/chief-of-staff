# Course Builder — Source Files Reference (Current State)

> **What this is.** A precise, descriptive map of the five Excel workbooks the team has built manually so far. Its purpose is to record *what exists and how it's structured* so we don't have to re-read the raw files every session.
>
> **What this is NOT.** This is not a proposal for the artifact schemas. It documents *how we did it*, not *how we have to do it*. Every structure here is a candidate to keep, change, or discard when we design the real artifacts. Read this to understand the ground truth; decide the schema separately.
>
> *Based on: Product_construct_ver1.xlsx, SRM_Full_Product_Construct_.xlsx, Corporate_Governance_TOC_final.xlsx, Compliance_Regulatory_Landscape_TOC_MODIFIED.xlsx, Course_Status.xlsx.*

---

## 1. The five workbooks at a glance

| Workbook | Role in the process | Sheets |
|---|---|---|
| **Product_construct_ver1.xlsx** | Master **planning + benchmarking** workbook. Defines the program-level plan and the step process, and holds per-subject competitor TOC grids. | `Product dimensions`, `Content dev process`, `ERM`, `FRM`, `CG` |
| **SRM_Full_Product_Construct_.xlsx** | Same template as above, for the SRM subject. | `Product dimensions`, `Content dev process`, `SRM` |
| **Corporate_Governance_TOC_final.xlsx** | A **finalized TOC** workbook for one subject (CG): competitor scan → cross-reference → in-house TOC → grounding sources. | `Course Comparison`, `ToC Comparison`, `FINAL TOC`, `Tools & Regulations` |
| **Compliance_Regulatory_Landscape_TOC_MODIFIED.xlsx** | Same kind of TOC workbook for the Compliance & Regulatory Landscape subject. *(No `FINAL TOC` sheet — see §6.)* | `Course Comparison`, `ToC Comparison`, `Tools & Regulations` |
| **Course_Status.xlsx** | The **production tracker** for the built FRM course: which assets exist, their files, and per-module hours/slides. | `Sheet1` (master tracker), `Module 1` … `Module 10` |

The three layers, in the order work flows through them:

```
PLAN & BENCHMARK            DEFINE STRUCTURE              PRODUCE & TRACK
Product_construct       →   *_TOC_*.xlsx             →   Course_Status.xlsx
(dimensions, process,       (Course Comparison,          (master tracker +
 per-subject TOC grids)      ToC Comparison,              per-module asset
                             FINAL TOC,                   sheets with real
                             Tools & Regulations)         files)
```

**Subjects represented:** FRM (planned + benchmarked + fully produced/tracked), CG (benchmarked + final TOC), Compliance & Regulatory Landscape (benchmarked + TOC), SRM (planned + benchmarked), ERM (benchmark grid only).

---

## 2. The process the files encode (the "Content dev process" sheet)

`Product_construct_ver1.xlsx → Content dev process` lays the step process out as columns. Reproduced verbatim (lightly cleaned), with the supporting notes that sit under each step:

| Step | Headline | Supporting notes (as written in the sheet) |
|---|---|---|
| **1** | Shortlist subject | Subjects listed beneath: **FRM, ERM, CG** |
| **2** | Freeze TOC on the basis of desk research | "Vett and validate in consultation with domain experts." "Freeze final TOC for the maximum or expanded version of the course." |
| **2** *(dup. label)* | Arrive at all versions of the course that can be created and freeze their TOC | "For each of these, separate desk research and competition comparison is important." |
| **3** | Chapter structure framework needs to be done | "List all pedagogical elements for the chosen subject." "Fun facts, did you know, quotes, important people in this domain (Nobel laureates), big companies, caselets, big cases, data banks, online tools, etc." "List of topic-wise SME for review and video recordings." |
| **4** | Create framework for each pedagogical element | "Allocate count for each element for each chapter and **aim for 20–50% EXTRA**." "Create a clear **bill of materials** for all assets." |
| **5** | Create a few samples for each with variations on tone, language, presentation, seriousness, etc. | "Freeze on one for each element before applying to all topics." "Ensure each chapter is **self-contained with no cross-linkages** at the content level." "Linkages are to be handled by faculty at instruction level." |
| **6** | Train the trainer, trainer support materials | "Solutions to assessments, cases, lesson plan, lecture plan, etc." |
| **7, 8** | *(present as columns but empty in these files)* | — |

**Notes worth flagging:**
- The numbering has a **duplicated "step 2"** label — the process as drawn is a little informal, not a clean 1–8.
- This six-effective-step process is the manual ancestor of the four-step product flow (Structure → Blueprint → Student Content → Lesson Plan). Steps 1–2 ≈ Structure; step 4 ≈ Blueprint metadata; steps 3–5 ≈ Student Content; step 6 ≈ Lesson Plan / trainer enablement.

---

## 3. The planning layer — `Product dimensions`

A program-level planning matrix (present in both construct workbooks; same template). It is **business/program planning, not course-content structure.**

- **Rows = audience segments**, each paired with a level:
  - BBA / Bcom → UG
  - MBA / Mcom → PG (plus "Other UG programs")
  - Exec MBA → Working Professionals
  - Certification Programs → Working Professionals
- **Columns = a four-phase journey**, each phase with "Service delivery" sub-columns:
  - **Phase 1 – Learn:** input, source, customer, payer
  - **Phase 2 – DO:** partner, degree, other bodies (domestic / international), memberships
  - **Phase 3 – Demonstrate / Showcase:** in person, virtual support, virtual content, master class, mentorship, projects, internships
  - **Phase 4 – Jobs:** capstone evaluations, contests, publications, first job
- Recurring **"Role of Garime"** placeholder rows — open ownership slots not yet filled in (matches the "open roles" note in the Current-State Process Map).

> This sheet sits *above* a single course — it frames the whole product line. It does not currently feed any specific artifact shape directly; it's context for *what* to build, not *how* a course is structured.

---

## 4. The structure layer — TOC workbooks

Two **different layouts** are used to benchmark competitors. Both exist in the file set, which is itself a finding.

### 4a. In-construct grid (`FRM`, `ERM`, `CG`, `SRM` sheets inside the construct workbooks)

- Title row (subject) + a `TOC-Comparison` label.
- **Header row:** `TOC Category` in column 0, then **one column per competing program** (10–12 programs; e.g. FRM benchmarks Baruch, Princeton, CMU, Imperial, Rotman, NYU Stern, Columbia, Reading, NMIMS, IIM Indore).
- **Each cell** = a bullet-style list of how that competitor covers that canonical category.
- **Reading:** rows are *our* canonical categories; you scan across to see how each program treats each one. Purpose: build the expanded in-house TOC from the union of coverage.

### 4b. Standalone TOC workbook (`Corporate_Governance_TOC_final.xlsx`, `Compliance_..._TOC_MODIFIED.xlsx`)

Four sheets, in order of use:

**`Course Comparison`** — one row per competing program, **13 fields**:
`Course Name · Provider / Institution · Platform · Duration · Price (₹) · Level · Key Topics Covered · Rating · Business Focus · Technical Depth · Key Strength · Key Weakness · Source / Verify Link`

**`ToC Comparison`** — column 0 holds **our own TOC** (modules + subtopics), and the remaining columns are competitor programs aligned alongside. (Same intent as 4a, but with *our* TOC as the anchor column rather than abstract categories.)

**`FINAL TOC`** — the cleaned, finalized **in-house expanded TOC** for the subject. Just the structure: module headings and their subtopics. *(Only present in the CG file.)*

**`Tools & Regulations`** — **2 columns**: `Item / Tool / Regulation` and `Verified Source / Link`. Organized as ALL-CAPS category headers (e.g. `INDIAN STATUTES`, `SEBI CIRCULARS & COMMITTEE REPORTS`, `GLOBAL FRAMEWORKS`) with indented items beneath, each carrying a **verified URL**. This is the grounding-source collection — the anti-hallucination backbone.

### 4c. How hierarchy is encoded in the TOC (important)

In `FINAL TOC` and the column-0 TOC of `ToC Comparison`, structure is encoded **as text, not as data**:
- **Modules** = a numeric prefix: `01. Foundations of Corporate Governance` (or `1.` style).
- **Subtopics** = the same cell column, **indented with leading spaces**: `    Evolution, purpose, and relevance`.
- There are **no explicit ID columns** and no separate hierarchy fields. The nesting is purely visual.
- The convention is **inconsistent in places** — some lines have a single leading space, some embed `INDIA -` / `GLOBAL -` tags inline within a subtopic, some run long. A parser couldn't rely on indentation alone.

---

## 5. The production layer — `Course_Status.xlsx`

This is the only workbook showing a *built* course (FRM), and it has two distinct sheet types.

### 5a. `Sheet1` — the master tracker

A **two-row header**:
- **Row 1 (element groups):** `S/N · Name · Case Study · Personality/Event · Learning Objectives · Course · Summary · Did you know · Assessment · Additional Resources · Activities · Total Hours · Slides`
- **Row 2 (sub-columns):** under each element group, a **`Status` + `Link` pair**. `Total Hours` and `Slides` are single columns.

**Body rows:**
- **Module rows** — e.g. `Module 1 | Foundations of Financial Risk | … | Hours | Slides`. (Modules 1–10 for FRM.)
- **Subtopic rows** beneath each — e.g. `1.1 | Nature of Financial Risk | …`, with a `Status` (e.g. `Done`) and `Link` per pedagogical element.

> Quirk: only **Module 1** has Hours/Slides filled (2.5 hrs, 49 slides); the rest are blank. The hours/slides "blueprint" data is mostly **not captured** here.

### 5b. `Module 1` … `Module 10` — per-module asset sheets

Where the actual produced material is recorded. Layout per sheet:
- Row 0: module title. Row 1: header `Module N | Links | Details`.
- Then, **per subtopic** (`1.1`, `1.2`, …), a block of asset rows. For each subtopic the assets tracked are:
  `Learning Objectives · Course Content · Summary · Case Study · Important Person · Did you know · Assessment · Activities · Resources`
- Each asset row carries the **real file name** in the `Links` column (e.g. `Financial-Risk-Management.pptx`, `The-Lehman-Brothers-Collapse.pptx`, `Learning Objectives and Summary.docx`) and a **`Details` excerpt** of the content (e.g. "Lehman Brothers Collapse (2008) as a multi-risk case…").

---

## 6. Asset-list reconciliation (a known drift)

Three different lists of "pedagogical elements" appear, and they don't fully agree:

| Source | Elements named |
|---|---|
| **Process step 3 (wishlist)** | pedagogical elements + fun facts, did you know, quotes, important people, big companies, caselets, big cases, data banks, online tools |
| **Tracker groups (Sheet1)** | Case Study, Personality/Event, Learning Objectives, Course, Summary, Did you know, Assessment, Additional Resources, Activities |
| **Per-module sheets (actual)** | Learning Objectives, Course Content, Summary, Case Study, Important Person, Did you know, Assessment, Activities, Resources |

The tracker and the per-module sheets are close but not identical (naming differs: "Personality/Event" vs "Important Person"; "Course" vs "Course Content"; "Additional Resources" vs "Resources"). The step-3 wishlist is broader than either. **This is the spec-vs-practice drift the Current-State Process Map already flagged.**

Other structural divergences in the file set:
- The Compliance workbook has **no `FINAL TOC` sheet**; CG does.
- Two **different TOC-comparison layouts** (§4a vs §4b) coexist.
- `Total Hours` / `Slides` are defined columns but **mostly unfilled**.

---

## 7. What maps to which target artifact (orientation only)

A rough bridge from these files to the four-step product flow. **Orientation, not a schema decision.**

| Target artifact | Closest current source(s) | State today |
|---|---|---|
| **Domain Model** | TOC-comparison grids + `Tools & Regulations` + step-3 "important people/cases/tools" wishlist | **No single artifact exists.** It's scattered across benchmarking + grounding sources. Largely greenfield. |
| **TOC** | `FINAL TOC` / `ToC Comparison` column 0 | Exists, but **text-encoded** hierarchy with no IDs (§4c). |
| **Blueprint** (hours, slides, speakers, dependencies) | `Total Hours` / `Slides` in tracker; SME list mentioned in process | **Barely exists.** Partial hours/slides for one module; no dependency map; speakers only as an SME-list intention. Largely greenfield. |
| **Content Package** | Per-module asset sheets + the real `.docx`/`.pptx` files | Exists as **files on disk tracked in a sheet**, not structured data. |
| **Lesson Plan** | Process step 6 (trainer support, lesson/lecture plans, solutions) | **Defined in the process, not present** in these files. |

---

## 8. Observations that will matter when we design the schemas

Flagged as observations and open questions — **not** decisions.

1. **No stable IDs exist anywhere.** Hierarchy is implied by numeric prefixes and indentation, inconsistently. The schema work's "stable IDs for modules/subtopics" requirement means we'll be *imposing* IDs the source data never had — we can't extract them, we have to assign them.
2. **Two benchmark layouts** (category-anchored vs our-TOC-anchored). If the Domain Model / competitor scan is to be a clean artifact, we pick one canonical representation.
3. **Blueprint and Domain Model are mostly greenfield.** They are the least represented in current files — which is consistent with them being the parts the manual process is weakest at. Schema design here is more invention than reverse-engineering.
4. **The asset set is fluid and drifts.** Any Content Package schema should probably treat the element list as configurable, not hardcoded — practice already varies the names and set.
5. **Grounding sources are real and verified** (`Tools & Regulations` with URLs). This is the strongest existing asset and the clearest thing to carry forward into the Domain Model / grounding design.
6. **FRM is the most complete worked example** end-to-end (planned → benchmarked → produced/tracked). It is the natural candidate for the single reference course we reverse-engineer the schemas from.

---

*Descriptive snapshot of the manual files as provided. Update if the source files change. Schema decisions live in the artifact-design work, not here.*
