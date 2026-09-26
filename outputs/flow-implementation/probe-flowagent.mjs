import { spawn } from 'node:child_process';
import { createInterface } from 'node:readline';

const serverPath = process.argv[2];
const mode = process.argv[3] ?? 'list';
if (!serverPath) throw new Error('Pass the FlowAgent MCP server path.');

const child = spawn(process.execPath, [serverPath], { stdio: ['pipe', 'pipe', 'pipe'] });
const lines = createInterface({ input: child.stdout });
let phase = 'initialize';
let timer = setTimeout(() => {
  process.stderr.write('Timed out waiting for FlowAgent MCP.\n');
  child.kill();
  process.exitCode = 1;
}, 30000);

function send(message) {
  child.stdin.write(JSON.stringify(message) + '\n');
}

send({ jsonrpc: '2.0', id: 1, method: 'initialize', params: {
  protocolVersion: '2025-03-26', capabilities: {},
  clientInfo: { name: 'flowagent-readonly-probe', version: '1.0.0' }
} });

for await (const line of lines) {
  let message;
  try { message = JSON.parse(line); } catch { continue; }
  if (phase === 'initialize' && message.id === 1) {
    if (message.error) throw new Error(JSON.stringify(message.error));
    send({ jsonrpc: '2.0', method: 'notifications/initialized' });
    send({ jsonrpc: '2.0', id: 2, method: 'tools/list', params: {} });
    phase = 'tools';
  } else if (phase === 'tools' && message.id === 2) {
    if (message.error) throw new Error(JSON.stringify(message.error));
    const tools = message.result?.tools ?? [];
    const names = tools.map(tool => tool.name);
    const matchingTools = tools.filter(tool => /^(doctor|whoami|list_environments|list_flows|get_flow|create_flow|edit_flow|update_flow|preflight_flow|preview_update|search_operations|get_operation_details|scaffold_flow|validate_flow)$/.test(tool.name));
    if (mode === 'schema') {
      process.stdout.write(JSON.stringify({ toolCount: names.length,
        matchingTools: matchingTools.map(tool => ({ name: tool.name, inputSchema: tool.inputSchema }))
      }) + '\n');
      clearTimeout(timer);
      child.kill();
      break;
    }
    if (mode === 'doctor' || mode === 'environments') {
      send({ jsonrpc: '2.0', id: 3, method: 'tools/call', params: {
        name: mode === 'doctor' ? 'doctor' : 'list_environments', arguments: {}
      } });
      phase = 'response';
      continue;
    }
    process.stdout.write(JSON.stringify({ toolCount: names.length,
      matchingTools: matchingTools.map(tool => tool.name)
    }) + '\n');
    clearTimeout(timer);
    child.kill();
    break;
  } else if (phase === 'response' && message.id === 3) {
    const raw = JSON.stringify(message.result ?? message.error ?? {});
    const redacted = raw.replace(/[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}/g, '[email]')
      .replace(/Bearer\s+[A-Za-z0-9._~+/-]+/gi, 'Bearer [redacted]');
    process.stdout.write(redacted.slice(0, 8000) + '\n');
    clearTimeout(timer);
    child.kill();
    break;
  }
}
