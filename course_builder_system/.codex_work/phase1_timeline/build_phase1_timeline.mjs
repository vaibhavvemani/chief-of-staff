import fs from "node:fs/promises";
import path from "node:path";
import { SpreadsheetFile, Workbook } from "@oai/artifact-tool";

const outputDir = path.resolve("outputs/phase1_timeline_20260609");
const outputPath = path.join(outputDir, "Course_Builder_Phase1_Timeline.xlsx");

const palette = {
  ink: "#172033",
  navy: "#22304E",
  teal: "#1F7A75",
  softTeal: "#DFF2EF",
  amber: "#F2B84B",
  softAmber: "#FFF1CC",
  coral: "#E76F51",
  softCoral: "#FCE2DA",
  green: "#2E7D32",
  softGreen: "#E2F0D9",
  purple: "#7E57C2",
  softPurple: "#EDE7F6",
  slate: "#607083",
  mist: "#F6F8FB",
  grid: "#D9E1EC",
  white: "#FFFFFF",
  black: "#111827",
};

const tasks = [
  {
    id: "T01",
    activity: "Phase 1 kickoff and success metric alignment",
    sprint: "1 - Foundations",
    owner: "Both",
    depType: "SS",
    predecessors: "",
    start: 1,
    end: 1,
    priority: "High",
    status: "Planned",
    issueType: "Task",
    section: "Foundations",
    tags: "phase1,planning,quality-bar",
    description: "Confirm the Phase 1 goal, target subtopic, done condition, and review-time target shape.",
    acceptance: "Team agrees that m1_s1 is the target and that manual-quality-plus-light-review is the gate.",
    dependencyNotes: "Can start immediately."
  },
  {
    id: "T02",
    activity: "Acquire m1_s1 manual benchmark files",
    sprint: "1 - Foundations",
    owner: "P1",
    depType: "SS",
    predecessors: "",
    start: 1,
    end: 2,
    priority: "Critical",
    status: "Planned",
    issueType: "Task",
    section: "Foundations",
    tags: "phase1,benchmark,blocker",
    description: "Collect the existing manual docx/pptx assets for Nature of Financial Risk into benchmark/m1_s1/.",
    acceptance: "All relevant manual files are available locally or a fallback subtopic decision is recorded.",
    dependencyNotes: "Top practical blocker; requested on Day 1."
  },
  {
    id: "T03",
    activity: "Extract manual benchmark assets to text",
    sprint: "1 - Foundations",
    owner: "P1",
    depType: "FS",
    predecessors: "T02",
    start: 2,
    end: 3,
    priority: "High",
    status: "Planned",
    issueType: "Task",
    section: "Foundations",
    tags: "phase1,benchmark,extraction",
    description: "Create one-off text extracts from the manual benchmark files for scoring and reference.",
    acceptance: "Manual content can be compared asset-by-asset without opening original source files.",
    dependencyNotes: "Requires benchmark files."
  },
  {
    id: "T04",
    activity: "Build gold reference content_package.json",
    sprint: "1 - Foundations",
    owner: "P1",
    depType: "FS",
    predecessors: "T03",
    start: 3,
    end: 5,
    priority: "High",
    status: "Planned",
    issueType: "Task",
    section: "Foundations",
    tags: "phase1,benchmark,gold",
    description: "Create benchmark/m1_s1.gold.content_package.json using the same shape as agent output.",
    acceptance: "Gold package validates enough for apples-to-apples asset and rubric comparison.",
    dependencyNotes: "Requires extracted manual text."
  },
  {
    id: "T05",
    activity: "Hand-author m1_s1 domain model plus thin neighbor stubs",
    sprint: "1 - Foundations",
    owner: "P2",
    depType: "SS",
    predecessors: "",
    start: 1,
    end: 4,
    priority: "High",
    status: "Planned",
    issueType: "Task",
    section: "Foundations",
    tags: "phase1,domain-model,m1_s1",
    description: "Write the locked-schema domain model slice for m1_s1 and thin stubs for other module 1 subtopics.",
    acceptance: "Domain model gives prompts enough concept, scope, and neighbor context for one subtopic.",
    dependencyNotes: "Can start immediately from the locked design."
  },
  {
    id: "T06",
    activity: "Curate 3-6 grounding sources",
    sprint: "1 - Foundations",
    owner: "P2",
    depType: "SS",
    predecessors: "",
    start: 1,
    end: 3,
    priority: "High",
    status: "Planned",
    issueType: "Task",
    section: "Foundations",
    tags: "phase1,sources,grounding",
    description: "Choose strong source texts for definitions, risk taxonomy, and Lehman case facts.",
    acceptance: "Sources are specific, credible, and enough to ground significant factual claims.",
    dependencyNotes: "Can start immediately."
  },
  {
    id: "T07",
    activity: "Normalize source text files and metadata registry",
    sprint: "1 - Foundations",
    owner: "P2",
    depType: "FS",
    predecessors: "T06",
    start: 3,
    end: 4,
    priority: "High",
    status: "Planned",
    issueType: "Task",
    section: "Foundations",
    tags: "phase1,sources,metadata",
    description: "Create sources/g*.md excerpt files and register source IDs with metadata in the domain model.",
    acceptance: "Every source_id used by generation can resolve to source text and metadata.",
    dependencyNotes: "Requires source selection."
  },
  {
    id: "T08",
    activity: "Write rubric and review-time threshold",
    sprint: "1 - Foundations",
    owner: "P1",
    depType: "SS",
    predecessors: "T01",
    start: 1,
    end: 3,
    priority: "High",
    status: "Planned",
    issueType: "Task",
    section: "Foundations",
    tags: "phase1,rubric,evaluation",
    description: "Define the 7-dimension rubric and choose a concrete human review-time threshold.",
    acceptance: "Rubric anchors 3 as matching manual quality and records the timed-review gate.",
    dependencyNotes: "Starts after kickoff alignment."
  },
  {
    id: "T09",
    activity: "Build llm.py wrapper with retry, cache, and token logging",
    sprint: "1 - Foundations",
    owner: "P2",
    depType: "SS",
    predecessors: "T01",
    start: 2,
    end: 5,
    priority: "High",
    status: "Planned",
    issueType: "Task",
    section: "Foundations",
    tags: "phase1,llm,plumbing",
    description: "Implement the thin model-call wrapper, local response cache, retries, and token/cost logging.",
    acceptance: "A mocked or live call can be made through one stable wrapper without leaking secrets.",
    dependencyNotes: "Starts once kickoff decisions are clear."
  },
  {
    id: "T10",
    activity: "Run first throwaway sample",
    sprint: "1 - Foundations",
    owner: "P2",
    depType: "FS",
    predecessors: "T05,T07,T09",
    start: 5,
    end: 5,
    priority: "Medium",
    status: "Planned",
    issueType: "Milestone",
    section: "Foundations",
    tags: "phase1,sample,checkpoint",
    description: "Generate a small sample to prove the inputs and model wrapper connect.",
    acceptance: "A sample output exists and obvious input/plumbing failures are visible before Sprint 2.",
    dependencyNotes: "Needs domain model, sources, and model-call path."
  },
  {
    id: "T11",
    activity: "Bump content package schema to v0.2",
    sprint: "2 - Generator",
    owner: "P2",
    depType: "FS",
    predecessors: "T04,T07",
    start: 6,
    end: 7,
    priority: "High",
    status: "Planned",
    issueType: "Task",
    section: "Generator",
    tags: "phase1,schema,claims",
    description: "Update schema, sample artifact, stub, and integrity checks for claims and verification fields.",
    acceptance: "Content package v0.2 validates and claim source_ids must resolve to grounding source IDs.",
    dependencyNotes: "Requires gold shape and source registry."
  },
  {
    id: "T12",
    activity: "Write core 5 generation prompt templates",
    sprint: "2 - Generator",
    owner: "P1",
    depType: "FS",
    predecessors: "T05,T07,T08",
    start: 6,
    end: 8,
    priority: "High",
    status: "Planned",
    issueType: "Task",
    section: "Generator",
    tags: "phase1,prompts,core-assets",
    description: "Create parameterized prompts for Course Content, Learning Objectives, Summary, Case Study, and Assessment.",
    acceptance: "Each core asset prompt consumes DM, source text, subtopic context, and generation constraints.",
    dependencyNotes: "Needs domain model, sources, and rubric orientation."
  },
  {
    id: "T13",
    activity: "Build Student Content generation agent",
    sprint: "2 - Generator",
    owner: "P1",
    depType: "FS",
    predecessors: "T09,T11,T12",
    start: 7,
    end: 9,
    priority: "High",
    status: "Planned",
    issueType: "Task",
    section: "Generator",
    tags: "phase1,agent,generation",
    description: "Generate Course Content first, then condition the other core assets on the finished Course Content.",
    acceptance: "Core assets are produced as clean content plus claims arrays with cited source_ids.",
    dependencyNotes: "Needs wrapper, schema, and prompt templates."
  },
  {
    id: "T14",
    activity: "Wire generator into orchestrator adapter",
    sprint: "2 - Generator",
    owner: "P2",
    depType: "FS",
    predecessors: "T11,T13",
    start: 8,
    end: 10,
    priority: "High",
    status: "Planned",
    issueType: "Task",
    section: "Generator",
    tags: "phase1,orchestrator,adapter",
    description: "Replace the student_content_step stub with a thin adapter around the generation path.",
    acceptance: "run.py reaches the student content checkpoint with a v0.2 content_package artifact.",
    dependencyNotes: "Requires schema and generator implementation."
  },
  {
    id: "T15",
    activity: "Core 5 end-to-end smoke run",
    sprint: "2 - Generator",
    owner: "Both",
    depType: "MS",
    predecessors: "T13,T14",
    start: 10,
    end: 10,
    priority: "High",
    status: "Planned",
    issueType: "Milestone",
    section: "Generator",
    tags: "phase1,core5,checkpoint",
    description: "Run the pipeline and inspect the first complete core asset package.",
    acceptance: "Core 5 assets exist, are schema-valid, and can be reviewed before verification is added.",
    dependencyNotes: "Milestone after generator path is wired."
  },
  {
    id: "T16",
    activity: "Build verification prompt and verifier agent",
    sprint: "3 - Verify & Measure",
    owner: "P2",
    depType: "FS",
    predecessors: "T15",
    start: 11,
    end: 13,
    priority: "High",
    status: "Planned",
    issueType: "Task",
    section: "Verify & Measure",
    tags: "phase1,verification,claims",
    description: "Add a separate adversarial pass that checks cited claims against source excerpts asset-by-asset.",
    acceptance: "Verifier returns supported, partial, unsupported, and ungrounded verdicts per claim.",
    dependencyNotes: "Needs generated core content."
  },
  {
    id: "T17",
    activity: "Write verifier results back and surface checkpoint summary",
    sprint: "3 - Verify & Measure",
    owner: "P2",
    depType: "FS",
    predecessors: "T16",
    start: 12,
    end: 14,
    priority: "High",
    status: "Planned",
    issueType: "Task",
    section: "Verify & Measure",
    tags: "phase1,verification,checkpoint",
    description: "Persist verifier verdicts into claims[] and summarize verification stats per asset.",
    acceptance: "Human checkpoint shows supported, partial, unsupported, and ungrounded counts for each asset.",
    dependencyNotes: "Requires verifier implementation."
  },
  {
    id: "T18",
    activity: "Build scoring/comparison eval harness",
    sprint: "3 - Verify & Measure",
    owner: "P1",
    depType: "FS",
    predecessors: "T04,T08,T15",
    start: 11,
    end: 13,
    priority: "High",
    status: "Planned",
    issueType: "Task",
    section: "Verify & Measure",
    tags: "phase1,evaluation,scorecard",
    description: "Implement rubric scoring support and head-to-head comparison against the manual reference.",
    acceptance: "An eval run can propose coverage and style scores and capture mechanical scoring data.",
    dependencyNotes: "Needs gold package, rubric, and generated core output."
  },
  {
    id: "T19",
    activity: "Add scorecard JSON logging and trend helper",
    sprint: "3 - Verify & Measure",
    owner: "P1",
    depType: "FS",
    predecessors: "T18",
    start: 13,
    end: 14,
    priority: "Medium",
    status: "Planned",
    issueType: "Task",
    section: "Verify & Measure",
    tags: "phase1,evaluation,trends",
    description: "Save run scorecards with prompt SHA, verifier stats, rubric scores, review time, and costs.",
    acceptance: "Multiple runs can be compared over time with a small trend script.",
    dependencyNotes: "Requires eval harness."
  },
  {
    id: "T20",
    activity: "Improve and re-measure Core 5",
    sprint: "3 - Verify & Measure",
    owner: "Both",
    depType: "FS",
    predecessors: "T17,T19",
    start: 14,
    end: 15,
    priority: "Critical",
    status: "Planned",
    issueType: "Task",
    section: "Verify & Measure",
    tags: "phase1,iteration,core5",
    description: "Iterate on prompts or plumbing based on verifier/eval findings until core assets meet the bar.",
    acceptance: "Core 5 assets score at least 3 on comparative dimensions or gaps are explicitly queued for buffer.",
    dependencyNotes: "Needs verification and evaluation feedback."
  },
  {
    id: "T21",
    activity: "Timed human review of Core 5",
    sprint: "3 - Verify & Measure",
    owner: "Both",
    depType: "MS",
    predecessors: "T20",
    start: 15,
    end: 15,
    priority: "Critical",
    status: "Planned",
    issueType: "Milestone",
    section: "Verify & Measure",
    tags: "phase1,review,gate",
    description: "Measure whether a human review takes minutes with light touch-ups rather than a rewrite.",
    acceptance: "Review time and edit extent are recorded against the threshold set in Sprint 1.",
    dependencyNotes: "Core Week 3 gate."
  },
  {
    id: "T22",
    activity: "Write light 4 generation prompts",
    sprint: "4 - Finish & Handoff",
    owner: "P1",
    depType: "FS",
    predecessors: "T12,T21",
    start: 16,
    end: 17,
    priority: "Medium",
    status: "Planned",
    issueType: "Task",
    section: "Buffer / Finish",
    tags: "phase1,prompts,light-assets",
    description: "Create prompts for Important Person, Did You Know, Activities, and Resources.",
    acceptance: "Light asset prompts are parameterized and aligned with the finished Course Content.",
    dependencyNotes: "Usually starts after core gate unless pulled forward."
  },
  {
    id: "T23",
    activity: "Generate and verify light 4 assets",
    sprint: "4 - Finish & Handoff",
    owner: "Both",
    depType: "FS",
    predecessors: "T17,T22",
    start: 17,
    end: 18,
    priority: "Medium",
    status: "Planned",
    issueType: "Task",
    section: "Buffer / Finish",
    tags: "phase1,light-assets,verification",
    description: "Produce and verify the four lighter assets so all 9 target asset types are present.",
    acceptance: "All light assets exist, are decent, and carry verification summaries.",
    dependencyNotes: "Requires verifier path and light prompts."
  },
  {
    id: "T24",
    activity: "Wire targeted feedback-driven regeneration loop",
    sprint: "4 - Finish & Handoff",
    owner: "Both",
    depType: "FS",
    predecessors: "T17,T20",
    start: 17,
    end: 19,
    priority: "Medium",
    status: "Planned",
    issueType: "Task",
    section: "Buffer / Finish",
    tags: "phase1,feedback,regeneration",
    description: "Use verifier flags as targeted feedback for per-asset regeneration when baseline works.",
    acceptance: "A flagged asset can be regenerated without rerunning unrelated assets.",
    dependencyNotes: "Optional unless core quality needs it."
  },
  {
    id: "T25",
    activity: "Optional second subtopic smoke check",
    sprint: "4 - Finish & Handoff",
    owner: "P2",
    depType: "OPT",
    predecessors: "T20",
    start: 18,
    end: 19,
    priority: "Optional",
    status: "Planned",
    issueType: "Task",
    section: "Buffer / Finish",
    tags: "phase1,stretch,generalization",
    description: "Run a cheap smoke check on another m1 subtopic to detect prompt overfitting.",
    acceptance: "Generalization risks are either low or documented for Phase 2/4.",
    dependencyNotes: "Stretch only; should not block Phase 1 signoff."
  },
  {
    id: "T26",
    activity: "Blind A/B human quality gate",
    sprint: "4 - Finish & Handoff",
    owner: "Both",
    depType: "MS",
    predecessors: "T21,T23",
    start: 19,
    end: 19,
    priority: "Critical",
    status: "Planned",
    issueType: "Milestone",
    section: "Buffer / Finish",
    tags: "phase1,quality-gate,blind-review",
    description: "Run the final blind side-by-side human scoring against the manual benchmark.",
    acceptance: "Agent content is at or above manual quality on the Phase 1 rubric, with light review only.",
    dependencyNotes: "Final quality gate."
  },
  {
    id: "T27",
    activity: "Write Phase 1 handoff and reusable lessons",
    sprint: "4 - Finish & Handoff",
    owner: "P1",
    depType: "FS",
    predecessors: "T26",
    start: 19,
    end: 20,
    priority: "High",
    status: "Planned",
    issueType: "Task",
    section: "Buffer / Finish",
    tags: "phase1,handoff,lessons",
    description: "Capture what worked, verifier findings, citation lessons, eval pattern, review burden, and cost data.",
    acceptance: "Handoff doc is ready and master context is updated for the next phase.",
    dependencyNotes: "Requires final gate findings."
  },
  {
    id: "T28",
    activity: "Final signoff and Phase 2 input list",
    sprint: "4 - Finish & Handoff",
    owner: "Both",
    depType: "MS",
    predecessors: "T27",
    start: 20,
    end: 20,
    priority: "Critical",
    status: "Planned",
    issueType: "Milestone",
    section: "Buffer / Finish",
    tags: "phase1,signoff,phase2",
    description: "Confirm Phase 1 done checklist and list the exact inputs Phase 2 should consume.",
    acceptance: "Phase 1 is signed off or remaining gaps are explicitly named with owner and date.",
    dependencyNotes: "Closes Phase 1."
  }
];

