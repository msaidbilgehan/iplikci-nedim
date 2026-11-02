// The screens and their addresses (architecture §18). Each screen loads when it is first opened; the dashboard is the
// home page.

import { lazy, Suspense, type ReactNode } from "react";
import type { RouteObject } from "react-router";

import { Layout } from "./components/Layout";
import { Loading } from "./components/QueryState";

const DashboardPage = lazy(() => import("./pages/DashboardPage"));
const FeedPage = lazy(() => import("./pages/FeedPage"));
const SystemPage = lazy(() => import("./pages/SystemPage"));
const DocumentsPage = lazy(() => import("./pages/DocumentsPage"));
const SubscriptionsPage = lazy(() => import("./pages/SubscriptionsPage"));
const CalendarPage = lazy(() => import("./pages/CalendarPage"));
const InvoicesPage = lazy(() => import("./pages/InvoicesPage"));
const NotificationsPage = lazy(() => import("./pages/NotificationsPage"));
const ExtensionPage = lazy(() => import("./pages/ExtensionPage"));
const NotFoundPage = lazy(() => import("./pages/NotFoundPage"));

function screen(page: ReactNode): ReactNode {
  return <Suspense fallback={<Loading />}>{page}</Suspense>;
}

export const routes: RouteObject[] = [
  {
    element: <Layout />,
    children: [
      { index: true, element: screen(<DashboardPage />) },
      { path: "akis", element: screen(<FeedPage />) },
      { path: "sistem", element: screen(<SystemPage />) },
      { path: "belgeler", element: screen(<DocumentsPage />) },
      { path: "abonelikler", element: screen(<SubscriptionsPage />) },
      { path: "takvim", element: screen(<CalendarPage />) },
      { path: "faturalar", element: screen(<InvoicesPage />) },
      { path: "bildirimler", element: screen(<NotificationsPage />) },
      { path: "kurulum/eklenti", element: screen(<ExtensionPage />) },
      { path: "*", element: screen(<NotFoundPage />) },
    ],
  },
];
