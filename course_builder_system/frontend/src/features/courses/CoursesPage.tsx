import { useQuery } from "@tanstack/react-query";
import { useState } from "react";
import { Link } from "react-router-dom";
import { getCourses } from "../../api/client";
import { AppBrand } from "../../components/AppBrand";
import { EmptyState, ErrorState, LoadingState } from "../../components/States";
import { StatusBadge } from "../../components/StatusBadge";
import type { CourseSummary, UiStatus } from "../../types";

function relativeDate(value: string): string {
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return "Recently";
  const days = Math.round((date.getTime() - Date.now()) / 86_400_000);
  const formatter = new Intl.RelativeTimeFormat("en", { numeric: "auto" });
  if (Math.abs(days) > 0) return formatter.format(days, "day");
  const hours = Math.round((date.getTime() - Date.now()) / 3_600_000);
  return formatter.format(hours, "hour");
}

function DashboardMetric({ value, label, tone }: { value: number; label: string; tone?: UiStatus }) {
  return (
    <div className={`dashboard-metric ${tone ? `metric-${tone}` : ""}`}>
      <strong>{value}</strong>
      <span>{label}</span>
    </div>
  );
}

function CourseCard({ course }: { course: CourseSummary }) {
  const stageLabel = course.currentStage.replaceAll("-", " ");
  return (
    <Link to={`/courses/${course.courseId}/${course.currentStage}`} className="course-card">
      <div className="course-card-topline">
        <StatusBadge status={course.status} count={course.attentionCount} />
        <span className="course-updated">Updated {relativeDate(course.updatedAt)}</span>
      </div>
      <div className="course-card-copy">
        <span className="eyebrow">{course.subject}</span>
        <h3>{course.title}</h3>
        <p>{course.nextAction}</p>
      </div>
      <div className="course-progress" aria-label={`${course.progress}% complete`}>
        <div className="progress-meta">
          <span>{stageLabel}</span>
          <span>{course.approvedStages} of {course.totalStages} stages approved</span>
        </div>
        <div className="progress-track"><span style={{ width: `${course.progress}%` }} /></div>
      </div>
      <div className="course-card-action">
        <span>{course.status === "requires_attention" ? "Open attention queue" : "Open workspace"}</span>
        <span aria-hidden="true">→</span>
      </div>
    </Link>
  );
}

export function CoursesPage() {
  const query = useQuery({ queryKey: ["courses"], queryFn: getCourses });
  const [filter, setFilter] = useState<"all" | "attention" | "ready">("all");

  if (query.isLoading) return <LoadingState label="Opening Course Builder Studio" />;
  if (query.isError) return <ErrorState message={query.error.message} onRetry={() => void query.refetch()} />;

  const courses = query.data?.courses ?? [];
  const attention = courses.filter((course) => course.status === "requires_attention").length;
  const active = courses.filter((course) => !["approved", "locked"].includes(course.status)).length;
  const ready = courses.filter((course) => course.status === "approved").length;
  const visibleCourses = courses.filter((course) =>
    filter === "all"
      ? true
      : filter === "attention"
        ? course.status === "requires_attention"
        : course.status === "approved",
  );

  return (
    <div className="dashboard-shell">
      <header className="dashboard-header">
        <AppBrand />
        <nav className="top-nav" aria-label="Primary navigation">
          <a href="#courses" className="active">Courses</a>
          <button className="plain-nav-button" type="button" disabled title="Settings are deferred from the single-director MVP">Settings</button>
        </nav>
        <Link to="/courses/new" className="button button-primary button-with-arrow">New course <span aria-hidden="true">+</span></Link>
      </header>

      <main className="dashboard-main" id="courses">
        <section className="dashboard-hero">
          <div>
            <span className="eyebrow">Production overview</span>
            <h1>Courses move forward<br />one clear decision at a time.</h1>
            <p>Review agent proposals, inspect their evidence, and resolve only the items that need your judgment.</p>
          </div>
          <div className="dashboard-metrics" aria-label="Course status summary">
            <DashboardMetric value={active} label="In production" />
            <DashboardMetric value={attention} label="Need attention" tone="requires_attention" />
            <DashboardMetric value={ready} label="Ready" tone="approved" />
          </div>
        </section>

        {query.data?.demoMode ? (
          <div className="demo-notice" role="status">
            <span className="demo-pulse" aria-hidden="true" />
            <div><strong>Previewing the studio with representative course data.</strong><span> Start the Course Builder API to work with your local artifacts.</span></div>
          </div>
        ) : null}

        <section className="course-section" aria-labelledby="course-heading">
          <div className="section-heading-row">
            <div>
              <span className="eyebrow">Your workspace</span>
              <h2 id="course-heading">All courses</h2>
            </div>
            <div className="segmented-control" aria-label="Filter courses">
              <button className={filter === "all" ? "active" : ""} onClick={() => setFilter("all")}>All</button>
              <button className={filter === "attention" ? "active" : ""} onClick={() => setFilter("attention")}>Attention</button>
              <button className={filter === "ready" ? "active" : ""} onClick={() => setFilter("ready")}>Ready</button>
            </div>
          </div>
          {courses.length ? (
            <div className="course-grid">
              {visibleCourses.map((course) => <CourseCard key={course.courseId} course={course} />)}
              <Link to="/courses/new" className="new-course-card">
                <span className="new-course-plus" aria-hidden="true">+</span>
                <strong>Start another course</strong>
                <span>Turn a sparse subject request into a reviewable course workspace.</span>
              </Link>
            </div>
          ) : (
            <EmptyState
              title="No courses yet"
              description="Start with a subject and the agent will prepare a structured Brief for your review."
              action={<Link className="button button-primary" to="/courses/new">Create your first course</Link>}
            />
          )}
        </section>
      </main>
      <footer className="dashboard-footer"><span>Course Builder Studio</span><span>Local prototype workspace</span></footer>
    </div>
  );
}
