"""
Course Builder - referential-integrity check (Handoff Section 7.1 / 4.8).

The TOC is the single source of truth for structure (Section 4.2): every other
artifact REFERENCES TOC ids and never re-encodes the module/subtopic tree. This
module is a cheap guard that the reference graph (Section 4.8) actually holds on
disk - that no Blueprint / Content Package / Lesson Plan reference dangles.

It reads only what is on disk via the orchestrator's loader, so it needs no
changes to orchestrator.py. The engine stays oblivious to body shapes; this
contract check lives outside it on purpose.

Checks performed:
  - Blueprint.allocations[].node_id        -> a TOC module OR subtopic id
  - Blueprint.dependencies[].module_id     -> a TOC module id
  - Blueprint.dependencies[].prerequisites -> TOC module ids
  - Blueprint.speakers[].placed_at         -> a TOC module OR subtopic id
  - Content Package.subtopics[].subtopic_id-> a TOC subtopic id
  - Content Package asset.sources[]        -> a Domain Model grounding-source id
  - Lesson Plan.sessions[].covers[].subtopic_id -> a TOC subtopic id
  - Domain Model.concepts[].depends_on     -> a Domain Model concept id
"""

from __future__ import annotations

from orchestrator import load_artifact


def _toc_ids(toc_body: dict) -> tuple[set[str], set[str]]:
    """Return (module_ids, subtopic_ids) declared by the TOC."""
    modules: set[str] = set()
    subtopics: set[str] = set()
    for m in toc_body.get("modules", []):
        modules.add(m["id"])
        for s in m.get("subtopics", []):
            subtopics.add(s["id"])
    return modules, subtopics


def check_referential_integrity(course_id: str) -> list[str]:
    """Validate cross-artifact references for one course.

    Returns a list of human-readable problems; an empty list means every
    reference resolves. Artifacts not yet on disk are simply skipped, so this
    is safe to run mid-pipeline (after the TOC exists) or at the end.
    """
    problems: list[str] = []

    toc = load_artifact(course_id, "toc")
    if toc is None:
        return [f"no TOC on disk for course '{course_id}' - cannot check references"]

    module_ids, subtopic_ids = _toc_ids(toc["body"])
    all_nodes = module_ids | subtopic_ids

    # Domain Model: build grounding/concept id universes; check concept graph.
    grounding_ids: set[str] = set()
    concept_ids: set[str] = set()
    dm = load_artifact(course_id, "domain_model")
    if dm is not None:
        for category in dm["body"].get("grounding_sources", []):
            for item in category.get("items", []):
                grounding_ids.add(item["id"])
        concept_ids = {c["id"] for c in dm["body"].get("concepts", [])}
        for c in dm["body"].get("concepts", []):
            for dep in c.get("depends_on", []):
                if dep not in concept_ids:
                    problems.append(
                        f"domain_model: concept '{c['id']}' depends_on missing "
                        f"concept '{dep}'"
                    )

    # Blueprint references.
    bp = load_artifact(course_id, "blueprint")
    if bp is not None:
        for a in bp["body"].get("allocations", []):
            if a["node_id"] not in all_nodes:
                problems.append(
                    f"blueprint: allocation node_id '{a['node_id']}' is not a "
                    f"TOC node"
                )
        for dep in bp["body"].get("dependencies", []):
            if dep["module_id"] not in module_ids:
                problems.append(
                    f"blueprint: dependency module_id '{dep['module_id']}' is "
                    f"not a TOC module"
                )
            for pr in dep.get("prerequisites", []):
                if pr not in module_ids:
                    problems.append(
                        f"blueprint: prerequisite '{pr}' is not a TOC module"
                    )
        for sp in bp["body"].get("speakers", []):
            if sp.get("placed_at") not in all_nodes:
                problems.append(
                    f"blueprint: speaker '{sp.get('id')}' placed_at "
                    f"'{sp.get('placed_at')}' is not a TOC node"
                )

    # Content Package references.
    cp = load_artifact(course_id, "content_package")
    if cp is not None:
        for st in cp["body"].get("subtopics", []):
            if st["subtopic_id"] not in subtopic_ids:
                problems.append(
                    f"content_package: subtopic_id '{st['subtopic_id']}' is not "
                    f"a TOC subtopic"
                )
            for asset in st.get("assets", []):
                for src in asset.get("sources", []):
                    if src not in grounding_ids:
                        problems.append(
                            f"content_package: asset '{asset['id']}' source "
                            f"'{src}' is not a Domain Model grounding id"
                        )

    # Lesson Plan references.
    lp = load_artifact(course_id, "lesson_plan")
    if lp is not None:
        for sess in lp["body"].get("sessions", []):
            for cov in sess.get("covers", []):
                if cov["subtopic_id"] not in subtopic_ids:
                    problems.append(
                        f"lesson_plan: session '{sess.get('id')}' covers "
                        f"'{cov['subtopic_id']}' which is not a TOC subtopic"
                    )

    return problems


def report(course_id: str) -> bool:
    """Run the check and print a one-line verdict (plus any problems).

    Returns True if every reference resolves, False otherwise.
    """
    problems = check_referential_integrity(course_id)
    if problems:
        print(f"\n[integrity] FAIL - {len(problems)} dangling reference(s) "
              f"in '{course_id}':")
        for p in problems:
            print(f"  - {p}")
        return False
    print(f"\n[integrity] OK - all cross-artifact references resolve for "
          f"'{course_id}'")
    return True


if __name__ == "__main__":
    import sys

    cid = sys.argv[1] if len(sys.argv) > 1 else "frm-demo"
    ok = report(cid)
    raise SystemExit(0 if ok else 1)
