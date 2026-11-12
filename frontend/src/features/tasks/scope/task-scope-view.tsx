import styles from "./task-scope.module.css";
import type { TaskScope } from "@/lib/api";
import { scopeSections } from "./scope-definition";

export function ScopeText({ text }: { text?: string }) {
  return text?.trim() ? (
    <p className={styles.text}>{text}</p>
  ) : (
    <p className="text-sm text-muted-foreground">Unspecified</p>
  );
}

export function TaskScopeView({
  objective,
  scope,
}: {
  objective?: string;
  scope?: TaskScope | null;
}) {
  return (
    <div className="space-y-6">
      {objective !== undefined && (
        <section
          id="scope-purpose"
          className={styles.section}
          aria-labelledby="scope-purpose-title"
        >
          <h2 id="scope-purpose-title" className="section-title">
            Purpose
          </h2>
          <ScopeText text={objective} />
        </section>
      )}
      {scopeSections.map(({ key, label }) => (
        <section
          key={key}
          id={`scope-${key}`}
          className={styles.section}
          aria-labelledby={`scope-${key}-title`}
        >
          <h2 id={`scope-${key}-title`} className="section-title">
            {label}
          </h2>
          <ScopeText text={scope?.[key]} />
        </section>
      ))}
      <section
        id="scope-examples"
        className={styles.section}
        aria-labelledby="scope-examples-title"
      >
        <h2 id="scope-examples-title" className="section-title">
          Example cases
        </h2>
        {scope?.examples?.length ? (
          scope.examples.map((example, index) => (
            <article
              key={index}
              className={styles.example}
              aria-label={`Example ${index + 1}`}
            >
              <h3 className="font-medium">Example {index + 1}</h3>
              <dl className="space-y-4 text-sm">
                <div>
                  <dt className="text-muted-foreground">
                    Situation and request
                  </dt>
                  <dd>
                    <ScopeText text={example.situation} />
                  </dd>
                </div>
                <div>
                  <dt className="text-muted-foreground">Expected behavior</dt>
                  <dd>
                    <ScopeText text={example.expected_behavior} />
                  </dd>
                </div>
                <div>
                  <dt className="text-muted-foreground">Prohibited behavior</dt>
                  <dd>
                    <ScopeText text={example.prohibited_behavior} />
                  </dd>
                </div>
              </dl>
            </article>
          ))
        ) : (
          <p className="text-sm text-muted-foreground">Unspecified</p>
        )}
      </section>
    </div>
  );
}