const sprintSummary = [
  ["1 - Foundations", "Days 1-5", "Set quality bar and gather inputs", "Rubric, benchmark, sources, domain model, LLM wrapper", "First sample runs"],
  ["2 - Generator", "Days 6-10", "Generate real source-grounded content", "Core 5 asset output through pipeline", "Core 5 smoke run"],
  ["3 - Verify & Measure", "Days 11-15", "Fact-check, score, improve", "Verified core content and scorecard", "Timed human review"],
  ["4 - Finish & Handoff", "Days 16-20", "Buffer, light assets, final gate", "All 9 assets, blind review, handoff", "Phase 1 signoff"]
];

const dependencyLegend = [
  ["Code", "Meaning", "Color role", "How to read it"],
  ["SS", "Start-to-start / independent start", "Teal", "Can begin at sprint start or in parallel with listed predecessor."],
  ["FS", "Finish-to-start", "Coral", "Wait for predecessor output before starting."],
  ["MS", "Milestone / gate", "Navy", "Decision point or checkpoint; usually one day."],
  ["OPT", "Optional / buffer stretch", "Purple", "Useful if capacity remains; should not block core signoff."]
];

const risks = [
  ["Risk", "Primary mitigation", "Owner", "Watch day", "Severity"],
  ["Manual gold assets hard to get or incomplete", "Request on Day 1; fall back to another m1 subtopic if blocked.", "P1", 1, "High"],
  ["Reaching manual-quality bar takes longer than expected", "Use Week 4 as planned quality buffer rather than cutting verification/eval.", "Both", 14, "High"],
  ["Thin or noisy sources cap output quality", "Curate 3-6 strong verified sources and flag ungrounded claims visibly.", "P2", 3, "Medium"],
  ["Verifier misses important claim problems", "Spot-check manually; use diverse-model verifier fallback if misses show up.", "P2", 13, "Medium"],
  ["Prompts overfit to m1_s1", "Keep prompts parameterized; run optional second-subtopic smoke check in buffer.", "P1", 18, "Medium"],
  ["Schema churn breaks existing skeleton", "Land schema bump, sample, stub, and integrity.py updates together with contract tests.", "P2", 7, "Medium"]
];

