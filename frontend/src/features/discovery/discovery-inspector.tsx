"use client";

import { useRef, useSyncExternalStore, type ReactNode } from "react";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import type { DiscoveryDetail, EvidenceRef } from "@/lib/api";
import { ModelingReasons, modelingChoices } from "./discovery-modeling";
import {
  adaptSchema,
  evidenceIssues,
  resolveEvidence,
  selectedRecord,
  selectionKey,
  type Selection,
} from "./schema-adapter";

function subscribe(listener: () => void) {
  const media = window.matchMedia("(min-width: 1024px)");
  media.addEventListener("change", listener);
  return () => media.removeEventListener("change", listener);
}
const desktopSnapshot = () => window.matchMedia("(min-width: 1024px)").matches;

function SavedValue({
  value,
  depth = 0,
}: {
  value: unknown;
  depth?: number;
}): ReactNode {
  if (value === undefined) return <p>Reference unavailable.</p>;
  if (value === null)
    return <span className="text-muted-foreground">Not supplied</span>;
  if (typeof value !== "object")
    return (
      <span className="whitespace-pre-wrap break-words">{String(value)}</span>
    );
  if (depth >= 5)
    return (
      <span className="text-muted-foreground">
        See Technical details for the complete saved value.
      </span>
    );
  if (Array.isArray(value))
    return value.length ? (
      <ul className="space-y-2 border-l pl-3">
        {value.map((item, index) => (
          <li key={index}>
            <SavedValue value={item} depth={depth + 1} />
          </li>
        ))}
      </ul>
    ) : (
      <span className="text-muted-foreground">None supplied</span>
    );
  return (
    <dl className="space-y-2">
      {Object.entries(value).map(([name, field]) => (
        <div key={name}>
          <dt className="break-words font-medium">
            {name.replaceAll("_", " ")}
          </dt>
          <dd className="mt-1 pl-3 text-muted-foreground">
            <SavedValue value={field} depth={depth + 1} />
          </dd>
        </div>
      ))}
    </dl>
  );
}
export function EvidenceLinks({
  refs,
  onOpen,
}: {
  refs: EvidenceRef[];
  onOpen: (ref: EvidenceRef) => void;
}) {
  return (
    <div className="mt-2 flex flex-wrap gap-2">
      {refs.map((ref, i) => (
        <button
          key={i}
          className="inspection-link break-all text-left text-xs"
          onClick={() => onOpen(ref)}
        >
          {ref.source}: {ref.path || ref.id}
        </button>
      ))}
    </div>
  );
}

