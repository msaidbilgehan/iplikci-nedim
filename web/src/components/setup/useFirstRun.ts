// The first run (F17): with nothing set up yet — no name, no e-mail, no document — the app opens on the setup wizard
// instead of an empty dashboard. Once a browser session: a user who leaves the wizard for the dashboard stays there.

import { useEffect } from "react";
import { useLocation, useNavigate } from "react-router";

import { useSetup } from "../../api/queries";

const OPENED = "iplikci.kurulum"; // sessionStorage: the wizard was opened for the first run in this session

export function useFirstRun(): void {
  const firstRun = useSetup().data?.first_run === true;
  const { pathname } = useLocation();
  const navigate = useNavigate();
  useEffect(() => {
    if (firstRun && pathname === "/" && sessionStorage.getItem(OPENED) === null) {
      sessionStorage.setItem(OPENED, "1");
      void navigate("/kurulum", { replace: true });
    }
  }, [firstRun, pathname, navigate]);
}
