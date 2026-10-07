import { Route, Routes } from "react-router";

import { Dashboard } from "./pages/Dashboard";
import { NewProject } from "./pages/NewProject";
import { ProjectPage } from "./pages/ProjectPage";
import { RunPage } from "./pages/RunPage";

export function App() {
  return (
    <Routes>
      <Route path="/" element={<Dashboard />} />
      <Route path="/projects/new" element={<NewProject />} />
      <Route path="/projects/:projectId" element={<ProjectPage />} />
      <Route path="/projects/:projectId/runs/:runId" element={<RunPage />} />
    </Routes>
  );
}
