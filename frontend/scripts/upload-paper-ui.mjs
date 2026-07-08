import { readFile } from 'node:fs/promises';
import http from 'node:http';
import path from 'node:path';

const args = parseArgs(process.argv.slice(2));
const projectRoot = path.resolve(import.meta.dirname, '..');
const bundleDir = path.resolve(projectRoot, args.dir ?? 'dist/paper-ui-export');
const host = args.host ?? '127.0.0.1';
const port = Number(args.port ?? 29979);
const fileName = args.fileName ?? 'Bambuddy Editable UI Export';

const manifest = await readJson(path.join(bundleDir, 'paper-ui-manifest.json'));
const tokens = await readJson(path.join(bundleDir, 'paper-tokens.json'));
const htmlByPath = new Map();

for (const artboard of manifest.artboards) {
  htmlByPath.set(artboard.htmlFile, await readFile(path.join(bundleDir, artboard.htmlFile), 'utf8'));
}

if (!args.upload) {
  console.log('Paper UI upload dry run');
  console.log(`Bundle: ${bundleDir}`);
  console.log(`Paper MCP: http://${host}:${port}/mcp`);
  console.log(`Artboards: ${manifest.artboards.length}`);
  console.log(`Tokens: ${tokens.length}`);
  console.log('Pass --upload to create or mutate a Paper file.');
  process.exit(0);
}

const client = await createMcpClient({ host, port });
await client.call('get_guide', { topic: 'paper-mcp-instructions' });

const created = JSON.parse(await client.call('create_file', { name: fileName }));
await client.call('open_file', { fileId: created.fileId });

for (const batch of chunks(tokens, 50)) {
  await client.call('create_tokens', { tokens: batch });
}

for (const artboard of manifest.artboards) {
  const createdArtboard = JSON.parse(
    await client.call('create_artboard', {
      name: artboard.label,
      styles: artboard.artboardStyles,
    }),
  );
  await client.call('write_html', {
    targetNodeId: createdArtboard.id,
    mode: 'insert-children',
    html: htmlByPath.get(artboard.htmlFile),
  });
  console.log(`Uploaded ${artboard.label}`);
}

await client.call('finish_working_on_nodes', {});
console.log(`Paper file: ${created.url}`);

function parseArgs(argv) {
  const parsed = {};
  for (let index = 0; index < argv.length; index += 1) {
    const arg = argv[index];
    if (arg === '--upload') {
      parsed.upload = true;
    } else if (arg === '--dir') {
      parsed.dir = argv[index + 1];
      index += 1;
    } else if (arg === '--host') {
      parsed.host = argv[index + 1];
      index += 1;
    } else if (arg === '--port') {
      parsed.port = argv[index + 1];
      index += 1;
    } else if (arg === '--file-name') {
      parsed.fileName = argv[index + 1];
      index += 1;
    } else if (arg === '--help') {
      printHelp();
      process.exit(0);
    } else {
      console.error(`Unknown argument: ${arg}`);
      printHelp();
      process.exit(2);
    }
  }
  return parsed;
}

function printHelp() {
  console.log(`Usage: node scripts/upload-paper-ui.mjs [--upload] [--dir <bundle-dir>] [--host <host>] [--port <port>] [--file-name <name>]

Without --upload this only validates that a generated bundle can be read.
With --upload it creates a Paper file through the local Paper Desktop MCP.
`);
}

async function readJson(filePath) {
  return JSON.parse(await readFile(filePath, 'utf8'));
}

function chunks(items, size) {
  const result = [];
  for (let index = 0; index < items.length; index += size) {
    result.push(items.slice(index, index + size));
  }
  return result;
}

async function createMcpClient({ host, port }) {
  let nextId = 1;
  const initialized = await post({
    jsonrpc: '2.0',
    id: nextId,
    method: 'initialize',
    params: {
      protocolVersion: '2025-03-26',
      capabilities: {},
      clientInfo: { name: 'bambuddy-paper-ui-upload', version: '1.0' },
    },
  });
  nextId += 1;

  const sessionId = initialized.headers['mcp-session-id'];
  if (!sessionId) throw new Error('Paper MCP did not return a session id.');

  await post({ jsonrpc: '2.0', method: 'notifications/initialized', params: {} }, sessionId);

  return {
    async call(name, callArgs) {
      const response = await post(
        {
          jsonrpc: '2.0',
          id: nextId,
          method: 'tools/call',
          params: { name, arguments: callArgs },
        },
        sessionId,
      );
      nextId += 1;

      const event = response.events[0];
      if (!event?.result) {
        throw new Error(`Paper MCP ${name} returned no result.`);
      }
      if (event.result.isError) {
        const message = event.result.content?.[0]?.text ?? JSON.stringify(event.result);
        throw new Error(`Paper MCP ${name} failed: ${message}`);
      }
      return event.result.content?.[0]?.text ?? '';
    },
  };

  function post(body, sessionId) {
    const payload = JSON.stringify(body);
    const headers = {
      'Content-Type': 'application/json',
      Accept: 'application/json, text/event-stream',
      'Content-Length': Buffer.byteLength(payload),
    };
    if (sessionId) headers['Mcp-Session-Id'] = sessionId;

    return new Promise((resolve, reject) => {
      const request = http.request(
        { host, port, path: '/mcp', method: 'POST', headers, timeout: 120000 },
        (response) => {
          let data = '';
          response.setEncoding('utf8');
          response.on('data', (chunk) => {
            data += chunk;
          });
          response.on('end', () => {
            if ((response.statusCode ?? 500) >= 400) {
              reject(new Error(`Paper MCP HTTP ${response.statusCode}: ${data}`));
              return;
            }
            resolve({
              headers: response.headers,
              events: parseSse(data),
            });
          });
        },
      );
      request.on('error', reject);
      request.on('timeout', () => {
        request.destroy(new Error('Paper MCP request timed out.'));
      });
      request.write(payload);
      request.end();
    });
  }
}

function parseSse(data) {
  return data
    .split('\n')
    .filter((line) => line.startsWith('data: '))
    .map((line) => JSON.parse(line.slice(6)));
}
