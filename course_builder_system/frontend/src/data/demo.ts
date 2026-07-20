import type {
  AssetPlan,
  BlueprintPlan,
  ContentAsset,
  CourseSummary,
  StageSummary,
  Subtopic,
  Workspace,
} from "../types";

const stageLabels = [
  ["brief", "Brief"],
  ["outcomes", "Outcomes"],
  ["research", "Research & Sources"],
  ["course-model", "Course Model"],
  ["blueprint", "Blueprint"],
  ["content", "Student Content"],
  ["lesson-plan", "Lesson Plan"],
  ["package", "Package"],
] as const;

export const demoStages: StageSummary[] = stageLabels.map(([slug, label], index) => ({
  slug,
  label,
  status: index < 5 ? "approved" : index === 5 ? "requires_attention" : "locked",
  count: index === 5 ? 9 : undefined,
  summary:
    index === 5
      ? "All assets were generated. Nine verification findings need a decision."
      : index < 5
        ? "Approved and current with upstream inputs."
        : "Complete content review to unlock this stage.",
  updatedAt: "2026-07-06T11:12:00Z",
  dependencies: [],
  downstreamStages: [],
  prerequisitesReady: index <= 5,
  approvalFailures: [],
  actions: [],
}));

export const demoCourses: CourseSummary[] = [
  {
    courseId: "coffee-live-main",
    title: "Coffee Making",
    subject: "Coffee making",
    status: "requires_attention",
    currentStage: "content",
    nextAction: "Resolve 9 verification findings",
    updatedAt: "2026-07-06T11:12:00Z",
    progress: 70,
    attentionCount: 9,
    approvedStages: 5,
    totalStages: 8,
    demo: true,
  },
  {
    courseId: "coffee-acceptance",
    title: "Coffee Making — Acceptance",
    subject: "Coffee making",
    status: "approved",
    currentStage: "package",
    nextAction: "Review rendered package",
    updatedAt: "2026-07-06T08:45:00Z",
    progress: 100,
    attentionCount: 0,
    approvedStages: 8,
    totalStages: 8,
    demo: true,
  },
];

const subtopics: Subtopic[] = [
  {
    id: "m1_s1",
    order: 1,
    title: "Core Concepts in Coffee Making",
    purpose: "Build a shared mental model of the seed-to-cup chain and the decisions that shape flavor.",
    inScope: ["Coffee lifecycle", "Bean freshness", "Brewing methods"],
    outOfScope: ["Commercial roasting profiles"],
    prerequisiteSubtopicIds: [],
    concepts: [
      {
        id: "c_m1_s1_1",
        name: "Seed-to-cup lifecycle",
        summary: "How growing, processing, roasting, storage, and brewing connect.",
        dependsOn: [],
        sourceIds: ["live_5"],
      },
    ],
    coverageRequirements: [
      {
        id: "cr_m1_s1_1",
        statement: "Explain the lifecycle and connect it to one practical buying or brewing decision.",
        conceptIds: ["c_m1_s1_1"],
        sourceIds: ["live_5"],
      },
    ],
    approvedSourceIds: ["live_5", "live_6"],
  },
  {
    id: "m1_s2",
    order: 2,
    title: "Practical Examples",
    purpose: "Apply the core model to realistic choices a new home brewer makes.",
    inScope: ["Method choice", "Recipe decisions", "Storage"],
    outOfScope: ["Cafe workflow"],
    prerequisiteSubtopicIds: ["m1_s1"],
    concepts: [
      {
        id: "c_m1_s2_1",
        name: "Brewing decisions",
        summary: "Matching method, beans, and constraints to a useful starting recipe.",
        dependsOn: [],
        sourceIds: ["live_5", "live_6"],
      },
    ],
    coverageRequirements: [
      {
        id: "cr_m1_s2_1",
        statement: "Compare two brewing approaches using explicit learner constraints.",
        conceptIds: ["c_m1_s2_1"],
        sourceIds: ["live_5", "live_6"],
      },
    ],
    approvedSourceIds: ["live_5", "live_6"],
  },
  {
    id: "m1_s3",
    order: 3,
    title: "Coffee Making Practice",
    purpose: "Turn principles into a repeatable, observable practice loop.",
    inScope: ["Brew log", "One-variable experiments", "Taste observation"],
    outOfScope: ["Sensory certification"],
    prerequisiteSubtopicIds: ["m1_s2"],
    concepts: [
      {
        id: "c_m1_s3_1",
        name: "Deliberate practice loop",
        summary: "Observe, change one variable, record, and repeat.",
        dependsOn: [],
        sourceIds: ["live_5"],
      },
    ],
    coverageRequirements: [
      {
        id: "cr_m1_s3_1",
        statement: "Complete a brew observation and propose a single controlled adjustment.",
        conceptIds: ["c_m1_s3_1"],
        sourceIds: ["live_5"],
      },
    ],
    approvedSourceIds: ["live_5"],
  },
  {
    id: "m1_s4",
    order: 4,
    title: "Coffee Making Troubleshooting",
    purpose: "Diagnose a disappointing cup and choose the smallest sensible next change.",
    inScope: ["Sour, bitter, weak, muddy", "Grind adjustment", "Equipment cleaning"],
    outOfScope: ["Machine repair"],
    prerequisiteSubtopicIds: ["m1_s3"],
    concepts: [
      {
        id: "c_m1_s4_1",
        name: "Troubleshooting loop",
        summary: "Work backward from taste through beans, grind, method, and equipment.",
        dependsOn: [],
        sourceIds: ["live_5", "live_6"],
      },
    ],
    coverageRequirements: [
      {
        id: "cr_m1_s4_1",
        statement: "Diagnose a common flavor problem and justify one next adjustment.",
        conceptIds: ["c_m1_s4_1"],
        sourceIds: ["live_5", "live_6"],
      },
    ],
    approvedSourceIds: ["live_5", "live_6"],
  },
];

