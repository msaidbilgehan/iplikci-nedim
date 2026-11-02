import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, type RenderResult } from "@testing-library/react";
import type { ReactNode } from "react";
import { MemoryRouter } from "react-router";

import { AppProviders } from "../components/AppProviders";

/** ui with fresh server state, a router and the display preferences, as the app gives every screen. */
export function renderScreen(ui: ReactNode, { path = "/" }: { path?: string } = {}): RenderResult {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false }, mutations: { retry: false } } });
  return render(
    <QueryClientProvider client={client}>
      <AppProviders>
        <MemoryRouter initialEntries={[path]}>{ui}</MemoryRouter>
      </AppProviders>
    </QueryClientProvider>,
  );
}
