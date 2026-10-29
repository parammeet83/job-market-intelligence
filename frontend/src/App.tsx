import { Link, Route, Routes } from "react-router-dom";
import { Layout } from "./components/Layout";
import { EmptyState } from "./components/ui";
import { Jobs } from "./pages/Jobs";
import { LocationsRoles } from "./pages/LocationsRoles";
import { Methodology } from "./pages/Methodology";
import { Overview } from "./pages/Overview";
import { Salaries } from "./pages/Salaries";
import { Skills } from "./pages/Skills";
import { Sources } from "./pages/Sources";

export function App() {
  return (
    <Routes>
      <Route element={<Layout />}>
        <Route index element={<Overview />} />
        <Route path="jobs" element={<Jobs />} />
        <Route path="skills" element={<Skills />} />
        <Route path="salaries" element={<Salaries />} />
        <Route path="locations-roles" element={<LocationsRoles />} />
        <Route path="sources" element={<Sources />} />
        <Route path="methodology" element={<Methodology />} />
        <Route
          path="*"
          element={
            <EmptyState title="Page not found">
              <Link to="/" className="text-sky hover:underline">Back to the overview</Link>
            </EmptyState>
          }
        />
      </Route>
    </Routes>
  );
}