const assetTypes = [
  ["lo", "learning_objectives", "Learning Objectives"],
  ["cc", "course_content", "Course Content"],
  ["summary", "summary", "Summary"],
  ["case", "case_study", "Case Study"],
  ["assess", "assessment", "Assessment"],
  ["activities", "activities", "Activities"],
  ["resources", "resources", "Resources"],
] as const;

const planFor = (subtopic: Subtopic): AssetPlan[] =>
  assetTypes.map(([suffix, assetType, title], index) => ({
    id: `${subtopic.id}_${suffix}`,
    assetType,
    title: assetType === "course_content" ? subtopic.title : title,
    selectionStatus:
      index < 3 ||
      (subtopic.id === "m1_s4" && ["case_study", "assessment", "activities"].includes(assetType)) ||
      (subtopic.id === "m1_s2" && assetType === "activities") ||
      (subtopic.id === "m1_s1" && assetType === "resources")
        ? "selected"
        : "proposed",
    sourceIds:
      index < 3 || assetType === "resources" ? subtopic.approvedSourceIds : subtopic.approvedSourceIds.slice(0, 1),
  }));

const blueprintPlans: BlueprintPlan[] = subtopics.map((subtopic, index) => ({
  subtopicId: subtopic.id,
  depth: "Introductory",
  minutes: 20,
  wordMinimum: 750,
  wordTarget: 1100,
  wordMaximum: 1550,
  examples: index === 1 || index === 3 ? 2 : 1,
  caseDepth: index === 3 ? "Detailed" : "None",
  assessmentComplexity: index === 1 || index === 3 ? "Analysis" : "Application",
  exception: index === 3,
  anchorWaiverConfirmed: false,
  assets: planFor(subtopic),
}));

const courseContent = `# Coffee Making Troubleshooting

## Begin with the cup, not the equipment

A disappointing cup is useful evidence. Describe what you taste before changing anything: is it **weak**, **watery**, **sour**, **bitter**, or simply different from what you expected? A precise observation keeps the repair loop focused.

## Work backward through the controllable decisions

Use four checkpoints: beans and storage, grind, brewing method, and equipment care. Change only one variable in the next attempt. That creates a clean comparison and turns every brew into a small learning experiment.

### A practical diagnostic

1. Name the most noticeable quality in the cup.
2. Check whether your beans and recipe were consistent with the previous brew.
3. Choose one variable with a plausible connection to the result.
4. Predict what the next cup should taste like if your diagnosis is correct.
5. Record the result, even when the change does not work.

## Key takeaway

Troubleshooting is not a hunt for a perfect universal recipe. It is a disciplined loop: observe, form a hypothesis, change one variable, and learn from the result.`;

const cleanAsset = (id: string, subtopicId: string, type: string, title: string): ContentAsset => ({
  id,
  subtopicId,
  type,
  title,
  format: type === "course_content" || type === "assessment" || type === "case_study" ? "pptx" : "docx",
  content:
    type === "course_content"
      ? courseContent.replace("Coffee Making Troubleshooting", title)
      : `# ${title}\n\nThis learner-facing ${title.toLowerCase()} supports the approved coverage for this subtopic.\n\n- Connect the core idea to a practical decision.\n- Use the approved source route.\n- Check understanding before continuing.`,
  status: "approved",
  reviewStatus: "approved",
  claims: [
    {
      id: `${id}_cl1`,
      text: "Brewing guidance covers methods, grinding, and equipment care.",
      sourceId: "live_5",
      support: "supported",
      excerpt: "techniques and tips for everything from grinding beans to cleaning equipment",
      note: "Directly supported by the approved source.",
    },
  ],
  verification: { supported: 1, partial: 0, unsupported: 0, ungrounded: 0, unattributed: 0 },
});

