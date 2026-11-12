import { Input } from "@/components/ui/input";
import type { TrainingLimits } from "@/lib/api";

export const trainingDefaults: TrainingLimits = {
  cost_usd: "",
  model_calls: 40,
  mcp_calls: 30,
  max_steps: 12,
  max_rounds: 3,
  active_seconds: 600,
};

const fields = [
  ["cost_usd", "Maximum model cost (USD)", 10, "0.000001"],
  ["model_calls", "Maximum model calls", 200, "1"],
  ["mcp_calls", "Maximum MCP calls", 200, "1"],
  ["max_steps", "Maximum steps per episode", 50, "1"],
  ["max_rounds", "Maximum training rounds", 10, "1"],
  ["active_seconds", "Maximum active runtime (seconds)", 7200, "1"],
] as const;

export function RunLimits({
  value,
  onChange,
  inference = false,
}: {
  value: TrainingLimits;
  onChange: (value: TrainingLimits) => void;
  inference?: boolean;
}) {
  return (
    <fieldset className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
      <legend className="mb-3 text-xs font-medium">Run limits</legend>
      {fields
        .filter(([key]) => !inference || key !== "max_rounds")
        .map(([key, label, max, step]) => (
          <label key={key} className="space-y-2 text-xs">
            <span>{label}</span>
            <Input
              type="number"
              required
              min={key === "cost_usd" ? 0.000001 : 1}
              max={max}
              step={step}
              value={value[key]}
              onChange={(event) =>
                onChange({
                  ...value,
                  [key]:
                    key === "cost_usd"
                      ? event.target.value
                      : Number(event.target.value),
                })
              }
            />
          </label>
        ))}
    </fieldset>
  );
}
