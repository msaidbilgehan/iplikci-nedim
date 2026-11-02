// What every screen stands in besides the router and the server state: the display preferences. The app and the tests
// wrap the screens in it alike (main.tsx, test/render.tsx).

import type { ReactNode } from "react";

import { ThemeProvider, ViewProvider } from "./Preferences";

export function AppProviders({ children }: { children: ReactNode }) {
  return (
    <ThemeProvider>
      <ViewProvider>{children}</ViewProvider>
    </ThemeProvider>
  );
}
