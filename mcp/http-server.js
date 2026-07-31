#!/usr/bin/env node
// Standalone MCP HTTP server, meant to run on the VPS behind nginx (NOT
// behind Vercel) so remote MCP clients (Grok, ChatGPT, Cursor Remote, etc.)
// don't hit Vercel's bot-protection challenge page.
//
// Serves two transports on the same port:
//   POST/GET/DELETE /mcp      — MCP Streamable HTTP (current spec, 2025-03-26+)
//   GET             /mcp/sse  — legacy SSE transport (2024-11-05), for
//                                clients that only speak SSE (e.g. Grok's
//                                custom-connector UI asks for ".../sse")
//   POST            /mcp/messages — POST endpoint paired with /mcp/sse
//
// Run via systemd (see deploy/pepperoni-mcp.service) — do not run manually
// long-term, that's what the unit file is for.
import http from 'node:http';
import { StreamableHTTPServerTransport } from '@modelcontextprotocol/sdk/server/streamableHttp.js';
import { SSEServerTransport } from '@modelcontextprotocol/sdk/server/sse.js';
import { createKazanMcpServer } from './create-server.js';

const PORT = process.env.MCP_PORT || 8130;

function setCors(res) {
  res.setHeader('Access-Control-Allow-Origin', '*');
  res.setHeader('Access-Control-Allow-Methods', 'GET, POST, DELETE, OPTIONS');
  res.setHeader('Access-Control-Allow-Headers', 'Content-Type, MCP-Protocol-Version, Mcp-Session-Id');
}

function readBody(req) {
  return new Promise((resolve, reject) => {
    let data = '';
    req.on('data', (chunk) => (data += chunk));
    req.on('end', () => resolve(data));
    req.on('error', reject);
  });
}

// One long-lived MCP server instance; each Streamable HTTP request in
// stateless mode gets a fresh transport wired to it (mirrors api/mcp.js).
// SSE clients (stateful) get their own transport+server pair per connection,
// keyed by session id, since SSE requires a persistent stream.
const sseSessions = new Map(); // sessionId -> { transport, server }

async function handleStreamableHttp(req, res) {
  const transport = new StreamableHTTPServerTransport({
    sessionIdGenerator: undefined,
    enableJsonResponse: true,
  });
  const server = createKazanMcpServer();
  await server.connect(transport);

  let body;
  if (!['GET', 'HEAD'].includes(req.method)) {
    const raw = await readBody(req);
    try {
      body = raw ? JSON.parse(raw) : undefined;
    } catch {
      body = undefined;
    }
  }

  try {
    await transport.handleRequest(req, res, body);
  } finally {
    res.on('close', () => {
      server.close().catch(() => {});
    });
  }
}

async function handleSseStream(req, res) {
  const transport = new SSEServerTransport('/mcp/messages', res);
  const server = createKazanMcpServer();
  sseSessions.set(transport.sessionId, { transport, server });

  // Just drop our session-map entry on close — do NOT also call
  // server.close() here. Server.close() closes its transport, which
  // re-invokes this onclose handler, which called server.close() again,
  // infinitely (stack overflow on client disconnect). The SDK's own
  // Server/transport machinery already tears itself down correctly.
  transport.onclose = () => {
    sseSessions.delete(transport.sessionId);
  };

  // server.connect() calls transport.start() internally — do not call it
  // again here, that throws ("already started").
  await server.connect(transport);
}

async function handleSseMessage(req, res) {
  const url = new URL(req.url, `http://${req.headers.host}`);
  const sessionId = url.searchParams.get('sessionId');
  const session = sessionId && sseSessions.get(sessionId);
  if (!session) {
    res.writeHead(400).end('Unknown or missing sessionId');
    return;
  }
  const raw = await readBody(req);
  let body;
  try {
    body = raw ? JSON.parse(raw) : undefined;
  } catch {
    res.writeHead(400).end('Invalid JSON body');
    return;
  }
  await session.transport.handlePostMessage(req, res, body);
}

const httpServer = http.createServer(async (req, res) => {
  setCors(res);
  if (req.method === 'OPTIONS') {
    res.writeHead(204).end();
    return;
  }

  const url = new URL(req.url, `http://${req.headers.host}`);

  try {
    if (url.pathname === '/mcp/sse' && req.method === 'GET') {
      await handleSseStream(req, res);
    } else if (url.pathname === '/mcp/messages' && req.method === 'POST') {
      await handleSseMessage(req, res);
    } else if (url.pathname === '/mcp') {
      await handleStreamableHttp(req, res);
    } else if (url.pathname === '/healthz') {
      res.writeHead(200, { 'Content-Type': 'application/json' }).end(JSON.stringify({ ok: true }));
    } else {
      res.writeHead(404).end('Not found');
    }
  } catch (err) {
    if (!res.headersSent) {
      res.writeHead(500, { 'Content-Type': 'application/json' });
    }
    res.end(JSON.stringify({ error: err.message || 'mcp_error' }));
  }
});

httpServer.listen(PORT, '127.0.0.1', () => {
  console.log(`[mcp-http] listening on 127.0.0.1:${PORT}`);
  console.log(`[mcp-http] Streamable HTTP: POST/GET/DELETE /mcp`);
  console.log(`[mcp-http] Legacy SSE:      GET /mcp/sse (+ POST /mcp/messages?sessionId=...)`);
});

process.on('SIGTERM', () => httpServer.close(() => process.exit(0)));
process.on('SIGINT', () => httpServer.close(() => process.exit(0)));
