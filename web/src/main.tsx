import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { StrictMode } from "react";
import { createRoot } from "react-dom/client";
import { createBrowserRouter, RouterProvider } from "react-router";

import { ApiError } from "./api/client";
import { AppProviders } from "./components/AppProviders";
import "./i18n";
import { checkOnReturn, reloadOnUpdate } from "./lib/appUpdate";
import { applyTheme, isDark, readTheme, systemIsDark } from "./lib/preferences";
import { routes } from "./routes";
import "./index.css";

// The remembered theme goes on <html> before anything renders. This module does it: the CSP allows no inline script.
applyTheme(isDark(readTheme(), systemIsDark()));

// After an update the new build shows at once, in a tab kept open too (lib/appUpdate.ts). A page served over plain
// HTTP from another computer has no service workers.
const workers = "serviceWorker" in navigator ? navigator.serviceWorker : undefined;
reloadOnUpdate(workers, () => window.location.reload());
checkOnReturn(workers, document);

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
        <AppProviders>
          <RouterProvider router={createBrowserRouter(routes)} />
        </AppProviders>
      </QueryClientProvider>
    </StrictMode>,
  );
}
