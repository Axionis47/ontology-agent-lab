"""Check MCP content conversion in the installed client without model calls."""

import json
import sqlite3
import subprocess
from pathlib import Path

import pytest

BACKEND = Path(__file__).resolve().parents[2]
PACKAGE = BACKEND / ".local/gemini-cli/node_modules/@google/gemini-cli"
SQLITE = BACKEND / ".local/real-mcp/sqlite-venv/bin/mcp-server-sqlite"
BUNDLES = [
    path
    for path in (PACKAGE / "bundle").glob("*.js")
    if "var McpComplianceTransport = class" in path.read_text()
]
SCRIPT = r"""
import assert from 'node:assert/strict';
import {pathToFileURL} from 'node:url';
const cli = await import(pathToFileURL(process.argv[2]).href);
const underlying = {};
const transport = new cli.oakMcpComplianceTransport(underlying);
let received;
transport.onmessage = (message) => {received = message;};
for (const text of ['[]','[1,2]','null','false','42','"text"',"[{'id': 1}]"]) {
  const message = {jsonrpc:'2.0',id:1,result:{content:[{type:'text',text}],isError:false}};
  underlying.onmessage(message);
  assert.equal(received.result.content[0].text,text);
  assert.equal(Object.hasOwn(received.result,'structuredContent'),false);
  assert.equal(cli.CallToolResultSchema.safeParse(received.result).success,true);
}
const object = {jsonrpc:'2.0',id:2,result:{content:[{type:'text',text:'{"offers":[]}'}]}};
underlying.onmessage(object);
assert.deepEqual(received.result.structuredContent,{offers:[]});
const existing = {jsonrpc:'2.0',id:3,result:{
  content:[{type:'text',text:'[]'}],structuredContent:{stable:true}
}};
underlying.onmessage(existing);
assert.deepEqual(received.result.structuredContent,{stable:true});
assert.equal(cli.CallToolResultSchema.safeParse({
  content:[{type:'text',text:'[]'}],structuredContent:[]
}).success,false);
console.log(JSON.stringify({passed:true}));
"""
INTEGRATION = r"""
import assert from 'node:assert/strict';
import {pathToFileURL} from 'node:url';
const cli = await import(pathToFileURL(process.argv[2]).href);
const client = await cli.connectToMcpServer(
  'local-test','sqlite',
  {command:process.argv[3],args:['--db-path',process.argv[4]],timeout:5000},
  false,
  {getDirectories:()=>[],onDirectoriesChanged:()=>()=>{}},
  {isTrustedFolder:()=>true,sanitizationConfig:{}}
);
try {
  await client.listTools();
  for (const query of [
    'SELECT * FROM reservations',
    'SELECT * FROM reservations r LEFT JOIN offers o ON r.offer_id=o.id',
    'SELECT * FROM offers WHERE id=\'missing\'',
  ]) {
    const result = await client.callTool({name:'read_query',arguments:{query}});
    assert.equal(result.isError,false);
    assert.equal(result.content[0].text,'[]');
    assert.equal(result.structuredContent,undefined);
  }
  console.log(JSON.stringify({passed:true,empty_queries:3}));
} finally {
  await client.close();
}
"""


@pytest.mark.skipif(len(BUNDLES) != 3, reason="Install and patch the local Gemini CLI.")
@pytest.mark.parametrize("bundle", BUNDLES, ids=lambda path: path.name)
def test_actual_client_preserves_array_and_primitive_text(bundle):
    result = subprocess.run(
        ["node", "--input-type=module", "-", str(bundle)],
        input=SCRIPT,
        text=True,
        capture_output=True,
        timeout=20,
    )
    assert result.returncode == 0, result.stderr
    assert json.loads(result.stdout.strip().splitlines()[-1])["passed"]


@pytest.mark.skipif(not BUNDLES or not SQLITE.is_file(), reason="Install the existing MCP servers.")
def test_real_sqlite_empty_results_pass_actual_gemini_client(tmp_path):
    database = tmp_path / "empty.db"
    with sqlite3.connect(database) as connection:
        connection.execute("CREATE TABLE reservations(offer_id TEXT)")
        connection.execute("CREATE TABLE offers(id TEXT)")
        connection.execute("INSERT INTO offers VALUES ('present')")
    result = subprocess.run(
        ["node", "--input-type=module", "-", str(BUNDLES[0]), str(SQLITE), str(database)],
        input=INTEGRATION,
        text=True,
        capture_output=True,
        timeout=20,
    )
    assert result.returncode == 0, result.stderr
    assert json.loads(result.stdout.strip().splitlines()[-1])["empty_queries"] == 3
