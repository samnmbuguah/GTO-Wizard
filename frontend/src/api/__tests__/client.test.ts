import { describe, it, expect, vi, beforeEach } from 'vitest';
import { apiClient } from '../client';

// Mock localStorage
const store: Record<string, string> = {};
const localStorageMock = {
  getItem: vi.fn((key: string) => store[key] || null),
  setItem: vi.fn((key: string, value: string) => { store[key] = value.toString(); }),
  removeItem: vi.fn((key: string) => { delete store[key]; }),
  clear: vi.fn(() => { Object.keys(store).forEach(k => delete store[k]); }),
};
vi.stubGlobal('localStorage', localStorageMock);

const mockFetch = vi.fn();
vi.stubGlobal('fetch', mockFetch);

describe('apiClient', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    localStorage.clear();
  });

  it('performs a GET request successfully', async () => {
    const mockData = { id: 1, name: 'Test' };
    mockFetch.mockResolvedValue({
      ok: true,
      json: async () => mockData,
    });

    const result = await apiClient.get('/test/');
    expect(result).toEqual(mockData);
    expect(mockFetch).toHaveBeenCalledWith('/api/test/', expect.any(Object));
  });

  it('performs a GET request with query params', async () => {
    mockFetch.mockResolvedValue({
      ok: true,
      json: async () => ({}),
    });

    await apiClient.get('/test/', { foo: 'bar', baz: '' });
    expect(mockFetch).toHaveBeenCalledWith('/api/test/?foo=bar', expect.any(Object));
  });

  it('performs a POST request (JSON) successfully', async () => {
    const mockData = { success: true };
    mockFetch.mockResolvedValue({
      ok: true,
      json: async () => mockData,
    });

    const body = { name: 'Test' };
    const result = await apiClient.post('/test/', body);
    
    expect(result).toEqual(mockData);
    const fetchArgs = mockFetch.mock.calls[0];
    expect(fetchArgs[1].method).toBe('POST');
    expect(fetchArgs[1].body).toBe(JSON.stringify(body));
    expect(fetchArgs[1].headers.get('Content-Type')).toBe('application/json');
  });

  it('performs a POST request (FormData) successfully', async () => {
    const mockData = { success: true };
    mockFetch.mockResolvedValue({
      ok: true,
      json: async () => mockData,
    });

    const formData = new FormData();
    formData.append('file', new File([''], 'test.zip'));
    
    const result = await apiClient.post('/test/', formData);
    
    expect(result).toEqual(mockData);
    const fetchArgs = mockFetch.mock.calls[0];
    expect(fetchArgs[1].method).toBe('POST');
    expect(fetchArgs[1].body).toBe(formData);
    expect(fetchArgs[1].headers).not.toHaveProperty('Content-Type');
  });

  it('handles API errors correctly', async () => {
    mockFetch.mockResolvedValue({
      ok: false,
      status: 400,
      json: async () => ({ error: 'Bad Request Message' }),
    });

    await expect(apiClient.get('/test/')).rejects.toEqual({ error: 'Bad Request Message' });
  });

  it('handles API errors without JSON payload', async () => {
    mockFetch.mockResolvedValue({
      ok: false,
      status: 500,
      json: async () => { throw new Error('Not JSON'); },
    });

    await expect(apiClient.get('/test/')).rejects.toEqual({ detail: 'An unexpected error occurred' });
  });
});
