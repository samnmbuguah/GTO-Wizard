import { render, screen, fireEvent, waitFor, act } from '@testing-library/react';
import { vi, describe, it, expect, beforeEach } from 'vitest';
import LibraryView from '../LibraryView';
import { BrowserRouter } from 'react-router-dom';
import '@testing-library/jest-dom';

// Mock localStorage
const store: Record<string, string> = {};
const localStorageMock = {
  getItem: vi.fn((key: string) => store[key] || null),
  setItem: vi.fn((key: string, value: string) => { store[key] = value.toString(); }),
  clear: vi.fn(() => { Object.keys(store).forEach(k => delete store[k]); }),
  removeItem: vi.fn((key: string) => { delete store[key]; }),
  length: 0,
  key: vi.fn((_index: number) => null),
};

vi.stubGlobal('localStorage', localStorageMock);
vi.stubGlobal('fetch', vi.fn());

const mockSolutions = [
  { id: 1, name: 'UTG vs BB 100bb', rake: 0.05, stack_depth: 100, flop_texture: 'High' },
  { id: 2, name: 'BTN vs BB 40bb', rake: 0.025, stack_depth: 40, flop_texture: 'Low' },
];

describe('LibraryView Component', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    localStorage.clear();
    localStorage.setItem('gto_token', 'test-token');
    (global.fetch as any).mockResolvedValue({
      ok: true,
      json: async () => mockSolutions,
    });
  });

  const renderLibrary = () => {
    render(
      <BrowserRouter>
        <LibraryView />
      </BrowserRouter>
    );
  };

  it('renders solutions and filters correctly', async () => {
    renderLibrary();
    
    await waitFor(() => {
      expect(screen.getByText('UTG vs BB 100bb')).toBeInTheDocument();
      expect(screen.getByText('BTN vs BB 40bb')).toBeInTheDocument();
    });

    expect(screen.getByPlaceholderText(/search/i)).toBeInTheDocument();
  });

  it('filters by search term', async () => {
    renderLibrary();
    
    await waitFor(() => screen.getByText('UTG vs BB 100bb'));

    const searchInput = screen.getByPlaceholderText(/search/i);
    fireEvent.change(searchInput, { target: { value: 'UTG' } });

    expect(screen.getByText('UTG vs BB 100bb')).toBeInTheDocument();
    expect(screen.queryByText('BTN vs BB 40bb')).not.toBeInTheDocument();
  });

  it('triggers refetch on filter change', async () => {
    renderLibrary();
    
    await waitFor(() => screen.getByText('UTG vs BB 100bb'));

    const rakeSelect = screen.getByDisplayValue('Any Rake');
    fireEvent.change(rakeSelect, { target: { value: '0.05' } });

    await waitFor(() => {
      expect(global.fetch).toHaveBeenCalledWith(
        expect.stringContaining('rake=0.05'),
        expect.any(Object)
      );
    });
  });
});
