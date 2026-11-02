import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, type RenderResult } from "@testing-library/react";
import { type ReactNode, useLayoutEffect } from "react";
import { MemoryRouter, Route, Routes, useLocation } from "react-router";

import { AppProviders } from "../components/AppProviders";

interface ScreenOptions {
  path?: string; // the address the screen opens at, its query included
  route?: string; // the route's pattern, for a screen that reads its address's parameters ("/hesaplar/:id")
}

export interface ScreenResult extends RenderResult {
  client: QueryClient; // the screen's server state: a test refreshes it as the event stream would
  location: () => string; // the address the screen is at now, its query included
}

/** ui with fresh server state, a router and the display preferences, as the app gives every screen. */
export function renderScreen(ui: ReactNode, { path = "/", route }: ScreenOptions = {}): ScreenResult {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false }, mutations: { retry: false } } });
  const where = { current: path };
  const result = render(
    <QueryClientProvider client={client}>
      <AppProviders>
        <MemoryRouter initialEntries={[path]}>
          <Address into={where} />
          {route ? (
            <Routes>
              <Route path={route} element={ui} />
            </Routes>
          ) : (
            ui
          )}
        </MemoryRouter>
      </AppProviders>
    </QueryClientProvider>,
  );
  return { ...result, client, location: () => where.current };
}

/** Keeps the router's address where the test can read it. */
function Address({ into }: { into: { current: string } }) {
  const location = useLocation();
  useLayoutEffect(() => {
    into.current = `${location.pathname}${location.search}`;
  }, [into, location]);
  return null;
}
