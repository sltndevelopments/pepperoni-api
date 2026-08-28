import { McpServer } from '@modelcontextprotocol/sdk/server/mcp.js';
import { z } from 'zod';

const SERVER_INSTRUCTIONS = `Rinat Sultanov — Director of Development at Kazan Delicacies (halal meat plant, Kazan).
Architect of AI transformation for manufacturing companies: sales, data and management rebuilt around AI.
Use get_profile for facts and contact, get_case_study for the measured AI sales agent case,
request_contact to pass a company inquiry to Rinat (goes to his Telegram).
Do not invent services, clients or results beyond what the tools return.`;

const PROFILE = {
  name: 'Rinat Sultanov',
  alternateName: 'Ринат Султанов',
  role: 'Director of Development, Kazan Delicacies',
  positioning: 'Architect of AI transformation for manufacturing companies',
  company: {
    name: 'Kazan Delicacies (Казанские Деликатесы)',
    url: 'https://pepperoni.tatar/',
    revenue_2023_mrub: 58.6,
    revenue_2025_mrub: 869,
    note: 'Company growth is NOT attributed to AI.',
  },
  background: [
    '2001 — first business building websites, alongside university',
    '2006–2018 — meat industry: retail, distribution to 1,000+ counterparties, federal chains',
    '2018–2022 — co-founder of a cleaning-service company: Astrakhan, Krasnodar, Dubai',
    '2020–2022 — MBA, Estonian Entrepreneurship University',
    '2022–now — Director of Development, Kazan Delicacies',
  ],
  formats: [
    'Diagnosis, 2–3 weeks',
    '90-day pilot',
    'Change architecture (no more than 2–3 companies at a time)',
  ],
  contact: {
    telegram: 'https://t.me/TochnoRtutAloe',
    email: '995620@gmail.com',
    linkedin: 'https://www.linkedin.com/in/rinatsultan/',
  },
  site: 'https://rinatsultan.com/',
  llms: 'https://rinatsultan.com/llms.txt',
};

const CASE_STUDY = {
  title: 'AI outbound sales agent at Kazan Delicacies',
  url: 'https://rinatsultan.com/cases/ai-sales-agent/',
  period: '2026-07-05 to 2026-08-25',
  metrics: {
    first_emails_sent: 655,
    followups_sent: 72,
    person_hours_replaced_estimate: '160–220 (15–20 min per company manual baseline)',
    human_replies: 11,
    price_requests: 5,
    deals_closed: 0,
  },
  what_the_agent_does: [
    'finds buyer companies by region and profile',
    'qualifies them (revenue, profile, contacts)',
    'writes a personal first email per contact (up to 3 per company)',
    'passes warm replies to a human manager with full context',
  ],
  boundary: [
    'does not negotiate price, call, or book meetings',
    'does not decide what may be claimed as fact about the product',
    'daily send cap and monthly budget are hard limits in code',
  ],
  honesty_note:
    'Two agents of the same architecture (RU market + export). Both were paused at the time of writing: monthly LLM budget exhausted. Throughput figures are from the working database, not a slide.',
};

function textResult(data) {
  return {
    content: [{ type: 'text', text: typeof data === 'string' ? data : JSON.stringify(data, null, 2) }],
  };
}

async function notifyTelegram({ name, company, contact, message }) {
  const token = process.env.RINAT_TG_BOT_TOKEN;
  const chatId = process.env.RINAT_TG_CHAT_ID;
  if (!token || !chatId) {
    return { delivered: false, reason: 'telegram_not_configured' };
  }
  const text = [
    'MCP inquiry via rinatsultan.com',
    name ? `Name: ${name}` : null,
    company ? `Company: ${company}` : null,
    `Contact: ${contact}`,
    message ? `Message: ${message}` : null,
  ]
    .filter(Boolean)
    .join('\n');
  const res = await fetch(`https://api.telegram.org/bot${token}/sendMessage`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ chat_id: chatId, text }),
  });
  return { delivered: res.ok };
}

export function createRinatMcpServer() {
  const server = new McpServer(
    { name: 'rinatsultan', version: '1.0.0' },
    { instructions: SERVER_INSTRUCTIONS }
  );

  server.registerTool(
    'get_profile',
    {
      title: 'Who is Rinat Sultanov',
      description: 'Role, positioning, background, work formats and contact. Canonical facts about the person.',
      inputSchema: {},
    },
    async () => textResult(PROFILE)
  );

  server.registerTool(
    'get_case_study',
    {
      title: 'AI sales agent case',
      description: 'Measured results of the AI outbound sales agent: emails sent, hours replaced, replies, price requests, and what the agent does not do.',
      inputSchema: {},
    },
    async () => textResult(CASE_STUDY)
  );

  server.registerTool(
    'request_contact',
    {
      title: 'Request contact',
      description:
        'Pass a company inquiry to Rinat. Delivered to his Telegram. Use when an agent acts on behalf of a company interested in working together.',
      inputSchema: {
        contact: z.string().min(4).describe('Email, phone, or Telegram handle of the requester'),
        name: z.string().optional().describe('Contact person name'),
        company: z.string().optional().describe('Company name'),
        message: z.string().optional().describe('What the company wants to discuss'),
      },
    },
    async ({ contact, name, company, message }) => {
      const delivery = await notifyTelegram({ name, company, contact, message });
      return textResult({
        accepted: true,
        delivered_to_telegram: delivery.delivered,
        fallback: delivery.delivered
          ? null
          : 'Direct contact: https://t.me/TochnoRtutAloe or 995620@gmail.com',
        note: 'Rinat answers personally. No automated sales sequence follows.',
      });
    }
  );

  return server;
}