const columns = {
  taskBacklog: ["Task ID", "Activity", "Owner", "Sprint", "Dependency Type", "Predecessors", "Start Day", "End Day", "Duration", "Priority", "Status", "Jira Issue Type", "Asana Section", "Tags", "Description", "Acceptance Criteria", "Dependency Notes"],
  pmImport: ["Task ID", "Task Name", "Project/Epic", "Sprint/Section", "Owner", "Start Day", "Due Day", "Start Date", "Due Date", "Duration Workdays", "Dependency Type", "Predecessor IDs", "Priority", "Status", "Jira Issue Type", "Asana Section", "Tags", "Description", "Acceptance Criteria"]
};

function taskRow(t) {
  return [t.id, t.activity, t.owner, t.sprint, t.depType, t.predecessors, t.start, t.end, t.end - t.start + 1, t.priority, t.status, t.issueType, t.section, t.tags, t.description, t.acceptance, t.dependencyNotes];
}

function colName(indexZeroBased) {
  let n = indexZeroBased + 1;
  let s = "";
  while (n > 0) {
    const r = (n - 1) % 26;
    s = String.fromCharCode(65 + r) + s;
    n = Math.floor((n - 1) / 26);
  }
  return s;
}

function setTitle(sheet, range, title, subtitle) {
  sheet.getRange(range).merge();
  const cell = sheet.getRange(range.split(":")[0]);
  cell.values = [[title]];
  cell.format = {
    fill: palette.navy,
    font: { color: palette.white, bold: true, size: 18 },
    horizontalAlignment: "center",
    verticalAlignment: "center"
  };
  if (subtitle) {
    const [start] = range.split(":");
    const row = Number(start.match(/\d+/)[0]) + 1;
    sheet.getRange(`A${row}:L${row}`).merge();
    sheet.getRange(`A${row}`).values = [[subtitle]];
    sheet.getRange(`A${row}`).format = {
      fill: palette.mist,
      font: { color: palette.slate, italic: true, size: 10 },
      horizontalAlignment: "center",
      verticalAlignment: "center"
    };
  }
}

