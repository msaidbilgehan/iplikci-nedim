import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { StrictMode } from "react";
import { createRoot } from "react-dom/client";
import { createBrowserRouter, RouterProvider } from "react-router";

import { ApiError } from "./api/client";
import { routes } from "./routes";
import "./index.css";

const queries = new QueryClient({
  defaultOptions: {
    queries: {
      // An ended session does not come back by asking again.
      retry: (count, error) => !(error instanceof ApiError && error.signedOut) && count < 2,
      refetchOnWindowFocus: true,
    },
  },
});

const root = document.getElementById("root");
if (root) {
  createRoot(root).render(
    <StrictMode>
      <QueryClientProvider client={queries}>
        <RouterProvider router={createBrowserRouter(routes)} />
      </QueryClientProvider>
    </StrictMode>,
  );
}
