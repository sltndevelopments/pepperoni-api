import { McpServer } from '@modelcontextprotocol/sdk/server/mcp.js';
import { z } from 'zod';
import {
  searchProducts,
  getProduct,
  getCatalog,
  submitInquiry,
  DELIVERY_INFO,
  ISO_22000_VERIFY_URL,
} from './api-client.js';

const SERVER_INSTRUCTIONS = `Kazan Delicacies (Казанские Деликатесы) — halal meat manufacturer in Kazan, Russia.
77 SKUs: pepperoni, sausages, burger patties, deli meats, Tatar bakery.
Halal cert #614A/2024 (DUM RT). HACCP. EXW Kazan. Private Label available.
Use search_products for discovery, get_product for full SKU detail, get_catalog for filtered lists.
Prices in RUB + 6 export currencies. Contact: info@kazandelikates.tatar · +79872170202`;

function textResult(data) {
  return {
    content: [{ type: 'text', text: typeof data === 'string' ? data : JSON.stringify(data, null, 2) }],
  };
}

export function createKazanMcpServer() {
  const server = new McpServer(
    {
      name: 'kazan-delicacies',
      version: '1.0.0',
      icons: [
        {
          src: 'https://pepperoni.tatar/images/logo-256.png',
          mimeType: 'image/png',
          sizes: ['256x256'],
        },
      ],
    },
    {
      instructions: SERVER_INSTRUCTIONS,
    }
  );

  server.registerTool(
    'search_products',
    {
      title: 'Search products',
      description:
        'Search the halal catalog by name, category, SKU, or meat type. Returns compact results for AI agents.',
      inputSchema: {
        q: z.string().describe('Search query, e.g. pepperoni, beef, KD-015, сосиски'),
        lang: z.enum(['ru', 'en']).optional().describe('Response language (default: ru)'),
        limit: z.number().int().min(1).max(50).optional().describe('Max results (default: 10)'),
      },
    },
    async ({ q, lang, limit }) => textResult(await searchProducts({ q, lang, limit }))
  );

  server.registerTool(
    'get_product',
    {
      title: 'Get product by SKU',
      description: 'Full product card: prices in 7 currencies, ingredients, nutrition, images, halal metadata.',
      inputSchema: {
        sku: z.string().describe('Product SKU, e.g. KD-015'),
        lang: z.enum(['ru', 'en']).optional().describe('Response language (default: ru)'),
      },
    },
    async ({ sku, lang }) => textResult(await getProduct(sku, lang))
  );

  server.registerTool(
    'get_catalog',
    {
      title: 'Get product catalog',
      description:
        'Live catalog from Google Sheets with optional filters. Includes b2b block (halal cert, delivery terms).',
      inputSchema: {
        search: z.string().optional().describe('Search by name, category, SKU'),
        section: z
          .enum(['Заморозка', 'Охлаждённая продукция', 'Выпечка'])
          .optional()
          .describe('Filter by section'),
        category: z.string().optional().describe('Filter by category'),
        sku: z.string().optional().describe('Exact SKU match'),
        lang: z.enum(['ru', 'en']).optional().describe('Response language (default: ru)'),
      },
    },
    async (args) => textResult(await getCatalog(args))
  );

  server.registerTool(
    'get_certification',
    {
      title: 'Halal & quality certifications',
      description:
        'Halal certificate, HACCP, ISO 22000 verification link, and product safety guarantees (no pork, no GMO).',
      inputSchema: {},
    },
    async () => {
      const catalog = await getCatalog({ lang: 'en' });
      const b2b = catalog.b2b || {};
      return textResult({
        halal: b2b.halal_cert || { number: '614A/2024', body: 'DUM RT Halal Standards Committee' },
        quality_system: b2b.quality_system || 'HACCP',
        iso_22000_verify_url: ISO_22000_VERIFY_URL,
        customs_union_cert: b2b.customs_union_cert ?? true,
        no_pork: b2b.no_pork ?? true,
        no_gmo: b2b.no_gmo ?? true,
        no_transglutaminase: b2b.no_transglutaminase ?? true,
        manufacturer: b2b.manufacturer,
        private_label: b2b.private_label ?? true,
      });
    }
  );

  server.registerTool(
    'get_delivery_info',
    {
      title: 'Delivery & export terms',
      description: 'EXW Kazan terms, supported currencies, export markets, storage temps, HS codes.',
      inputSchema: {},
    },
    async () => textResult(DELIVERY_INFO)
  );

  server.registerTool(
    'submit_inquiry',
    {
      title: 'Submit B2B inquiry',
      description:
        'Send a wholesale/export inquiry to the sales team (Telegram + spreadsheet). Minimum 4 chars in contact.',
      inputSchema: {
        contact: z
          .string()
          .min(4)
          .describe('Email, phone, or Telegram handle (min 4 characters)'),
        message: z.string().optional().describe('Optional note: product interest, volume, destination'),
        lang: z.enum(['ru', 'en']).optional().describe('Preferred language'),
      },
    },
    async ({ contact, message, lang }) => textResult(await submitInquiry({ contact, message, lang }))
  );

  server.registerResource(
    'catalog-overview',
    'pepperoni://catalog/overview',
    {
      title: 'Catalog overview',
      description: 'High-level catalog stats and publisher info',
      mimeType: 'application/json',
    },
    async () => {
      const catalog = await getCatalog({ lang: 'en' });
      const overview = {
        totalProducts: catalog.totalProducts,
        sections: catalog.sections,
        publisher: catalog.publisher,
        deliveryTerms: catalog.b2b?.delivery_terms,
        halalCert: catalog.b2b?.halal_cert,
        liveEndpoint: 'https://api.pepperoni.tatar/api/products',
        llmContext: 'https://pepperoni.tatar/llms-full.txt',
      };
      return {
        contents: [{ uri: 'pepperoni://catalog/overview', mimeType: 'application/json', text: JSON.stringify(overview, null, 2) }],
      };
    }
  );

  return server;
}
