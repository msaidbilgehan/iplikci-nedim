// A card of the dashboard (F06): its title, and the screen it leads to. In the simple view the service's sentence on
// what the card shows comes first with the link as its next step; in the detailed view the link stands beside the
// title and the card's tables follow.

import type { ReactNode } from "react";

import { Detailed } from "../Preferences";
import { Card } from "../ui/Card";
import { NextStep, Say, type Step } from "../ui/Say";

interface DashboardCardProps {
  title: string;
  say: string; // the plain view's sentence, from the service
  next: Step;
  className?: string;
  children?: ReactNode;
}

export function DashboardCard({ title, say, next, className, children }: DashboardCardProps) {
  return (
    <Card
      title={title}
      action={
        <Detailed>
          <NextStep step={next} />
        </Detailed>
      }
      {...(className ? { className } : {})}
    >
      <Say next={next}>{say}</Say>
      {children}
    </Card>
  );
}