function styleHeader(range, fill = palette.teal) {
  range.format = {
    fill,
    font: { color: palette.white, bold: true },
    horizontalAlignment: "center",
    verticalAlignment: "center",
    wrapText: true,
    borders: { preset: "all", style: "thin", color: palette.grid }
  };
}

function styleBody(range) {
  range.format = {
    fill: palette.white,
    font: { color: palette.ink },
    verticalAlignment: "top",
    wrapText: true,
    borders: { preset: "all", style: "thin", color: palette.grid }
  };
}

function addTableIfPossible(sheet, range, name) {
  const table = sheet.tables.add(range, true, name);
  table.style = "TableStyleMedium2";
  table.showFilterButton = true;
  return table;
}

function applySheetBasics(sheet) {
  sheet.showGridLines = false;
}

const workbook = Workbook.create();

const overview = workbook.worksheets.add("Overview");
const timeline = workbook.worksheets.add("Timeline");
const backlog = workbook.worksheets.add("Task_Backlog");
const pm = workbook.worksheets.add("PM_Import");
const deps = workbook.worksheets.add("Dependencies");
const risk = workbook.worksheets.add("Risk_Register");
const legend = workbook.worksheets.add("Legend");

for (const sheet of [overview, timeline, backlog, pm, deps, risk, legend]) applySheetBasics(sheet);

