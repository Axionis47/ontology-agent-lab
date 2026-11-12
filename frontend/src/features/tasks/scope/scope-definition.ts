export const scopeSections = [
  {
    key: "responsibilities",
    label: "Responsibilities",
    required: true,
    guidance:
      "Describe the families of actions this task must support across different requests.",
    example:
      "Find meeting times, create meetings, change arrangements, and cancel meetings.",
  },
  {
    key: "context_and_rules",
    label: "Context and rules",
    required: false,
    guidance:
      "Explain the concepts, relationships, prerequisites, and rules that affect these actions.",
    example:
      "A recurring series contains individual occurrences. Required participants must be available for the full duration.",
  },
  {
    key: "boundaries",
    label: "Boundaries",
    required: false,
    guidance:
      "State what is excluded, what must not happen, and when the agent must ask for clarification.",
    example:
      "Do not change unrelated meetings. Ask which meeting to change when several match the request.",
  },
  {
    key: "success_criteria",
    label: "Success criteria",
    required: true,
    guidance:
      "Describe observable results that show the work was completed correctly.",
    example:
      "The requested meeting is updated. Other meetings are unchanged. The reported result matches the calendar record.",
  },
] as const;