const contentAssets = blueprintPlans.flatMap((plan) =>
  plan.assets
    .filter((asset) => asset.selectionStatus === "selected")
    .map((asset) => cleanAsset(asset.id, plan.subtopicId, asset.assetType, asset.title)),
);

const flaggedIndex = contentAssets.findIndex((asset) => asset.id === "m1_s4_cc");
contentAssets[flaggedIndex] = {
  ...contentAssets[flaggedIndex],
  status: "requires_attention",
  reviewStatus: "pending",
  claims: [
    {
      id: "cl1",
      text: "Brewing techniques and tips cover everything from grinding beans to cleaning equipment.",
      sourceId: "live_5",
      support: "supported",
      excerpt: "techniques and tips for everything from grinding beans to cleaning equipment",
      note: "Directly stated in the approved source.",
    },
    {
      id: "cl2",
      text: "A grind that is too coarse produces weak or sour coffee because water passes through too quickly.",
      sourceId: "live_6",
      support: "unsupported",
      excerpt: null,
      note: "The assigned source is a site index and does not explain extraction speed or flavor outcomes.",
    },
    {
      id: "cl3",
      text: "A fine grind can make a French press bitter during a long steep.",
      sourceId: "live_6",
      support: "unsupported",
      excerpt: null,
      note: "No relevant passage was found in the routed source.",
    },
    {
      id: "cl4",
      text: "Old coffee oils create stale, bitter off-flavors.",
      sourceId: null,
      support: "ungrounded",
      excerpt: null,
      note: "This factual claim has no approved source attribution.",
    },
  ],
  verification: { supported: 1, partial: 1, unsupported: 2, ungrounded: 1, unattributed: 1 },
};

const summary = demoCourses[0];