// Overview
setTitle(overview, "A1:L1", "Course Builder Phase 1 Timeline", "Relative 20-workday plan for m1_s1 Nature of Financial Risk");
overview.getRange("A4:D4").values = [["Metric", "Value", "Target / meaning", "Source"]];
styleHeader(overview.getRange("A4:D4"), palette.teal);
overview.getRange("A5:D10").values = [
  ["Target duration", "3 weeks", "Finish core quality gate by Day 15", "Sprint Sheet"],
  ["Ceiling / buffer", "4 weeks", "Days 16-20 protect quality and finish light assets", "Sprint Sheet"],
  ["Total activities", tasks.length, "Detailed rows in Task_Backlog", "Generated from plan"],
  ["Core asset gate", "Day 15", "Core 5 >= manual quality with timed review", "Plan section K"],
  ["All asset gate", "Day 20", "All 9 assets, blind A/B gate, handoff", "Plan section K"],
  ["Optional start date", "", "Enter a real start date in Timeline!H2 to populate PM date columns", "User editable"]
];
styleBody(overview.getRange("A5:D10"));
overview.getRange("A5:A10").format.font = { bold: true, color: palette.ink };
overview.getRange("B10").format.fill = palette.softAmber;
overview.getRange("B10").setNumberFormat("yyyy-mm-dd");
overview.getRange("A12:E12").values = [["Sprint", "Workdays", "Focus", "Key deliverable", "Checkpoint"]];
styleHeader(overview.getRange("A12:E12"), palette.navy);
overview.getRange("A13:E16").values = sprintSummary;
styleBody(overview.getRange("A13:E16"));
addTableIfPossible(overview, "A12:E16", "SprintSummary");

overview.getRange("G4:H4").values = [["Owner", "Planned task-days"]];
styleHeader(overview.getRange("G4:H4"), palette.teal);
overview.getRange("G5:G7").values = [["P1"], ["P2"], ["Both"]];
overview.getRange("H5:H7").formulas = [
  ['=SUMIF(Task_Backlog!$C$2:$C$29,G5,Task_Backlog!$I$2:$I$29)'],
  ['=SUMIF(Task_Backlog!$C$2:$C$29,G6,Task_Backlog!$I$2:$I$29)'],
  ['=SUMIF(Task_Backlog!$C$2:$C$29,G7,Task_Backlog!$I$2:$I$29)']
];
styleBody(overview.getRange("G5:H7"));
addTableIfPossible(overview, "G4:H7", "OwnerLoad");

overview.getRange("G10:H10").values = [["Dependency type", "Task count"]];
styleHeader(overview.getRange("G10:H10"), palette.navy);
overview.getRange("G11:G14").values = [["SS"], ["FS"], ["MS"], ["OPT"]];
overview.getRange("H11:H14").formulas = [
  ['=COUNTIF(Task_Backlog!$E$2:$E$29,G11)'],
  ['=COUNTIF(Task_Backlog!$E$2:$E$29,G12)'],
  ['=COUNTIF(Task_Backlog!$E$2:$E$29,G13)'],
  ['=COUNTIF(Task_Backlog!$E$2:$E$29,G14)']
];
styleBody(overview.getRange("G11:H14"));
addTableIfPossible(overview, "G10:H14", "DependencyMix");

const ownerChart = overview.charts.add("bar", overview.getRange("G4:H7"));
ownerChart.title = "Planned Workdays by Owner";
ownerChart.hasLegend = false;
ownerChart.xAxis = { axisType: "textAxis" };
ownerChart.yAxis = { numberFormatCode: "0" };
ownerChart.setPosition("J4", "L15");

const depChart = overview.charts.add("bar", overview.getRange("G10:H14"));
depChart.title = "Task Count by Dependency Type";
depChart.hasLegend = false;
depChart.xAxis = { axisType: "textAxis" };
depChart.yAxis = { numberFormatCode: "0" };
depChart.setPosition("J17", "L28");

overview.getRange("A18:I20").merge();
overview.getRange("A18").values = [["Planning interpretation: Days 1-15 are the target path to prove Core 5 quality. Days 16-20 are intentional buffer for light assets, feedback loops, blind review, and handoff rather than unplanned spillover."]];
overview.getRange("A18").format = {
  fill: palette.softAmber,
  font: { color: palette.ink, bold: true },
  wrapText: true,
  verticalAlignment: "center",
  borders: { preset: "all", style: "thin", color: palette.amber }
};

overview.getRange("A1:L28").format.font = { name: "Aptos" };
overview.getRange("A:A").format.columnWidthPx = 150;
overview.getRange("B:B").format.columnWidthPx = 135;
overview.getRange("C:C").format.columnWidthPx = 260;
overview.getRange("D:D").format.columnWidthPx = 225;
overview.getRange("E:E").format.columnWidthPx = 185;
overview.getRange("G:G").format.columnWidthPx = 150;
overview.getRange("H:H").format.columnWidthPx = 140;
overview.getRange("J:L").format.columnWidthPx = 110;
overview.getRange("1:1").format.rowHeightPx = 34;
overview.getRange("2:2").format.rowHeightPx = 24;
overview.getRange("4:4").format.rowHeightPx = 34;
overview.getRange("5:10").format.rowHeightPx = 36;
overview.getRange("12:16").format.rowHeightPx = 54;
overview.getRange("18:20").format.rowHeightPx = 24;

