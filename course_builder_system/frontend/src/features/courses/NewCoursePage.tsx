import { useMutation } from "@tanstack/react-query";
import { FormEvent, useMemo, useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { ApiError, createCourse } from "../../api/client";
import { AppBrand } from "../../components/AppBrand";

function slugify(value: string): string {
  return value
    .toLowerCase()
    .trim()
    .replace(/[^a-z0-9]+/g, "-")
    .replace(/^-|-$/g, "")
    .slice(0, 48);
}

export function NewCoursePage() {
  const navigate = useNavigate();
  const [subject, setSubject] = useState("");
  const [description, setDescription] = useState("");
  const [constraints, setConstraints] = useState("");
  const [sources, setSources] = useState("");
  const [mode, setMode] = useState<"deterministic" | "live">("deterministic");
  const courseId = useMemo(() => slugify(subject) || "your-course", [subject]);
  const mutation = useMutation({
    mutationFn: createCourse,
    onSuccess: ({ courseId: createdId }) => navigate(`/courses/${createdId || courseId}/brief`),
  });

  async function submit(event: FormEvent) {
    event.preventDefault();
    if (!subject.trim()) return;
    try {
      await mutation.mutateAsync({
        subject: subject.trim(),
        description: description.trim() || undefined,
        constraints: constraints.trim() || undefined,
        sourceUrls: sources.split("\n").map((value) => value.trim()).filter(Boolean),
      });
    } catch (error) {
      if (error instanceof ApiError && error.status === 0) {
        navigate(`/courses/${courseId}/brief?preview=1&mode=${mode}`);
      }
    }
  }

  return (
    <div className="create-shell">
      <header className="create-header">
        <AppBrand />
        <Link to="/courses" className="button button-quiet">Cancel</Link>
      </header>
      <main className="create-main">
        <section className="create-intro">
          <span className="eyebrow">New course</span>
          <h1>Give the agent a clear starting point.</h1>
          <p>You do not need a finished specification. A subject is enough to create a first Brief; the workspace will surface assumptions for you to approve or correct.</p>
          <ol className="create-steps" aria-label="Creation steps">
            <li className="active"><span>1</span><div><strong>Starting request</strong><small>Subject and useful context</small></div></li>
            <li><span>2</span><div><strong>Brief review</strong><small>Confirm scope and assumptions</small></div></li>
            <li><span>3</span><div><strong>Build the course</strong><small>Approve each structured stage</small></div></li>
          </ol>
        </section>
        <form className="create-form" onSubmit={submit}>
          <div className="form-heading">
            <span className="step-number">01</span>
            <div><h2>Starting request</h2><p>Keep it sparse or add the context you already know.</p></div>
          </div>
          <label className="form-field">
            <span>What should this course teach? <em>Required</em></span>
            <input
              autoFocus
              required
              value={subject}
              onChange={(event) => setSubject(event.target.value)}
              placeholder="e.g. Coffee making for complete beginners"
            />
          </label>
          <label className="form-field">
            <span>What should the course help learners do?</span>
            <textarea
              value={description}
              onChange={(event) => setDescription(event.target.value)}
              placeholder="A short description of the practical result, audience, or business need."
              rows={4}
            />
            <small>Optional. The Brief will make any missing assumptions visible.</small>
          </label>
          <div className="form-grid-two">
            <label className="form-field">
              <span>Known constraints</span>
              <textarea
                value={constraints}
                onChange={(event) => setConstraints(event.target.value)}
                placeholder="Duration, delivery mode, jurisdiction…"
                rows={4}
              />
            </label>
            <label className="form-field">
              <span>Known source links</span>
              <textarea
                value={sources}
                onChange={(event) => setSources(event.target.value)}
                placeholder={"https://…\nOne link per line"}
                rows={4}
              />
            </label>
          </div>
          <fieldset className="run-mode-fieldset">
            <legend>Build mode</legend>
            <label className={mode === "deterministic" ? "selected" : ""}>
              <input type="radio" name="mode" value="deterministic" checked={mode === "deterministic"} onChange={() => setMode("deterministic")} />
              <span><strong>Deterministic preview</strong><small>Fast local fixtures for reviewing workflow and interface behavior.</small></span>
            </label>
            <label className={mode === "live" ? "selected" : ""}>
              <input type="radio" name="mode" value="live" checked={mode === "live"} onChange={() => setMode("live")} />
              <span><strong>Live agent run</strong><small>Uses configured research and model services. Credentials stay on the server.</small></span>
            </label>
          </fieldset>
          {mutation.isError && !(mutation.error instanceof ApiError && mutation.error.status === 0) ? (
            <div className="form-error" role="alert"><strong>Couldn’t create the course.</strong> {mutation.error.message}</div>
          ) : null}
          <div className="create-submit-row">
            <div><span>Course ID preview</span><code>{courseId}</code></div>
            <button className="button button-primary button-large" disabled={!subject.trim() || mutation.isPending}>
              {mutation.isPending ? "Creating workspace…" : "Create Brief"} <span aria-hidden="true">→</span>
            </button>
          </div>
        </form>
      </main>
    </div>
  );
}

