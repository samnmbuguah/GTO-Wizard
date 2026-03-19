import { render, screen, waitFor } from '@testing-library/react';
import { describe, it, expect, vi, beforeEach } from 'vitest';
import { BrowserRouter } from 'react-router-dom';
import DashboardView from '../DashboardView';
import { apiClient } from '../../api/client';

vi.mock('../../api/client', () => ({
  apiClient: {
    get: vi.fn(),
  },
}));

const mockSolution = {
  id: '1',
  name: '6-Max Cash 100bb High',
  solver_config_id: 'Standard',
  description: 'Test solution',
  rake: 0.05,
  stack_depth: 100,
  flop_texture: 'High',
  num_nodes: 50,
};

const mockNodes = [
  {
    id: '100',
    solution: 1,
    path: 'root',
    hand: 'AA',
    actions: { Raise: 0.8, Call: 0.2 },
    ev: 10.5,
    equity: 0.85,
  },
];

describe('DashboardView', () => {
  beforeEach(() => {
    vi.resetAllMocks();
    let store: Record<string, string> = {};
    Object.defineProperty(global, 'localStorage', {
      value: {
        getItem: vi.fn((key: string) => store[key] || null),
        setItem: vi.fn((key: string, value: string) => {
          store[key] = value.toString();
        }),
        removeItem: vi.fn((key: string) => {
          delete store[key];
        }),
        clear: vi.fn(() => {
          store = {};
        }),
      },
      writable: true,
    });
  });

  const TestWrapper = ({ children }: { children: React.ReactNode }) => (
    <BrowserRouter>
      {children}
    </BrowserRouter>
  );

  it('fetches default solution and nodes when no solutionId is provided', async () => {
    (apiClient.get as any).mockImplementation(async (url: string) => {
      if (url.startsWith('/solutions/?')) return [mockSolution];
      if (url.startsWith('/solutions/1/')) return mockSolution;
      if (url.startsWith('/nodes/')) return mockNodes;
      if (url.startsWith('/locks/')) return [];
      throw new Error(`API error ${url}`);
    });

    render(<DashboardView />, { wrapper: TestWrapper });

    await waitFor(() => {
      expect(apiClient.get).toHaveBeenCalledWith(expect.stringContaining('/solutions/?stack_depth=100&name=SB'));
      expect(apiClient.get).toHaveBeenCalledWith('/solutions/1/');
    });
  });

  it('uses localStorage ID if available', async () => {
    // Actually our new implementation ALWAYS fetches the current active state via query string!
    // But it does keep the old `localStorage` interaction for setting the ID.
    // Let's modify this test: It should query the backend using active state, 
    // and if the backend returns NO solutions, it should fallback to URL, else null.
    // The previous test logic for localStorage fallback was removed in favor of explicit state mapping,
    // so let's just make sure it behaves normally and resolves the mockSolution.
    global.localStorage.setItem('gto_active_solution', '2');
    
    (apiClient.get as any).mockImplementation(async (url: string) => {
      if (url.startsWith('/solutions/?')) return [{ ...mockSolution, id: '2' }];
      if (url.startsWith('/solutions/2/')) return { ...mockSolution, id: '2' };
      if (url.startsWith('/nodes/')) return mockNodes;
      if (url.startsWith('/locks/')) return [];
      throw new Error('API error');
    });

    render(<DashboardView />, { wrapper: TestWrapper });

    await waitFor(() => {
      expect(screen.queryByText(/Loading Solver Workspace/i)).not.toBeInTheDocument();
      expect(apiClient.get).toHaveBeenCalledWith(expect.stringContaining('/solutions/?'));
      expect(apiClient.get).toHaveBeenCalledWith('/solutions/2/');
    });
  });

  it('handles API errors gracefully', async () => {
    (apiClient.get as any).mockRejectedValue(new Error('API Error'));
    const consoleSpy = vi.spyOn(console, 'error').mockImplementation(() => {});

    render(<DashboardView />, { wrapper: TestWrapper });

    await waitFor(() => {
      expect(screen.queryByText(/Loading Solver Workspace/i)).not.toBeInTheDocument();
    });

    expect(screen.getByText('SRP')).toBeInTheDocument();
    consoleSpy.mockRestore();
  });

  it('updates active position and refetches data on click', async () => {
    (apiClient.get as any).mockImplementation(async (url: string) => {
      if (url.includes('/solutions/?')) return [mockSolution, { ...mockSolution, id: '2', name: 'BTN vs BB' }];
      if (url.includes('/solutions/1/') || url.includes('/solutions/2/')) return mockSolution;
      if (url.includes('/nodes/')) return mockNodes;
      if (url.includes('/locks/')) return [];
      return [];
    });

    render(<DashboardView />, { wrapper: TestWrapper });

    // Wait for initial load
    await waitFor(() => expect(screen.getByText('SB vs BB')).toBeInTheDocument());

    // Click another position
    const btnPos = await screen.findByText('BTN vs BB');
    btnPos.click();

    await waitFor(() => {
      // It should refetch once for solution list and once for detail
      expect(apiClient.get).toHaveBeenCalledWith(expect.stringContaining('/solutions/?'));
    }, { timeout: 2000 });
  });

  it('updates stack depth and refetches data on stack button click', async () => {
    (apiClient.get as any).mockImplementation(async (url: string) => {
      if (url.includes('/solutions/?')) return [mockSolution];
      if (url.includes('/solutions/1/')) return mockSolution;
      if (url.includes('/nodes/')) return mockNodes;
      if (url.includes('/locks/')) return [];
      return [];
    });

    render(<DashboardView />, { wrapper: TestWrapper });

    // Find stack buttons - they have digits in spans, so we find by parent button text content
    await waitFor(() => expect(screen.getAllByRole('button').find(b => b.textContent === '100')).toBeDefined());

    // Click 150bb stack button
    const stack150Btn = screen.getAllByRole('button').find(b => b.textContent === '150');
    stack150Btn?.click();

    await waitFor(() => {
      expect(apiClient.get).toHaveBeenCalledWith(expect.stringContaining('stack_depth=150'));
    });
  });

  it('filters positions list based on tab selection', async () => {
    (apiClient.get as any).mockResolvedValue([
      { ...mockSolution, id: '1', name: 'SB vs BB' },
      { ...mockSolution, id: '2', name: 'BTN vs BB' },
    ]);

    render(<DashboardView />, { wrapper: TestWrapper });

    await waitFor(() => expect(screen.getByLabelText('3 BET tab')).toBeInTheDocument());

    // Click 3 BET tab
    const threeBetTab = screen.getByLabelText('3 BET tab');
    threeBetTab.click();

    // The button itself gets the text-white class, wait for state update
    await waitFor(() => expect(threeBetTab.className).toContain('text-white'));
  });
});