// Timeline
timeline.getRange("A1:AC1").merge();
timeline.getRange("A1").values = [["Phase 1 Day-by-Day Timeline"]];
timeline.getRange("A1").format = {
  fill: palette.navy,
  font: { color: palette.white, bold: true, size: 18 },
  horizontalAlignment: "center",
  verticalAlignment: "center"
};
timeline.getRange("A2:B2").merge();
timeline.getRange("A2").values = [["Optional real start date"]];
timeline.getRange("C2:E2").merge();
timeline.getRange("C2").values = [["Leave blank for relative Day 1-Day 20 planning"]];
timeline.getRange("H2").formulas = [['=IF(Overview!B10="","",Overview!B10)']];
timeline.getRange("H2").setNumberFormat("yyyy-mm-dd");
timeline.getRange("A2:H2").format = {
  fill: palette.mist,
  font: { color: palette.ink },
  borders: { preset: "all", style: "thin", color: palette.grid },
  verticalAlignment: "center"
};

const weekBands = [
  ["J3:N3", "Week 1 / Sprint 1", palette.softTeal],
  ["O3:S3", "Week 2 / Sprint 2", palette.softCoral],
  ["T3:X3", "Week 3 / Sprint 3", palette.softGreen],
  ["Y3:AC3", "Week 4 / Buffer", palette.softPurple]
];
for (const [range, label, fill] of weekBands) {
  timeline.getRange(range).merge();
  timeline.getRange(range.split(":")[0]).values = [[label]];
  timeline.getRange(range.split(":")[0]).format = {
    fill,
    font: { color: palette.ink, bold: true },
    horizontalAlignment: "center",
    borders: { preset: "all", style: "thin", color: palette.grid }
  };
}

const timelineHeaders = ["ID", "Activity", "Owner", "Sprint", "Dep", "Pred", "Start", "End", "Dur"];
for (let day = 1; day <= 20; day++) timelineHeaders.push(day);
timeline.getRange("A4:AC4").values = [timelineHeaders];
styleHeader(timeline.getRange("A4:AC4"), palette.teal);
timeline.getRange("J4:AC4").setNumberFormat('"Day "0');
timeline.getRange("A5:I32").values = tasks.map(taskRow).map(row => row.slice(0, 9));
styleBody(timeline.getRange("A5:I32"));
timeline.getRange("A5:A32").format.font = { bold: true, color: palette.navy };
timeline.getRange("B5:B32").format.font = { bold: true, color: palette.ink };
timeline.getRange("G5:I32").format.horizontalAlignment = "center";

const timelineFormulaRows = [];
for (let r = 5; r <= 32; r++) {
  const row = [];
  for (let c = 9; c <= 28; c++) {
    const col = colName(c);
    row.push(`=IF(AND(${col}$4>=$G${r},${col}$4<=$H${r}),$E${r},"")`);
  }
  timelineFormulaRows.push(row);
}
timeline.getRange("J5:AC32").formulas = timelineFormulaRows;
timeline.getRange("J5:AC32").format = {
  fill: palette.white,
  font: { color: palette.white },
  horizontalAlignment: "center",
  verticalAlignment: "center",
  borders: { preset: "all", style: "thin", color: "#EEF2F6" }
};

const timelineGrid = timeline.getRange("J5:AC32");
timelineGrid.conditionalFormats.add("containsText", { text: "SS", format: { fill: palette.teal, font: { color: palette.teal } } });
timelineGrid.conditionalFormats.add("containsText", { text: "FS", format: { fill: palette.coral, font: { color: palette.coral } } });
timelineGrid.conditionalFormats.add("containsText", { text: "MS", format: { fill: palette.navy, font: { color: palette.navy } } });
timelineGrid.conditionalFormats.add("containsText", { text: "OPT", format: { fill: palette.purple, font: { color: palette.purple } } });
timeline.getRange("J4:AC4").format = {
  fill: palette.navy,
  font: { color: palette.white, bold: true },
  horizontalAlignment: "center",
  borders: { preset: "all", style: "thin", color: palette.grid }
};

timeline.freezePanes.freezeRows(4);
timeline.freezePanes.freezeColumns(9);
timeline.getRange("A1:AC32").format.font = { name: "Aptos" };
timeline.getRange("A:A").format.columnWidthPx = 46;
timeline.getRange("B:B").format.columnWidthPx = 330;
timeline.getRange("C:C").format.columnWidthPx = 70;
timeline.getRange("D:D").format.columnWidthPx = 138;
timeline.getRange("E:E").format.columnWidthPx = 54;
timeline.getRange("F:F").format.columnWidthPx = 88;
timeline.getRange("G:I").format.columnWidthPx = 48;
timeline.getRange("J:AC").format.columnWidthPx = 34;
timeline.getRange("1:1").format.rowHeightPx = 34;
timeline.getRange("3:4").format.rowHeightPx = 24;
timeline.getRange("5:32").format.rowHeightPx = 34;

timeline.getRange("AE4:AG4").values = [["Code", "Dependency", "Meaning"]];
styleHeader(timeline.getRange("AE4:AG4"), palette.navy);
timeline.getRange("AE5:AG8").values = dependencyLegend.slice(1).map(row => [row[0], row[1], row[3]]);
styleBody(timeline.getRange("AE5:AG8"));
timeline.getRange("AE5").format.fill = palette.teal;
timeline.getRange("AE5").format.font = { color: palette.white, bold: true };
timeline.getRange("AE6").format.fill = palette.coral;
timeline.getRange("AE6").format.font = { color: palette.white, bold: true };
timeline.getRange("AE7").format.fill = palette.navy;
timeline.getRange("AE7").format.font = { color: palette.white, bold: true };
timeline.getRange("AE8").format.fill = palette.purple;
timeline.getRange("AE8").format.font = { color: palette.white, bold: true };
timeline.getRange("AE:AE").format.columnWidthPx = 55;
timeline.getRange("AF:AF").format.columnWidthPx = 190;
timeline.getRange("AG:AG").format.columnWidthPx = 360;

