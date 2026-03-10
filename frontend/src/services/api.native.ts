/**
 * Native API service for Expo/React Native.
 * Uses EXPO_PUBLIC_API_URL when available.
 */

const API_BASE_URL = process.env.EXPO_PUBLIC_API_URL || 'http://10.0.2.2:8000/api';

export type ReceiptInferenceApiItem = {
  product: string;
  price: string;
  amount: number | null;
};

export type ReceiptInferenceApiResponse = {
  engine: 'donut';
  device: string;
  model_source: string;
  processor_source: string;
  using_checkpoint_fallback: boolean;
  total: number | null;
  items: ReceiptInferenceApiItem[];
  raw_prediction?: { items?: Array<{ product?: string; price?: string }> };
};

async function request<T>(path: string, options?: RequestInit): Promise<T> {
  const url = `${API_BASE_URL}${path}`;
  const hasFormDataBody = typeof FormData !== 'undefined' && options?.body instanceof FormData;

  const response = await fetch(url, {
    ...options,
    headers: {
      ...(hasFormDataBody ? {} : { 'Content-Type': 'application/json' }),
      ...options?.headers,
    },
  });

  if (!response.ok) {
    const text = await response.text();
    let message = `Error ${response.status}`;

    try {
      const json = JSON.parse(text);
      if (typeof json?.message === 'string' && json.message.trim()) {
        message = json.message;
      } else if (typeof json?.detail === 'string' && json.detail.trim()) {
        message = json.detail;
      }
    } catch {
      if (text) message = text.slice(0, 140);
    }

    throw new Error(message);
  }

  return response.json();
}

function inferUploadMimeType(uri: string, fallbackMimeType?: string): string {
  if (fallbackMimeType && fallbackMimeType.trim()) return fallbackMimeType;
  const lowerUri = uri.toLowerCase();
  if (lowerUri.endsWith('.png')) return 'image/png';
  if (lowerUri.endsWith('.webp')) return 'image/webp';
  if (lowerUri.endsWith('.bmp')) return 'image/bmp';
  return 'image/jpeg';
}

function inferUploadFileName(uri: string, fallbackName?: string): string {
  if (fallbackName && fallbackName.trim()) return fallbackName;
  const sanitized = uri.split(/[\\/]/).pop()?.split('?')[0]?.trim();
  return sanitized || 'receipt.jpg';
}

export const apiService = {
  users: {
    list: () => request<any[]>('/users'),
    create: (payload: { email: string; name?: string }) =>
      request<any>('/users', {
        method: 'POST',
        body: JSON.stringify(payload),
      }),
  },
  auth: {
    login: (email: string) =>
      request<any>('/auth/login', {
        method: 'POST',
        body: JSON.stringify({ email }),
      }),
    register: (email: string, name?: string) =>
      request<any>('/auth/register', {
        method: 'POST',
        body: JSON.stringify({ email, name }),
      }),
  },
  summary: {
    get: (userId: string) => request<any>(`/summary?userId=${userId}`),
  },
  groups: {
    list: () => request<any[]>('/groups'),
    get: (id: string) => request<any>(`/groups/${id}`),
    getExpenses: (id: string) => request<any[]>(`/groups/${id}/expenses`),
    getBalances: (id: string) => request<any[]>(`/groups/${id}/balances`),
    create: (payload: { name: string; memberIds?: number[]; userId?: number }) =>
      request<any>('/groups', {
        method: 'POST',
        body: JSON.stringify(payload),
      }),
  },
  expenses: {
    create: (expenseData: any) =>
      request<any>('/expenses', {
        method: 'POST',
        body: JSON.stringify(expenseData),
      }),
    list: () => request<any[]>('/expenses'),
  },
  pyg: {
    get: (userId: number) => request<any[]>(`/pyg/${userId}`),
  },
  receipts: {
    infer: (payload: { uri: string; mimeType?: string; fileName?: string }) => {
      const form = new FormData();
      form.append('file', {
        uri: payload.uri,
        name: inferUploadFileName(payload.uri, payload.fileName),
        type: inferUploadMimeType(payload.uri, payload.mimeType),
      } as any);

      return request<ReceiptInferenceApiResponse>('/receipt-inference', {
        method: 'POST',
        body: form,
        headers: {
          Accept: 'application/json',
        },
      });
    },
    status: () => request<any>('/receipt-inference/status'),
  },
};
