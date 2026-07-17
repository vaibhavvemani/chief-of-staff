import { describe, expect, it } from "vitest";
import { demoWorkspace } from "../../data/demo";
import { briefSectionUpdates } from "./WorkspacePage";

describe("Brief direct-edit merge payloads", () => {
  it("sends only changed fields from the edited section", () => {
    const original = demoWorkspace.brief;
    const edited = {
      ...original,
      audience: "Adults learning to brew coffee at home",
      purpose: "Diagnose common taste problems",
    };

    expect(briefSectionUpdates("learner", edited, original)).toEqual({
      audience: "Adults learning to brew coffee at home",
      purpose: "Diagnose common taste problems",
    });
  });

  it("does not reset unrelated answers or accepted defaults", () => {
    const original = demoWorkspace.brief;
    const edited = {
      ...original,
      mustHaveTopics: [...original.mustHaveTopics, "Taste troubleshooting"],
    };

    expect(briefSectionUpdates("coverage", edited, original)).toEqual({
      mustHaveTopics: [...original.mustHaveTopics, "Taste troubleshooting"],
    });
    expect(briefSectionUpdates("coverage", edited, original)).not.toHaveProperty("language");
    expect(original.intakeState.acceptedDefaultFields).toEqual(["audience", "duration", "level"]);
  });

  it("supports sparse edits to conditional requirements and source materials", () => {
    const original = demoWorkspace.brief;
    const edited = {
      ...original,
      liveTeachingConstraints: "Keep instructor-led blocks under 45 minutes.",
      availableMaterials: [...original.availableMaterials, "https://example.test/coffee"],
    };

    expect(briefSectionUpdates("requirements", edited, original)).toEqual({
      liveTeachingConstraints: "Keep instructor-led blocks under 45 minutes.",
      availableMaterials: [...original.availableMaterials, "https://example.test/coffee"],
    });
    expect(briefSectionUpdates("requirements", edited, original)).not.toHaveProperty("audience");
  });
});
