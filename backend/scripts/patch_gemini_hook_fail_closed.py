"""Require an explicit task-guard decision in the local Gemini CLI 0.67.0.

The change applies only when OAK_REQUIRE_TASK_GUARD=1. Keep other sessions unchanged.
Back up each bundle before this patch. The MCP server packages stay unchanged.
"""

import json
from pathlib import Path

MARKER = "// OAK task guard: require an explicit successful BeforeTool decision."
HELPERS = """// OAK task guard: require an explicit successful BeforeTool decision.
function oakRequiresTaskGuard() {
  return process.env.OAK_REQUIRE_TASK_GUARD === "1";
}
function oakTaskGuardReason(output) {
  return output?.reason || "The task guard did not explicitly allow this call.";
}
function oakTaskGuardToolError(reason) {
  return {
    llmContent: reason,
    returnDisplay: reason,
    error: { type: "policy_violation", message: reason }
  };
}
function oakTaskGuardScheduleError(reason) {
  return { status: "error", error: new Error(reason), errorType: "policy_violation" };
}
"""


def replace_once(text, old, new):
    if text.count(old) != 1:
        raise ValueError("The installed CLI code does not match this version-specific patch.")
    return text.replace(old, new, 1)


def patch(text):
    if MARKER in text:
        return text
    legacy_start = text.index("async function executeToolWithHooks(")
    scheduler_start = text.index("async function evaluateBeforeToolHook(", legacy_start)
    next_section = text.index("\n// packages/", scheduler_start)
    legacy = text[legacy_start:scheduler_start]
    scheduler = text[scheduler_start:next_section]
    legacy = replace_once(
        legacy,
        "  const hookSystem = config2?.getHookSystem();\n",
        "  const hookSystem = config2?.getHookSystem();\n"
        "  if (oakRequiresTaskGuard() && !skipBeforeHook && !hookSystem) {\n"
        '    return oakTaskGuardToolError("The required task guard is unavailable.");\n'
        "  }\n",
    )
    legacy_call = """    const beforeOutput = await hookSystem.fireBeforeToolEvent(
      toolName,
      toolInput,
      mcpContext,
      originalRequestName
    );"""
    if legacy_call not in legacy:
        legacy_call = (
            "    const beforeOutput = await hookSystem.fireBeforeToolEvent("
            "toolName, toolInput, mcpContext, originalRequestName);"
        )
    legacy = replace_once(
        legacy,
        legacy_call,
        """    let beforeOutput;
    try {
      beforeOutput = await hookSystem.fireBeforeToolEvent(
        toolName, toolInput, mcpContext, originalRequestName
      );
    } catch (oakError) {
      if (oakRequiresTaskGuard()) {
        return oakTaskGuardToolError(`The task guard failed: ${String(oakError)}`);
      }
      throw oakError;
    }
    if (oakRequiresTaskGuard() && beforeOutput?.decision !== "allow") {
      return oakTaskGuardToolError(oakTaskGuardReason(beforeOutput));
    }""",
    )
    scheduler = replace_once(
        scheduler,
        """  if (!hookSystem) {
    return { status: "continue" };
  }""",
        """  if (!hookSystem) {
    if (oakRequiresTaskGuard()) {
      return oakTaskGuardScheduleError("The required task guard is unavailable.");
    }
    return { status: "continue" };
  }""",
    )
    scheduler_call = """  const beforeOutput = await hookSystem.fireBeforeToolEvent(
    request.name,
    toolInput,
    mcpContext,
    request.originalRequestName
  );"""
    if scheduler_call not in scheduler:
        scheduler_call = (
            "  const beforeOutput = await hookSystem.fireBeforeToolEvent("
            "request.name, toolInput, mcpContext, request.originalRequestName);"
        )
    scheduler = replace_once(
        scheduler,
        scheduler_call,
        """  let beforeOutput;
  try {
    beforeOutput = await hookSystem.fireBeforeToolEvent(
      request.name, toolInput, mcpContext, request.originalRequestName
    );
  } catch (oakError) {
    if (oakRequiresTaskGuard()) {
      return oakTaskGuardScheduleError(`The task guard failed: ${String(oakError)}`);
    }
    throw oakError;
  }
  if (oakRequiresTaskGuard() && beforeOutput?.decision !== "allow") {
    return oakTaskGuardScheduleError(oakTaskGuardReason(beforeOutput));
  }""",
    )
    text = text[:legacy_start] + HELPERS + legacy + scheduler + text[next_section:]
    text = replace_once(
        text,
        """  aggregateResults(results, eventName) {
    const allOutputs = [];""",
        """  aggregateResults(results, eventName) {
    if (oakRequiresTaskGuard() && eventName === "BeforeTool") {
      const invalid = results.find((result) =>
        !result.success || result.output?.decision !== "allow" || result.outputFormat === "text"
      );
      if (results.length === 0 || invalid) {
        const reason = invalid?.error?.message || invalid?.output?.reason ||
          "The task guard must return a successful explicit JSON allow decision.";
        const denied = { decision: "deny", reason };
        return {
          success: false,
          finalOutput: this.createSpecificHookOutput(denied, eventName),
          allOutputs: results.map((result) => result.output).filter(Boolean),
          errors: [new Error(reason)],
          totalDuration: results.reduce((total, result) => total + result.duration, 0)
        };
      }
    }
    const allOutputs = [];""",
    )
    # Expose the installed functions for local tests. This does not execute a model call.
    return text + (
        "\nexport { evaluateBeforeToolHook as oakEvaluateBeforeToolHook, "
        "executeToolWithHooks as oakExecuteToolWithHooks };\n"
    )


def main():
    package = (
        Path(__file__).resolve().parents[1] / ".local/gemini-cli/node_modules/@google/gemini-cli"
    )
    metadata = json.loads((package / "package.json").read_text())
    if metadata["version"] != "0.67.0":
        raise SystemExit("This patch applies only to Gemini CLI 0.67.0.")
    changes, found = [], 0
    for path in (package / "bundle").glob("*.js"):
        original = path.read_text()
        if "async function evaluateBeforeToolHook(" not in original:
            continue
        found += 1
        updated = patch(original)
        if updated != original:
            changes.append((path, original, updated))
    if found != 3:
        raise SystemExit(f"Expected three CLI hook bundles. Found {found}.")
    for path, original, updated in changes:
        backup = path.with_suffix(".js.oak-before-guard-patch")
        if not backup.exists():
            backup.write_text(original)
        path.write_text(updated)
    print(f"Patched {len(changes)} CLI bundles. Only task-guard sessions change.")


if __name__ == "__main__":
    main()
