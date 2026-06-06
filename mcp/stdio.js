#!/usr/bin/env node
import { StdioServerTransport } from '@modelcontextprotocol/sdk/server/stdio.js';
import { createKazanMcpServer } from './create-server.js';

const server = createKazanMcpServer();
const transport = new StdioServerTransport();
await server.connect(transport);
