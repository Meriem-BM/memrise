"use client";

import { Card, CardTitle } from "@/components/ui/card";

export function RetrievalsPanel() {
  return (
    <Card>
      <CardTitle>Retrieval Traces</CardTitle>
      <p className="mt-3 text-sm text-slate-600">
        Run a retrieval in the playground to create trace rows with ranking signals and selected
        context.
      </p>
    </Card>
  );
}
