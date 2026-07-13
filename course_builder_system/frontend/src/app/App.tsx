import { Navigate, Route, Routes } from "react-router-dom";
import { CoursesPage } from "../features/courses/CoursesPage";
import { NewCoursePage } from "../features/courses/NewCoursePage";
import { WorkspacePage } from "../features/workspace/WorkspacePage";

export function App() {
  return (
    <Routes>
      <Route path="/" element={<Navigate to="/courses" replace />} />
      <Route path="/courses" element={<CoursesPage />} />
      <Route path="/courses/new" element={<NewCoursePage />} />
      <Route path="/courses/:courseId" element={<WorkspacePage />} />
      <Route path="/courses/:courseId/:stage" element={<WorkspacePage />} />
      <Route path="*" element={<Navigate to="/courses" replace />} />
    </Routes>
  );
}

