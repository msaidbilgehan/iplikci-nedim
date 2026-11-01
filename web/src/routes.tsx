// The screens and their addresses (architecture §18). Each screen loads when it is first opened. Until the
// dashboard comes (Phase 6), the home address shows the System screen.

import { lazy, Suspense, type ReactNode } from "react";
import { Navigate, type RouteObject } from "react-router";

import { Layout } from "./components/Layout";
import { Loading } from "./components/QueryState";

const SystemPage = lazy(() => import("./pages/SystemPage"));
const DocumentsPage = lazy(() => import("./pages/DocumentsPage"));
const ExtensionPage = lazy(() => import("./pages/ExtensionPage"));
const NotFoundPage = lazy(() => import("./pages/NotFoundPage"));

function screen(page: ReactNode): ReactNode {
  return <Suspense fallback={<Loading />}>{page}</Suspense>;
}

export const routes: RouteObject[] = [
  {
    element: <Layout />,
    children: [
      { index: true, element: <Navigate to="/sistem" replace /> },
      { path: "sistem", element: screen(<SystemPage />) },
      { path: "belgeler", element: screen(<DocumentsPage />) },
      { path: "kurulum/eklenti", element: screen(<ExtensionPage />) },
      { path: "*", element: screen(<NotFoundPage />) },
    ],
  },
];
