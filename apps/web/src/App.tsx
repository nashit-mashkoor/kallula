import { useQuery } from "@tanstack/react-query";
import { Route, Routes } from "react-router";

import { apiGet } from "./api/client";

type Health = { status: string };

function Home() {
  const health = useQuery({
    queryKey: ["health"],
    queryFn: () => apiGet<Health>("/health/ready"),
  });

  return (
    <main>
      <h1>Kallula</h1>
      <p>
        API status:{" "}
        {health.isLoading ? "checking..." : health.isError ? "unreachable" : health.data?.status}
      </p>
    </main>
  );
}

export function App() {
  return (
    <Routes>
      <Route path="/" element={<Home />} />
    </Routes>
  );
}
