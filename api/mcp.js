import { WebStandardStreamableHTTPServerTransport } from '@modelcontextprotocol/sdk/server/webStandardStreamableHttp.js';
import { createKazanMcpServer } from '../mcp/create-server.js';

export const config = {
  maxDuration: 60,
};

function nodeReqToWebRequest(req) {
  const proto = req.headers['x-forwarded-proto'] || 'https';
  const host = req.headers.host || 'api.pepperoni.tatar';
  const url = `${proto}://${host}${req.url || '/api/mcp'}`;

  const headers = new Headers();
  for (const [key, value] of Object.entries(req.headers)) {
    if (value == null) continue;
    headers.set(key, Array.isArray(value) ? value.join(', ') : String(value));
  }

  let body;
  if (req.method && !['GET', 'HEAD'].includes(req.method.toUpperCase())) {
    if (typeof req.body === 'string') body = req.body;
    else if (Buffer.isBuffer(req.body)) body = req.body;
    else if (req.body != null) body = JSON.stringify(req.body);
  }

  return new Request(url, { method: req.method || 'POST', headers, body });
}

async function sendWebResponse(webRes, res) {
  res.status(webRes.status);
  webRes.headers.forEach((value, key) => {
    if (key.toLowerCase() === 'transfer-encoding') return;
    res.setHeader(key, value);
  });
  const buffer = Buffer.from(await webRes.arrayBuffer());
  res.end(buffer);
}

export default async function handler(req, res) {
  if (req.method === 'OPTIONS') {
    res.setHeader('Access-Control-Allow-Origin', '*');
    res.setHeader('Access-Control-Allow-Methods', 'GET, POST, DELETE, OPTIONS');
    res.setHeader('Access-Control-Allow-Headers', 'Content-Type, MCP-Protocol-Version, Mcp-Session-Id');
    return res.status(204).end();
  }

  const transport = new WebStandardStreamableHTTPServerTransport({
    sessionIdGenerator: undefined,
    enableJsonResponse: true,
  });

  const server = createKazanMcpServer();
  await server.connect(transport);

  try {
    const webReq = nodeReqToWebRequest(req);
    const webRes = await transport.handleRequest(webReq);
    res.setHeader('Access-Control-Allow-Origin', '*');
    await sendWebResponse(webRes, res);
  } catch (err) {
    res.setHeader('Access-Control-Allow-Origin', '*');
    res.status(500).json({ error: err.message || 'mcp_error' });
  } finally {
    await server.close().catch(() => {});
  }
}