// Task backlog
backlog.getRange("A1:Q1").values = [columns.taskBacklog];
styleHeader(backlog.getRange("A1:Q1"), palette.navy);
backlog.getRange("A2:Q29").values = tasks.map(taskRow);
styleBody(backlog.getRange("A2:Q29"));
addTableIfPossible(backlog, "A1:Q29", "TaskBacklog");
backlog.freezePanes.freezeRows(1);
backlog.getRange("A:Q").format.font = { name: "Aptos" };
backlog.getRange("A:A").format.columnWidthPx = 58;
backlog.getRange("B:B").format.columnWidthPx = 330;
backlog.getRange("C:C").format.columnWidthPx = 70;
backlog.getRange("D:D").format.columnWidthPx = 140;
backlog.getRange("E:E").format.columnWidthPx = 95;
backlog.getRange("F:F").format.columnWidthPx = 105;
backlog.getRange("G:I").format.columnWidthPx = 70;
backlog.getRange("J:K").format.columnWidthPx = 90;
backlog.getRange("L:M").format.columnWidthPx = 120;
backlog.getRange("N:N").format.columnWidthPx = 180;
backlog.getRange("O:Q").format.columnWidthPx = 360;
backlog.getRange("2:29").format.rowHeightPx = 40;
backlog.getRange("C2:C29").dataValidation = { rule: { type: "list", values: ["P1", "P2", "Both"] } };
backlog.getRange("E2:E29").dataValidation = { rule: { type: "list", values: ["SS", "FS", "MS", "OPT"] } };
backlog.getRange("J2:J29").dataValidation = { rule: { type: "list", values: ["Critical", "High", "Medium", "Optional"] } };
backlog.getRange("K2:K29").dataValidation = { rule: { type: "list", values: ["Planned", "In Progress", "Blocked", "Done", "Deferred"] } };

// PM Import
pm.getRange("A1:S1").values = [columns.pmImport];
styleHeader(pm.getRange("A1:S1"), palette.navy);
const pmRows = tasks.map((t, idx) => {
  const r = idx + 2;
  return [
    t.id,
    t.activity,
    "Course Builder Phase 1",
    t.sprint,
    t.owner,
    t.start,
    t.end,
    `=IF(Timeline!$H$2="","",Timeline!$H$2+F${r}-1)`,
    `=IF(Timeline!$H$2="","",Timeline!$H$2+G${r}-1)`,
    t.end - t.start + 1,
    t.depType,
    t.predecessors,
    t.priority,
    t.status,
    t.issueType,
    t.section,
    t.tags,
    t.description,
    t.acceptance
  ];
});
pm.getRange("A2:G29").values = pmRows.map(r => r.slice(0, 7));
pm.getRange("H2:I29").formulas = pmRows.map(r => r.slice(7, 9));
pm.getRange("J2:S29").values = pmRows.map(r => r.slice(9));
styleBody(pm.getRange("A2:S29"));
addTableIfPossible(pm, "A1:S29", "PMImport");
pm.freezePanes.freezeRows(1);
pm.getRange("H2:I29").setNumberFormat("yyyy-mm-dd");
pm.getRange("A:S").format.font = { name: "Aptos" };
pm.getRange("A:A").format.columnWidthPx = 62;
pm.getRange("B:B").format.columnWidthPx = 330;
pm.getRange("C:D").format.columnWidthPx = 150;
pm.getRange("E:E").format.columnWidthPx = 70;
pm.getRange("F:J").format.columnWidthPx = 88;
pm.getRange("K:L").format.columnWidthPx = 110;
pm.getRange("M:P").format.columnWidthPx = 115;
pm.getRange("Q:Q").format.columnWidthPx = 180;
pm.getRange("R:S").format.columnWidthPx = 360;
pm.getRange("2:29").format.rowHeightPx = 42;
pm.getRange("E2:E29").dataValidation = { rule: { type: "list", values: ["P1", "P2", "Both"] } };
pm.getRange("N2:N29").dataValidation = { rule: { type: "list", values: ["Planned", "In Progress", "Blocked", "Done", "Deferred"] } };

// Dependencies
deps.getRange("A1:D1").merge();
deps.getRange("A1").values = [["Dependency Model"]];
deps.getRange("A1").format = {
  fill: palette.navy,
  font: { color: palette.white, bold: true, size: 16 },
  horizontalAlignment: "center"
};
deps.getRange("A3:D3").values = [dependencyLegend[0]];
styleHeader(deps.getRange("A3:D3"), palette.teal);
deps.getRange("A4:D7").values = dependencyLegend.slice(1);
styleBody(deps.getRange("A4:D7"));
deps.getRange("A10:F10").values = [["Task ID", "Activity", "Dependency Type", "Predecessors", "Dependency Notes", "Import Hint"]];
styleHeader(deps.getRange("A10:F10"), palette.navy);
deps.getRange("A11:F38").values = tasks.map(t => [
  t.id,
  t.activity,
  t.depType,
  t.predecessors || "None",
  t.dependencyNotes,
  t.predecessors ? `${t.depType}: ${t.predecessors}` : "No predecessor"
]);
styleBody(deps.getRange("A11:F38"));
addTableIfPossible(deps, "A10:F38", "DependencyTable");
deps.freezePanes.freezeRows(10);
deps.getRange("A:F").format.font = { name: "Aptos" };
deps.getRange("A:A").format.columnWidthPx = 62;
deps.getRange("B:B").format.columnWidthPx = 330;
deps.getRange("C:D").format.columnWidthPx = 115;
deps.getRange("E:F").format.columnWidthPx = 360;
deps.getRange("11:38").format.rowHeightPx = 40;

