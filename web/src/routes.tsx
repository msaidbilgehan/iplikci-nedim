// The screens and their addresses (architecture §18). Each screen loads when it is first opened; the dashboard is the
// home page.

import { lazy, Suspense, type ReactNode } from "react";
import type { RouteObject } from "react-router";

import { Layout } from "./components/Layout";
import { Loading } from "./components/QueryState";

const DashboardPage = lazy(() => import("./pages/DashboardPage"));
const FeedPage = lazy(() => import("./pages/FeedPage"));
const TransactionsPage = lazy(() => import("./pages/TransactionsPage"));
const AccountsPage = lazy(() => import("./pages/AccountsPage"));
const AccountPage = lazy(() => import("./pages/AccountPage"));
const SystemPage = lazy(() => import("./pages/SystemPage"));
const DocumentsPage = lazy(() => import("./pages/DocumentsPage"));
const DocumentPage = lazy(() => import("./pages/DocumentPage"));
const SubscriptionsPage = lazy(() => import("./pages/SubscriptionsPage"));
const CalendarPage = lazy(() => import("./pages/CalendarPage"));
const InsightsPage = lazy(() => import("./pages/InsightsPage"));
const FxPage = lazy(() => import("./pages/FxPage"));
const InvoicesPage = lazy(() => import("./pages/InvoicesPage"));
const NotificationsPage = lazy(() => import("./pages/NotificationsPage"));
const ExtensionPage = lazy(() => import("./pages/ExtensionPage"));
const MonthEndPage = lazy(() => import("./pages/MonthEndPage"));
const MonthPage = lazy(() => import("./pages/MonthPage"));
const RulesPage = lazy(() => import("./pages/RulesPage"));
const TodoPage = lazy(() => import("./pages/TodoPage"));
const SetupPage = lazy(() => import("./pages/SetupPage"));
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
      { path: "hesaplar", element: screen(<AccountsPage />) },
      { path: "hesaplar/:id", element: screen(<AccountPage />) },
      { path: "islemler", element: screen(<TransactionsPage />) },
      { path: "sistem", element: screen(<SystemPage />) },
      { path: "belgeler", element: screen(<DocumentsPage />) },
      { path: "belgeler/:id", element: screen(<DocumentPage />) },
      { path: "abonelikler", element: screen(<SubscriptionsPage />) },
      { path: "takvim", element: screen(<CalendarPage />) },
      { path: "degerlendirme", element: screen(<InsightsPage />) },
      { path: "doviz", element: screen(<FxPage />) },
      { path: "faturalar", element: screen(<InvoicesPage />) },
      { path: "bildirimler", element: screen(<NotificationsPage />) },
      { path: "kurulum/eklenti", element: screen(<ExtensionPage />) },
      { path: "ay-sonu", element: screen(<MonthEndPage />) },
      { path: "ay-sonu/:ay", element: screen(<MonthPage />) },
      { path: "kurallar", element: screen(<RulesPage />) },
      { path: "yapilacaklar", element: screen(<TodoPage />) },
      { path: "kurulum", element: screen(<SetupPage />) },
      { path: "*", element: screen(<NotFoundPage />) },
    ],
  },
];
