import { apiService, type ReceiptInferenceApiResponse } from './api.native';

export type InferredReceiptItem = {
  description: string;
  amount: number;
  confidence?: number;
};

export type InferredReceipt = {
  total: number | null;
  items: InferredReceiptItem[];
  engine: 'donut';
  text: string;
  lines: string[];
  confidence: number;
  debug: {
    steps: string[];
  };
};

type InferReceiptInput = {
  uri: string;
  mimeType?: string;
  fileName?: string;
};

function buildFallbackLines(response: ReceiptInferenceApiResponse): string[] {
  return response.items
    .map((item) => [item.product, item.price].filter(Boolean).join(' '))
    .filter((line) => line.trim().length > 0);
}

export async function inferReceiptWithBackend(input: InferReceiptInput): Promise<InferredReceipt> {
  const response = await apiService.receipts.infer(input);
  return {
    total: typeof response.total === 'number' ? response.total : null,
    items: response.items.map((item) => ({
      description: item.product || 'Item',
      amount: typeof item.amount === 'number' ? item.amount : 0,
      confidence: 0.99,
    })),
    engine: 'donut',
    text: JSON.stringify(response.raw_prediction ?? { items: response.items }),
    lines: buildFallbackLines(response),
    confidence: 0.99,
    debug: {
      steps: [
        `engine:${response.engine}`,
        response.using_checkpoint_fallback ? 'checkpoint_fallback:yes' : 'checkpoint_fallback:no',
      ],
    },
  };
}
