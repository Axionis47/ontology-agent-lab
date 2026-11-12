import { Plus, Trash2 } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Textarea } from "@/components/ui/textarea";
import type { ScopeExample } from "@/lib/api";
import styles from "./task-scope.module.css";

const exampleFields = [
  [
    "situation",
    "Situation and request",
    "Include the starting state and the user's request.",
  ],
  [
    "expected_behavior",
    "Expected behavior",
    "Describe the correct action or result.",
  ],
  [
    "prohibited_behavior",
    "Prohibited behavior",
    "Describe what must not happen in this situation.",
  ],
] as const;

export function ScopeExamples({
  examples,
  onChange,
  idPrefix = "scope",
}: {
  examples: ScopeExample[];
  onChange: (examples: ScopeExample[]) => void;
  idPrefix?: string;
}) {
  function updateExample(
    index: number,
    key: keyof ScopeExample,
    value: string,
  ) {
    onChange(
      examples.map((example, i) =>
        i === index ? { ...example, [key]: value } : example,
      ),
    );
  }

  return (
    <section
      id={`${idPrefix}-examples`}
      className={styles.section}
      aria-labelledby={`${idPrefix}-examples-title`}
    >
      <h2 id={`${idPrefix}-examples-title`} className={styles.label}>
        Example cases <span aria-hidden="true">Optional</span>
      </h2>
      <p className={styles.guidance}>
        Include ordinary situations and cases where an action must not occur.
        State the correct alternative, such as asking for missing information.
      </p>
      <p className={styles.hint}>
        These examples provide guidance for future construction. They are not
        executable evals yet.
      </p>
      {examples.map((example, index) => (
        <fieldset key={index} className={styles.example}>
          <legend className="px-2 text-sm">Example {index + 1}</legend>
          {exampleFields.map(([key, label, guidance]) => (
            <div key={key} className="space-y-2">
              <label
                htmlFor={`${idPrefix}-example-${index}-${key}`}
                className={styles.label}
              >
                {label}{" "}
                <span aria-hidden="true">
                  {key === "prohibited_behavior" ? "Optional" : "Required"}
                </span>
              </label>
              <p
                id={`${idPrefix}-example-${index}-${key}-help`}
                className={styles.guidance}
              >
                {guidance}
              </p>
              <Textarea
                id={`${idPrefix}-example-${index}-${key}`}
                aria-describedby={`${idPrefix}-example-${index}-${key}-help`}
                required={key !== "prohibited_behavior"}
                maxLength={10000}
                rows={3}
                value={example[key] ?? ""}
                onChange={(event) =>
                  updateExample(index, key, event.target.value)
                }
              />
            </div>
          ))}
          <Button
            type="button"
            variant="ghost"
            aria-label={`Remove example ${index + 1}`}
            onClick={() => onChange(examples.filter((_, i) => i !== index))}
          >
            <Trash2 /> Remove example
          </Button>
        </fieldset>
      ))}
      <Button
        type="button"
        variant="outline"
        onClick={() =>
          onChange([
            ...examples,
            { situation: "", expected_behavior: "", prohibited_behavior: "" },
          ])
        }
      >
        <Plus /> Add example
      </Button>
    </section>
  );
}
