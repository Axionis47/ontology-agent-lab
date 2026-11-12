import styles from "./task-scope.module.css";
import { Input } from "@/components/ui/input";
import { Textarea } from "@/components/ui/textarea";
import type { ScopeDraft } from "./draft-store";
import { scopeSections } from "./scope-definition";

export function ScopeFields({
  draft,
  onChange,
}: {
  draft: ScopeDraft;
  onChange: (draft: ScopeDraft) => void;
}) {
  return (
    <>
      <section id="scope-name" className={styles.section}>
        <label htmlFor="task-name" className={styles.label}>
          Name <span aria-hidden="true">Required</span>
        </label>
        <p id="task-name-help" className={styles.guidance}>
          Use a short name for this area of work.
        </p>
        <Input
          id="task-name"
          required
          maxLength={100}
          value={draft.name}
          aria-describedby="task-name-help"
          placeholder="e.g. Team meeting coordination"
          onChange={(event) => onChange({ ...draft, name: event.target.value })}
        />
      </section>
      <section id="scope-purpose" className={styles.section}>
        <label htmlFor="task-purpose" className={styles.label}>
          Purpose <span aria-hidden="true">Required</span>
        </label>
        <p id="task-purpose-help" className={styles.guidance}>
          What continuing outcome should this task support?
        </p>
        <p className={styles.hint}>
          Example: Keep team meetings consistent with participant availability
          and scheduling rules.
        </p>
        <Textarea
          id="task-purpose"
          required
          maxLength={5000}
          rows={5}
          value={draft.objective}
          aria-describedby="task-purpose-help"
          onChange={(event) =>
            onChange({ ...draft, objective: event.target.value })
          }
        />
      </section>
      {scopeSections.map(({ key, label, required, guidance, example }) => (
        <section key={key} id={`scope-${key}`} className={styles.section}>
          <label htmlFor={`task-${key}`} className={styles.label}>
            {label}{" "}
            <span aria-hidden="true">{required ? "Required" : "Optional"}</span>
          </label>
          <p id={`task-${key}-help`} className={styles.guidance}>
            {guidance}
          </p>
          <p className={styles.hint}>Example: {example}</p>
          <Textarea
            id={`task-${key}`}
            required={required}
            maxLength={10000}
            rows={6}
            aria-describedby={`task-${key}-help`}
            value={draft.scope[key]}
            onChange={(event) =>
              onChange({
                ...draft,
                scope: { ...draft.scope, [key]: event.target.value },
              })
            }
          />
        </section>
      ))}
    </>
  );
}
