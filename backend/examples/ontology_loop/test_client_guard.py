"""Test the installed CLI hook code without a model or MCP network request."""

import json
import subprocess
from pathlib import Path

import pytest

from .native import require_guard_patch

BACKEND = Path(__file__).resolve().parents[2]
PACKAGE = BACKEND / ".local/gemini-cli/node_modules/@google/gemini-cli"
BUNDLES = [
    path
    for path in (PACKAGE / "bundle").glob("*.js")
    if "async function evaluateBeforeToolHook(" in path.read_text()
]
SCRIPT = r"""
import assert from 'node:assert/strict';
import {pathToFileURL} from 'node:url';
const cli = await import(pathToFileURL(process.argv[2]).href);
const cwd = process.argv[3];
const runner = new cli.HookRunner({
  isTrustedFolder: () => true,
  storage: {getPlansDir: () => cwd},
  sanitizationConfig: {},
});
const aggregator = new cli.HookAggregator();
const input = {cwd, session_id:'local-guard-test', hook_event_name:'BeforeTool'};
let writes = 0;
const invocation = {params:{}, execute:async () => {
  writes += 1;
  return {llmContent:'Local action',returnDisplay:'Local action'};
}};
const tool = {build: () => invocation};
async function check(output, allowed, missing=false, throws=false) {
  writes = 0;
  const hookSystem = missing ? undefined : {
    fireBeforeToolEvent:async () => {if(throws) throw Error('guard crashed'); return output;},
    fireAfterToolEvent:async () => undefined,
  };
  const config = {getHookSystem: () => hookSystem};
  const scheduled = await cli.oakEvaluateBeforeToolHook(
    config,tool,{name:'mcp_sqlite_write_query'},invocation
  );
  const executed = await cli.oakExecuteToolWithHooks(
    invocation,'mcp_sqlite_write_query',new AbortController().signal,tool,
    undefined,{},config,undefined,false
  );
  assert.equal(scheduled.status, allowed ? 'continue' : 'error');
  assert.equal(writes, allowed ? 1 : 0);
  if(!allowed) {
    assert.equal(scheduled.errorType,'policy_violation');
    assert.equal(executed.error.type,'policy_violation');
  }
}
process.env.OAK_REQUIRE_TASK_GUARD = '1';
await check(undefined,false,true);
await check(undefined,false);
await check(undefined,false,false,true);
await check(new cli.BeforeToolHookOutput({}),false);
await check(new cli.BeforeToolHookOutput({decision:'ask'}),false);
await check(new cli.BeforeToolHookOutput({decision:'deny',reason:'test deny'}),false);
await check(new cli.BeforeToolHookOutput({decision:'allow'}),true);
const cases = [
  ['timeout',{type:'runtime',timeout:5,action:async()=>new Promise(()=>{})},input,false],
  ['spawn_error',{type:'command',command:'true'}, {...input,cwd:cwd+'/missing'},false],
  ['malformed',{type:'command',command:"printf '%s' 'not-json'"},input,false],
  ['empty_object',{type:'command',command:"printf '%s' '{}'"},input,false],
  ['nonzero_allow',{type:'command',
    command:"printf '%s' '{\"decision\":\"allow\"}'; exit 1"},input,false],
  ['valid_allow',{type:'command',command:"printf '%s' '{\"decision\":\"allow\"}'"},input,true],
];
const outcomes = [];
for (const [name,hook,event,allowed] of cases) {
  const result = await runner.executeHook(hook,'BeforeTool',event);
  const aggregate = aggregator.aggregateResults([result],'BeforeTool');
  await check(aggregate.finalOutput,allowed);
  outcomes.push({name,allowed});
}
const empty = aggregator.aggregateResults([],'BeforeTool');
await check(empty.finalOutput,false);
delete process.env.OAK_REQUIRE_TASK_GUARD;
await check(undefined,true,true);
await check(undefined,true);
const legacy = aggregator.aggregateResults([
  {success:true,output:{},duration:0}
],'BeforeTool');
assert.equal(legacy.finalOutput.decision,'allow');
console.log(JSON.stringify({passed:true,cases:outcomes,default_behavior_preserved:true}));
"""


@pytest.mark.skipif(len(BUNDLES) != 3, reason="Install and patch the local Gemini CLI.")
@pytest.mark.parametrize("bundle", BUNDLES, ids=lambda path: path.name)
def test_actual_cli_rejects_missing_or_failed_guard_before_actions(bundle, tmp_path):
    result = subprocess.run(
        ["node", "--input-type=module", "-", str(bundle), str(tmp_path)],
        input=SCRIPT,
        text=True,
        capture_output=True,
        timeout=30,
    )
    assert result.returncode == 0, result.stderr
    assert json.loads(result.stdout.strip().splitlines()[-1])["passed"]


def test_native_runner_refuses_unpatched_cli(tmp_path):
    executable = tmp_path / "bundle/gemini.js"
    executable.parent.mkdir()
    executable.write_text("// An unpatched CLI fixture.")
    (tmp_path / "package.json").write_text(json.dumps({"version": "0.67.0"}))
    with pytest.raises(ValueError, match="patch_gemini_hook_fail_closed"):
        require_guard_patch(str(executable))