export function DiscoveryInspector({
  detail,
  selection,
  onSelect,
  onClose,
}: {
  detail: DiscoveryDetail;
  selection: Selection | null;
  onSelect: (item: Selection) => void;
  onClose: () => void;
}) {
  const desktop = useSyncExternalStore(subscribe, desktopSnapshot, () => false);
  const returnFocus = useRef<HTMLElement | null>(null);
  const model = adaptSchema(detail.schema_proposal ?? {});
  const item = selection;
  const choices = modelingChoices(detail, item);
  const record = item ? selectedRecord(detail, item) : undefined;
  const entity =
    item && (item.kind === "entity" || item.kind === "property")
      ? model.entityById.get(item.id)
      : undefined;
  const selectedRelation =
    item?.kind === "relation"
      ? model.relations.find((r) => r.id === item.id)
      : undefined;
  const evidence =
    item?.kind === "evidence" ? resolveEvidence(detail, item.ref) : undefined;
  const selectedQuestion =
    item?.kind === "evidence" && item.ref.source === "question"
      ? detail.questions.find((question) => question.id === item.ref.id)
      : undefined;
  const sameRef = (a: EvidenceRef, b: EvidenceRef) =>
    a.source === b.source &&
    a.id === b.id &&
    (a.path === b.path || a.path.startsWith(`${b.path}/`));
  const relations = model.relations.filter(
    (relation) =>
      selectedRelation?.id === relation.id ||
      (entity &&
        ((relation.from_entity === entity.id &&
          (item?.kind !== "property" ||
            relation.from_property === item.property)) ||
          (relation.to_entity === entity.id &&
            (item?.kind !== "property" ||
              relation.to_property === item.property)))) ||
      (item?.kind === "binding" && relation.binding_ids.includes(item.id)) ||
      (item?.kind === "tool" &&
        relation.binding_ids.some(
          (id) => model.bindingById.get(id)?.tool_id === item.id,
        )) ||
      (item?.kind === "requirement" &&
        relation.requirement_ids.includes(item.id)),
  );
  const bindings = model.bindings.filter(
    (binding) =>
      (entity &&
        binding.entity_id === entity.id &&
        (item?.kind !== "property" || binding.property === item.property)) ||
      selectedRelation?.binding_ids.includes(binding.id) ||
      (item?.kind === "binding" && binding.id === item.id) ||
      (item?.kind === "tool" && binding.tool_id === item.id) ||
      (item?.kind === "evidence" && sameRef(binding.source, item.ref)),
  );
  const requirementIds = new Set<string>(entity?.requirement_ids ?? []);
  if (
    record &&
    typeof record === "object" &&
    "requirement_ids" in record &&
    Array.isArray(record.requirement_ids)
  )
    for (const id of record.requirement_ids) requirementIds.add(String(id));
  for (const binding of bindings)
    for (const id of model.entityById.get(binding.entity_id)?.requirement_ids ??
      [])
      requirementIds.add(id);
  if (item?.kind === "requirement") requirementIds.add(item.id);
  const requirements =
    detail.requirements?.requirements.filter(
      (requirement) =>
        requirementIds.has(requirement.id) ||
        (item?.kind === "tool" && requirement.tool_ids?.includes(item.id)) ||
        (item?.kind === "evidence" &&
          requirement.evidence.some((ref) => sameRef(ref, item.ref))),
    ) ?? [];
  const refs = [
    ...choices.flatMap((choice) => choice.evidence),
    ...bindings.map((binding) => binding.source),
    ...requirements.flatMap((requirement) => requirement.evidence),
  ];
  if (item?.kind === "evidence") refs.push(item.ref);
  if (selectedQuestion) refs.push(...selectedQuestion.question.evidence);
  if (
    record &&
    typeof record === "object" &&
    "evidence" in record &&
    Array.isArray(record.evidence)
  )
    refs.push(...(record.evidence as EvidenceRef[]));
  const uniqueRefs = [
    ...new Map(refs.map((ref) => [JSON.stringify(ref), ref])).values(),
  ];
  const observations = [
    ...new Map([
      ...uniqueRefs.flatMap((ref) => {
        const resolved = resolveEvidence(detail, ref);
        return resolved.artifact?.kind === "observation"
          ? [[resolved.artifact.id, resolved.artifact] as const]
          : [];
      }),
      ...detail.artifacts
        .filter(
          (artifact) =>
            item?.kind === "tool" &&
            artifact.kind === "observation" &&
            artifact.payload.tool_id === item.id,
        )
        .map((artifact) => [artifact.id, artifact] as const),
    ]).values(),
  ];
  const relatedKeys = new Set([
    selectionKey(item),
    ...bindings.map((binding) =>
      selectionKey({ kind: "binding", id: binding.id }),
    ),
    ...relations.map((relation) =>
      selectionKey({ kind: "relation", id: relation.id }),
    ),
    ...requirements.map((requirement) =>
      selectionKey({ kind: "requirement", id: requirement.id }),
    ),
    ...uniqueRefs.map((ref) => selectionKey({ kind: "evidence", ref })),
  ]);
  const issues = [...model.issues, ...evidenceIssues(detail)].filter((issue) =>
    relatedKeys.has(selectionKey(issue.item)),
  );
  const sourceRefs = uniqueRefs.filter((ref) => ref.source !== "question");
  const clarificationRefs = uniqueRefs.filter(
    (ref) => ref.source === "question" && ref.id !== selectedQuestion?.id,
  );
  const title =
    item?.kind === "record"
      ? item.title
      : selectedQuestion
        ? selectedQuestion.question.text
        : item?.kind === "evidence"
          ? `${item.ref.source}: ${item.ref.path || item.ref.id}`
          : item?.kind === "property"
            ? `${item.id}.${item.property}`
            : (entity?.name ??
              selectedRelation?.name ??
              (item && "id" in item ? item.id : "Saved record"));
  const proposal =
    item &&
    ["entity", "property", "relation", "operation", "requirement"].includes(
      item.kind,
    );
  const link = (target: Selection, text: ReactNode) => (
    <button
      className="inspection-link break-words text-left"
      onClick={() => onSelect(target)}
    >
      {text}
    </button>
  );
  return (
    <Dialog
      key={desktop ? "panel" : "dialog"}
      open={Boolean(item)}
      modal={!desktop}
      onOpenChange={(open) => {
        if (!open) onClose();
      }}
    >
      <DialogContent
        aria-modal={!desktop}
        className="discovery-inspector max-h-[90dvh] overflow-y-auto sm:max-w-xl"
        onOpenAutoFocus={() => {
          returnFocus.current =
            document.activeElement instanceof HTMLElement
              ? document.activeElement
              : null;
        }}
        onCloseAutoFocus={(event) => {
          event.preventDefault();
          if (item) return;
          const origin = returnFocus.current;
          if (origin?.isConnected) origin.focus();
          else if (origin?.dataset.testid)
            document
              .querySelector<HTMLElement>(
                `[data-testid="${CSS.escape(origin.dataset.testid)}"]`,
              )
              ?.focus();
        }}
        onInteractOutside={(event) => {
          if (desktop) event.preventDefault();
        }}
      >
        <DialogHeader>
          <DialogTitle className="break-words pr-8">{title}</DialogTitle>
          <DialogDescription>
            {selectedQuestion
              ? "User clarification about task intent. This is not a tool observation."
              : proposal
                ? "Proposal. Source evidence remains separate."
                : item?.kind === "binding"
                  ? "Saved source mapping. Support and coverage are shown as saved."
                  : evidence?.artifact?.kind === "observation"
                    ? "Saved tool observation. This does not establish complete coverage."
                    : "Saved discovery record."}
          </DialogDescription>
        </DialogHeader>
        <div className="min-w-0 space-y-5 text-xs">
          {item && "id" in item && (
            <p className="break-all text-muted-foreground">
              Saved ID: {item.id}
            </p>
          )}
          {evidence && !evidence.found && (
            <p role="alert" className="error-panel">
              Evidence reference unavailable. No substitute was inferred.
            </p>
          )}
          <section className="space-y-2">
            <h3 className="font-semibold">
              {selectedQuestion ? "User clarification" : "Saved definition"}
            </h3>
            {selectedQuestion && evidence?.found ? (
              <>
                <p>{selectedQuestion.question.why_needed}</p>
                {!!selectedQuestion.question.affected?.length && (
                  <p>
                    Affects: {selectedQuestion.question.affected.join(", ")}
                  </p>
                )}
                {selectedQuestion.answer === null &&
                  selectedQuestion.question.unresolved_detail && (
                    <p>
                      Point to clarify:{" "}
                      {selectedQuestion.question.unresolved_detail}
                    </p>
                  )}
                <p>
                  {selectedQuestion.answer === null
                    ? "Awaiting an answer."
                    : `Answer: ${selectedQuestion.answer}`}
                </p>
                {selectedQuestion.answered_by && (
                  <p className="text-muted-foreground">
                    Answered by {selectedQuestion.answered_by}
                    {selectedQuestion.answered_at
                      ? ` · ${new Date(selectedQuestion.answered_at).toLocaleString()}`
                      : ""}
                  </p>
                )}
              </>
            ) : (
              <SavedValue value={record} />
            )}
          </section>
          {item?.kind === "property" && (
            <p>
              Identity declaration:{" "}
              {entity?.identity_keys?.includes(item.property)
                ? "Identity property"
                : "Not declared"}
            </p>
          )}
          <ModelingReasons choices={choices} onInspect={onSelect} />
          {selectedRelation && <p>Cardinality: unspecified.</p>}
          {requirements.length > 0 && (
            <section className="space-y-2">
              <h3 className="font-semibold">Relevant requirements</h3>
              {requirements.map((requirement) => (
                <div key={requirement.id}>
                  {link(
                    { kind: "requirement", id: requirement.id },
                    `${requirement.id}: ${requirement.statement}`,
                  )}
                  {requirement.ambiguity && (
                    <p className="mt-1">Unresolved: {requirement.ambiguity}</p>
                  )}
                </div>
              ))}
              {!requirements.length && (
                <p className="text-muted-foreground">
                  No explicit requirement links supplied.
                </p>
              )}
            </section>
          )}
          {(relations.length > 0 || entity || selectedRelation) && (
            <section className="space-y-2">
              <h3 className="font-semibold">Relationships</h3>
              {relations.map((relation) => (
                <div key={relation.id}>
                  {link(
                    { kind: "relation", id: relation.id },
                    `${relation.name} · ${relation.id}`,
                  )}
                  <p className="mt-1 break-words">
                    {relation.from_entity}.{relation.from_property} →{" "}
                    {relation.to_entity}.{relation.to_property}
                  </p>
                  <p className="text-muted-foreground">
                    Proposed · Cardinality: unspecified
                  </p>
                </div>
              ))}
              {!relations.length && (
                <p className="text-muted-foreground">
                  No explicit relationship links supplied.
                </p>
              )}
            </section>
          )}
          {(bindings.length > 0 || entity || item?.kind === "binding") && (
            <section className="space-y-3">
              <h3 className="font-semibold">Source mappings</h3>
              {bindings.map((binding) => (
                <div key={binding.id}>
                  {link(
                    { kind: "binding", id: binding.id },
                    `${binding.id}: ${binding.entity_id}.${binding.property}`,
                  )}
                  <p>
                    Source support: {binding.support} · Coverage:{" "}
                    {binding.coverage}
                  </p>
                  <p className="break-words">Tool: {binding.tool_id}</p>
                  <EvidenceLinks
                    refs={[binding.source]}
                    onOpen={(ref) => onSelect({ kind: "evidence", ref })}
                  />
                </div>
              ))}
              {!bindings.length && (
                <p className="text-muted-foreground">
                  No explicit source mappings supplied.
                </p>
              )}
            </section>
          )}
          {(observations.length > 0 || item?.kind === "tool") && (
            <section className="space-y-2">
              <h3 className="font-semibold">Supporting observations</h3>
              {observations.map((observation) => (
                <p key={observation.id}>
                  {link(
                    {
                      kind: "evidence",
                      ref: { source: "artifact", id: observation.id, path: "" },
                    },
                    observation.title,
                  )}
                </p>
              ))}
              {!observations.length && (
                <p className="text-muted-foreground">
                  No supporting observation is linked to this item.
                </p>
              )}
            </section>
          )}
          {sourceRefs.length > 0 && (
            <section>
              <h3 className="font-semibold">Source evidence</h3>
              <EvidenceLinks
                refs={sourceRefs}
                onOpen={(ref) => onSelect({ kind: "evidence", ref })}
              />
            </section>
          )}
          {clarificationRefs.length > 0 && (
            <section className="space-y-2">
              <h3 className="font-semibold">Linked user clarifications</h3>
              <p className="text-muted-foreground">
                These answers describe intent. They do not establish tool
                capabilities or observed effects.
              </p>
              {clarificationRefs.map((ref, index) => {
                const question = detail.questions.find((q) => q.id === ref.id);
                return (
                  <p key={index}>
                    {link(
                      { kind: "evidence", ref },
                      question?.question.text ??
                        "Unavailable user clarification",
                    )}
                  </p>
                );
              })}
            </section>
          )}
          {issues.length > 0 && (
            <section className="space-y-2">
              <h3 className="font-semibold">
                Reference issues for this record
              </h3>
              {issues.map((issue, index) => (
                <p key={index}>{link(issue.item, issue.message)}</p>
              ))}
            </section>
          )}
          <details className="border-t pt-3">
            <summary>Technical details</summary>
            <pre className="mt-3 max-h-80 overflow-auto whitespace-pre-wrap break-all">
              {JSON.stringify(
                evidence
                  ? {
                      reference:
                        item?.kind === "evidence" ? item.ref : undefined,
                      selected: record,
                      record: evidence.record,
                    }
                  : record,
                null,
                2,
              )}
            </pre>
          </details>
        </div>
      </DialogContent>
    </Dialog>
  );
}