export const demoWorkspace: Workspace = {
  course: summary,
  stages: demoStages,
  artifactVersion: "demo-coffee-live-main-r1",
  estimatedCost: 2.5,
  brief: {
    courseTitle: "Coffee Making",
    subject: "Coffee making",
    audience: "General adult learners who are new to the subject.",
    priorKnowledge: "No prior knowledge assumed.",
    purpose: "Build practical working knowledge of coffee making.",
    level: "Beginner",
    duration: "3 hours of self-paced learning",
    modality: "Self-paced",
    language: "English",
    inScope: ["Core concepts in coffee making", "Practical examples", "Troubleshooting"],
    outOfScope: ["Advanced specialist topics", "Commercial cafe operations"],
    mustHaveTopics: ["Practical examples"],
    constraints: ["Keep the course compact for the prototype run."],
    availableMaterials: [],
    jurisdiction: null,
    accessibilityRequirements: null,
    assessmentExpectations: "Short practical checks and scenario questions.",
    liveTeachingConstraints: null,
    toolsOrEquipment: null,
    freshnessRequirement: null,
    assumptions: [
      {
        field: "audience",
        value: "General adult learners who are new to the subject.",
        rationale: "The course director explicitly accepted this visible default.",
      },
      {
        field: "duration",
        value: "3 hours of self-paced learning",
        rationale: "The course director explicitly accepted this visible default.",
      },
      {
        field: "level",
        value: "Beginner",
        rationale: "The course director explicitly accepted this visible default.",
      },
    ],
    provenance: [
      { field: "purpose", source: "user", confidence: "explicit" },
      { field: "audience", source: "default", confidence: "explicit" },
      { field: "duration", source: "default", confidence: "explicit" },
      { field: "level", source: "default", confidence: "explicit" },
    ],
    intakeState: {
      explicitFields: ["purpose"],
      acceptedDefaultFields: ["audience", "duration", "level"],
      unresolvedRequiredFields: [],
      answeredQuestionIds: ["brief_purpose", "brief_audience", "brief_duration", "brief_level"],
      lastGapAnalysis: [],
    },
  },
  outcomes: [
    {
      id: "co1",
      statement: "Explain the core concepts and vocabulary needed to make coffee at home.",
      cognitiveLevel: "understand",
      evidence: "Learner accurately explains key terms in their own words.",
      priority: "core",
    },
    {
      id: "co2",
      statement: "Apply a repeatable process to prepare a balanced cup of coffee.",
      cognitiveLevel: "apply",
      evidence: "Learner completes a realistic brewing task using the process.",
      priority: "core",
    },
    {
      id: "co3",
      statement: "Analyze common flavor problems and justify the next variable to adjust.",
      cognitiveLevel: "analyze",
      evidence: "Learner diagnoses a scenario and explains a focused next step.",
      priority: "core",
    },
    {
      id: "co4",
      statement: "Evaluate whether a brewing approach fits the learner’s time, tools, and taste preferences.",
      cognitiveLevel: "evaluate",
      evidence: "Learner compares options against explicit criteria.",
      priority: "supporting",
    },
  ],
  research: {
    sources: [
      {
        id: "live_5",
        title: "Coffee education: origins, beans, brewing and sustainability",
        publisher: "National Coffee Association",
        sourceType: "Web page",
        locator: "https://www.ncausa.org/About-Coffee",
        status: "approved",
        trustNotes: "Recognized industry association with a broad, public education resource.",
        relevance: "Supports lifecycle, beans, brewing methods, storage, and equipment-care coverage.",
        assignedNodeIds: ["m1_s1", "m1_s2", "m1_s3", "m1_s4"],
      },
      {
        id: "live_6",
        title: "Coffee Research topic index",
        publisher: "CoffeeResearch.org",
        sourceType: "Web page",
        locator: "https://www.coffeeresearch.org/",
        status: "approved",
        trustNotes: "Useful topic index, but many entries lack the depth needed for causal claims.",
        relevance: "Broad coverage; currently too weak for three troubleshooting claims.",
        assignedNodeIds: ["m1_s1", "m1_s2", "m1_s4"],
      },
      {
        id: "live_7",
        title: "Anonymous espresso hack list",
        publisher: "Unknown",
        sourceType: "Blog post",
        locator: "https://example.test/espresso-hacks",
        status: "rejected",
        trustNotes: "Authorship and evidence trail are unclear.",
        relevance: "Advice falls outside beginner home-brewing scope.",
        assignedNodeIds: [],
      },
    ],
    competitors: [
      {
        id: "comp_homebrew",
        provider: "Example Learning",
        offering: "Home Coffee Brewing Basics",
        locator: "https://example.test/home-coffee",
        outlineStatus: "usable",
        outlineSections: ["Beans and freshness", "Grind size", "Water temperature", "Brew ratio", "Taste adjustment"],
        structureSummary: "Moves from inputs and recipe control to tasting and adjustment.",
      },
      {
        id: "comp_barista",
        provider: "Example Academy",
        offering: "Barista Fundamentals",
        locator: "https://example.test/barista",
        outlineStatus: "usable",
        outlineSections: ["Extraction basics", "Grind adjustment", "Recipe control", "Milk texture", "Troubleshooting"],
        structureSummary: "Introduces extraction before practice and closes with troubleshooting.",
      },
      {
        id: "comp_brewlab",
        provider: "Example Brew Lab",
        offering: "Brew Better Coffee at Home",
        locator: "https://example.test/brewlab",
        outlineStatus: "usable",
        outlineSections: ["Fresh beans", "Recipe basics", "Grind size", "Water quality", "Taste correction"],
        structureSummary: "Uses a home-brewing sequence with a final correction loop.",
      },
    ],
    observations: [
      "Grind size is the only topic present in all three comparable outlines.",
      "Competitors usually teach inputs before troubleshooting; the proposed model preserves this sequence.",
      "A guided one-variable practice loop is a useful differentiation opportunity.",
    ],
  },
  modules: [
    {
      id: "m1",
      order: 1,
      title: "Coffee Making Foundations",
      purpose: "Build the shared foundations needed for confident home brewing.",
      inScope: ["Coffee lifecycle", "Practical brewing"],
      outOfScope: ["Commercial operations"],
      prerequisiteModuleIds: [],
      subtopics,
    },
  ],
  courseModel: {
    modules: [{
      id: "m1",
      order: 1,
      title: "Coffee Making Foundations",
      purpose: "Build the shared foundations needed for confident home brewing.",
      inScope: ["Coffee lifecycle", "Practical brewing"],
      outOfScope: ["Commercial operations"],
      prerequisiteModuleIds: [],
      subtopics,
    }],
    courseOutcomeIds: ["co1", "co2", "co3", "co4"],
    rationales: [{
      id: "sr1",
      statement: "Foundations precede practice and troubleshooting.",
      relatedOutcomeIds: ["co1", "co2", "co3", "co4"],
    }],
    eligibleSources: [
      { id: "live_5", title: "Coffee brewing guide", publisher: "Example publisher" },
      { id: "live_6", title: "Water quality guide", publisher: "Example publisher" },
    ],
  },
  courseModelChecksum: "demo-course-model-checksum",
  blueprint: {
    defaults: {
      depth: "Introductory",
      minutes: 20,
      wordMinimum: 750,
      wordTarget: 1100,
      wordMaximum: 1550,
      examples: 2,
      caseDepth: "Brief",
      assessmentComplexity: "Application",
      assetTypes: ["learning_objectives", "course_content", "summary", "assessment"],
    },
    plans: blueprintPlans,
  },
  blueprintChecksum: "demo-blueprint-checksum",
  content: {
    assets: contentAssets,
    completed: contentAssets.length,
    expected: contentAssets.length,
  },
  lessonPlan: {
    sessions: [
      {
        id: "sess1",
        order: 1,
        title: "Foundations and the brew decision chain",
        durationMinutes: 40,
        covers: subtopics.slice(0, 2).map((subtopic) => ({
          subtopicId: subtopic.id,
          mode: "live",
          talkingPoints: [
            `Introduce ${subtopic.title} through the approved course content.`,
            "Use the selected activity or summary for consolidation.",
          ],
        })),
      },
      {
        id: "sess2",
        order: 2,
        title: "Practice, diagnosis, and transfer",
        durationMinutes: 40,
        covers: subtopics.slice(2).map((subtopic) => ({
          subtopicId: subtopic.id,
          mode: subtopic.id === "m1_s3" ? "self_study" : "live",
          talkingPoints: [
            `Apply ${subtopic.title} to a realistic learner scenario.`,
            "Close with a one-variable adjustment and learner reflection.",
          ],
        })),
      },
    ],
    totalDurationMinutes: 80,
    expectedSubtopicIds: subtopics.map((subtopic) => subtopic.id),
    coveredSubtopicIds: subtopics.map((subtopic) => subtopic.id),
    constraints: {
      maxSessionHours: 2,
      defaultMode: "live",
      calendarDates: [],
      instructorCount: null,
      deliveryPlatform: null,
    },
    unresolvedConstraints: ["calendar_dates", "instructor_count", "delivery_platform"],
    affectedSessionIds: [],
  },
  lessonPlanChecksum: "demo-lesson-plan-checksum",
  package: {
    format: "Markdown folder",
    operatorStatus: "requires_attention",
    integrityPassed: true,
    approvedSourceCount: 2,
    rejectedSourceLeaks: 0,
    selectedAssets: contentAssets.length,
    renderedAssets: contentAssets.length,
    unresolvedBlockers: 9,
    files: [
      { path: "README.md", label: "Course index", kind: "markdown" },
      { path: "course_overview.md", label: "Course overview", kind: "markdown" },
      { path: "source_index.md", label: "Source index", kind: "markdown" },
      { path: "lesson_plan.md", label: "Lesson plan", kind: "markdown" },
      {
        path: "modules",
        label: "Modules",
        kind: "folder",
        children: subtopics.map((subtopic) => ({
          path: `modules/${subtopic.id}`,
          label: subtopic.title,
          kind: "folder",
          children: contentAssets
            .filter((asset) => asset.subtopicId === subtopic.id)
            .map((asset) => ({ path: `modules/${subtopic.id}/${asset.id}.md`, label: asset.title, kind: "markdown" })),
        })),
      },
    ],
  },
  activity: [
    {
      id: "evt4",
      at: "2026-07-06T11:12:00Z",
      title: "Verification completed",
      detail: "18 assets checked; 9 findings require operator attention.",
      tone: "attention",
    },
    {
      id: "evt3",
      at: "2026-07-06T11:10:00Z",
      title: "Student content generated",
      detail: "18 of 18 selected assets generated. Course-content anchors ran first.",
      tone: "good",
    },
    {
      id: "evt2",
      at: "2026-07-06T10:42:00Z",
      title: "Blueprint approved",
      detail: "Asset decisions confirmed across four subtopics.",
      tone: "good",
    },
    {
      id: "evt1",
      at: "2026-07-06T10:10:00Z",
      title: "Two grounding sources approved",
      detail: "One candidate was rejected before ingestion.",
      tone: "neutral",
    },
  ],
};

export function demoWorkspaceFor(courseId: string): Workspace {
  if (courseId === "coffee-acceptance") {
    return {
      ...demoWorkspace,
      course: demoCourses[1],
      stages: demoStages.map((stage) => ({ ...stage, status: "approved", count: undefined })),
      package: { ...demoWorkspace.package, operatorStatus: "ready", unresolvedBlockers: 0 },
    };
  }
  return demoWorkspace;
}
