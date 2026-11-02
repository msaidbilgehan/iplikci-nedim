// A card of the dashboard (F06): its title, and the screen it leads to. In the simple view the service's sentence on
// what the card shows comes first with the link as its next step; in the detailed view the link stands beside the
// title and the card's tables follow. A card whose sentence the first row already says shows only the link.

import type { ReactNode } from "react";

import { Detailed } from "../Preferences";
import { Card } from "../ui/Card";
import { NextStep, Say, type Step } from "../ui/Say";

interface DashboardCardProps {
  title: string;
  say: string; // the plain view's sentence, from the service
  next: Step;
  quiet?: boolean; // the dashboard's first row says it already: no sentence, the link beside the title in both views
  className?: string;
  children?: ReactNode;
}

export function DashboardCard({ title, say, next, quiet = false, className, children }: DashboardCardProps) {
  return (
    <Card
      title={title}
      action={
        quiet ? (
          <NextStep step={next} />
        ) : (
          <Detailed>
            <NextStep step={next} />
          </Detailed>
        )
      }
      {...(className ? { className } : {})}
    >
      {quiet ? null : <Say next={next}>{say}</Say>}
      {children}
    </Card>
  );
}
