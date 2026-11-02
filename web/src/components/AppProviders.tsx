// What every screen stands in besides the router and the server state: the display preferences and the tooltips'
// timing. The app and the tests wrap the screens in it alike (main.tsx, test/render.tsx).

import * as Tooltip from "@radix-ui/react-tooltip";
import type { ReactNode } from "react";

import { ThemeProvider, ViewProvider } from "./Preferences";

export function AppProviders({ children }: { children: ReactNode }) {
  return (
    <ThemeProvider>
      <ViewProvider>
        {/* A hint opens after a short rest of the pointer, and at once on the next one. */}
        <Tooltip.Provider delayDuration={300} skipDelayDuration={300}>
          {children}
        </Tooltip.Provider>
      </ViewProvider>
    </ThemeProvider>
  );
}
