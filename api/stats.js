const AI_BOTS = {
  'GPTBot': 'ChatGPT (OpenAI)',
  'ChatGPT-User': 'ChatGPT Browse',
  'OAI-SearchBot': 'ChatGPT Search',
  'PerplexityBot': 'Perplexity',
  'ClaudeBot': 'Claude (Anthropic)',
  'Claude-Web': 'Claude Web',
  'GoogleOther': 'Google AI / Gemini',
  'Google-Extended': 'Google AI Training',
  'Applebot-Extended': 'Apple Intelligence',
  'cohere-ai': 'Cohere',
  'Bytespider': 'ByteDance / TikTok',
  'CCBot': 'Common Crawl',
  'anthropic-ai': 'Anthropic',
  'Amazonbot': 'Amazon Alexa',
  'Meta-ExternalAgent': 'Meta AI',
  'meta-externalagent': 'Meta AI',
  'YouBot': 'You.com',
  'DuckAssistBot': 'DuckDuckGo AI',
  'Groks': 'Grok (xAI)',
  'facebookexternalhit': 'Facebook',
  'Twitterbot': 'Twitter/X',
  'LinkedInBot': 'LinkedIn',
  'Slackbot': 'Slack',
  'TelegramBot': 'Telegram',
  'WhatsApp': 'WhatsApp',
  'YandexBot': 'Yandex',
  'Googlebot': 'Google Search',
  'bingbot': 'Bing',
  'DotBot': 'Moz SEO',
  'AhrefsBot': 'Ahrefs SEO',
  'SemrushBot': 'Semrush SEO',
};

function detectBot(userAgent) {
  if (!userAgent) return null;
  for (const [key, name] of Object.entries(AI_BOTS)) {
    if (userAgent.includes(key)) return { key, name };
  }
  return null;
}

let visitLog = [];
const MAX_LOG = 500;

export function logVisit(req) {
  const ua = req.headers?.['user-agent'] || '';
  const bot = detectBot(ua);
  const entry = {
    timestamp: new Date().toISOString(),
    path: req.url || req.query?.path || '/api/products',
    ip: req.headers?.['x-forwarded-for']?.split(',')[0] || req.headers?.['x-real-ip'] || 'unknown',
    country: req.headers?.['cf-ipcountry'] || 'unknown',
    bot: bot ? bot.name : null,
    botKey: bot ? bot.key : null,
    userAgent: ua.substring(0, 200),
    isBot: !!bot,
  };
  visitLog.unshift(entry);
  if (visitLog.length > MAX_LOG) visitLog = visitLog.slice(0, MAX_LOG);
  return entry;
}

export default function handler(req, res) {
  const botVisits = visitLog.filter((v) => v.isBot);
  const botCounts = {};
  for (const v of botVisits) {
    botCounts[v.bot] = (botCounts[v.bot] || 0) + 1;
  }

  const countryCounts = {};
  for (const v of visitLog) {
    countryCounts[v.country] = (countryCounts[v.country] || 0) + 1;
  }

  const result = {
    service: 'Pepperoni.tatar API Analytics',
    totalVisits: visitLog.length,
    botVisits: botVisits.length,
    humanVisits: visitLog.length - botVisits.length,
    botBreakdown: botCounts,
    countryBreakdown: countryCounts,
    recentBotVisits: botVisits.slice(0, 20).map((v) => ({
      bot: v.bot,
      path: v.path,
      country: v.country,
      time: v.timestamp,
    })),
    recentVisits: visitLog.slice(0, 10).map((v) => ({
      bot: v.bot || 'Human',
      path: v.path,
      country: v.country,
      time: v.timestamp,
      ua: v.userAgent.substring(0, 100),
    })),
    note: 'Stats are in-memory and reset on cold start. For persistent analytics, check Cloudflare Dashboard → Security → Bots → AI Audit.',
  };

  res.setHeader('Content-Type', 'application/json; charset=utf-8');
  res.setHeader('Cache-Control', 'no-cache');
  res.status(200).json(result);
}
