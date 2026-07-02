import { Card, CardTitle } from "@/components/ui/card";

export function EvaluationsPanel() {
  return (
    <Card>
      <CardTitle>Evaluations</CardTitle>
      <p className="mt-3 text-sm text-slate-600">
        No benchmark run has been recorded. Evaluation datasets and metric contracts are available
        in the Python package.
      </p>
    </Card>
  );
}