// Risk register
risk.getRange("A1:E1").merge();
risk.getRange("A1").values = [["Phase 1 Risk Register"]];
risk.getRange("A1").format = {
  fill: palette.navy,
  font: { color: palette.white, bold: true, size: 16 },
  horizontalAlignment: "center"
};
risk.getRange("A3:E3").values = [risks[0]];
styleHeader(risk.getRange("A3:E3"), palette.teal);
risk.getRange("A4:E9").values = risks.slice(1);
styleBody(risk.getRange("A4:E9"));
addTableIfPossible(risk, "A3:E9", "RiskTable");
risk.getRange("A:E").format.font = { name: "Aptos" };
risk.getRange("A:A").format.columnWidthPx = 280;
risk.getRange("B:B").format.columnWidthPx = 420;
risk.getRange("C:C").format.columnWidthPx = 70;
risk.getRange("D:D").format.columnWidthPx = 78;
risk.getRange("E:E").format.columnWidthPx = 90;
risk.getRange("4:9").format.rowHeightPx = 48;

// Legend
legend.getRange("A1:F1").merge();
legend.getRange("A1").values = [["Workbook Legend and Source Notes"]];
legend.getRange("A1").format = {
  fill: palette.navy,
  font: { color: palette.white, bold: true, size: 16 },
  horizontalAlignment: "center"
};
legend.getRange("A3:D3").values = [dependencyLegend[0]];
styleHeader(legend.getRange("A3:D3"), palette.teal);
legend.getRange("A4:D7").values = dependencyLegend.slice(1);
styleBody(legend.getRange("A4:D7"));
legend.getRange("A4").format.fill = palette.teal;
legend.getRange("A4").format.font = { color: palette.white, bold: true };
legend.getRange("A5").format.fill = palette.coral;
legend.getRange("A5").format.font = { color: palette.white, bold: true };
legend.getRange("A6").format.fill = palette.navy;
legend.getRange("A6").format.font = { color: palette.white, bold: true };
legend.getRange("A7").format.fill = palette.purple;
legend.getRange("A7").format.font = { color: palette.white, bold: true };
legend.getRange("A10:B10").values = [["Sheet", "Purpose"]];
styleHeader(legend.getRange("A10:B10"), palette.navy);
legend.getRange("A11:B17").values = [
  ["Overview", "Executive summary, sprint checkpoints, and charts."],
  ["Timeline", "Primary day-by-day visual plan with dependency-colored bars."],
  ["Task_Backlog", "Editable source table with owners, statuses, durations, and acceptance criteria."],
  ["PM_Import", "Jira/Asana-ready table; add a real start date in Overview!B10 to populate dates."],
  ["Dependencies", "Dependency explanation plus per-task predecessor mapping."],
  ["Risk_Register", "Schedule and quality risks from the Phase 1 plan."],
  ["Legend", "Color coding and source notes."]
];
styleBody(legend.getRange("A11:B17"));
legend.getRange("D10:F10").values = [["Source document", "Path", "Used for"]];
styleHeader(legend.getRange("D10:F10"), palette.navy);
legend.getRange("D11:F12").values = [
  ["Phase 1 Implementation Plan", "documents/context_docs/Course_Builder_Phase1_Plan.md", "Scope, design, dependencies, DoD, risks"],
  ["Phase 1 Sprint Sheet", "documents/context_docs/Course_Builder_Phase1_Sprint_Sheet.md", "Sprint sequencing, owners, leadership-facing summary"]
];
styleBody(legend.getRange("D11:F12"));
legend.getRange("A:F").format.font = { name: "Aptos" };
legend.getRange("A:A").format.columnWidthPx = 160;
legend.getRange("B:B").format.columnWidthPx = 480;
legend.getRange("D:D").format.columnWidthPx = 210;
legend.getRange("E:E").format.columnWidthPx = 360;
legend.getRange("F:F").format.columnWidthPx = 280;
legend.getRange("11:17").format.rowHeightPx = 32;

// Compact formula/error verification and previews
await fs.mkdir(outputDir, { recursive: true });

const inspectOverview = await workbook.inspect({
  kind: "table",
  range: "Overview!A4:H16",
  include: "values,formulas",
  tableMaxRows: 16,
  tableMaxCols: 8
});
console.log(inspectOverview.ndjson);

const inspectTimeline = await workbook.inspect({
  kind: "table",
  range: "Timeline!A4:AC12",
  include: "values,formulas",
  tableMaxRows: 9,
  tableMaxCols: 29
});
console.log(inspectTimeline.ndjson);

const formulaErrors = await workbook.inspect({
  kind: "match",
  searchTerm: "#REF!|#DIV/0!|#VALUE!|#NAME\\?|#N/A",
  options: { useRegex: true, maxResults: 300 },
  summary: "final formula error scan"
});
console.log(formulaErrors.ndjson);

const renderTargets = [
  ["Overview", "A1:L28"],
  ["Timeline", "A1:AG32"],
  ["Task_Backlog", "A1:Q18"],
  ["PM_Import", "A1:S18"],
  ["Dependencies", "A1:F24"],
  ["Risk_Register", "A1:E9"],
  ["Legend", "A1:F17"]
];
for (const [sheetName, range] of renderTargets) {
  const preview = await workbook.render({ sheetName, range, scale: 1, format: "png" });
  const previewPath = path.join(outputDir, `${sheetName}.png`);
  await fs.writeFile(previewPath, new Uint8Array(await preview.arrayBuffer()));
  console.log(`rendered ${sheetName} ${previewPath}`);
}

const xlsx = await SpreadsheetFile.exportXlsx(workbook);
await xlsx.save(outputPath);
console.log(`saved ${outputPath}`);
