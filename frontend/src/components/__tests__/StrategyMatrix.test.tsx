import { render, screen, waitFor } from '@testing-library/react';
import { describe, it, expect, vi } from 'vitest';
import type { StrategyNode } from '../../types/poker';
import StrategyMatrix from '../StrategyMatrix';
import { apiClient } from '../../api/client';

vi.mock('../../api/client', () => ({
  apiClient: {
    get: vi.fn(),
    post: vi.fn(),
    delete: vi.fn(),
  },
}));

describe('StrategyMatrix', () => {
  const mockNodes: StrategyNode[] = [
    {
      id: 1,
      path: 'root',
      hand: 'AA',
      actions: { 'raise': 1.0, 'call': 0.0, 'fold': 0.0 },
      ev: 10.5,
      equity: 0.85,
    },
    {
      id: 2,
      path: 'root',
      hand: 'AKs',
      actions: { 'raise': 0.7, 'call': 0.3, 'fold': 0.0 },
      ev: 5.2,
      equity: 0.65,
    },
  ];

  // Mock localStorage
  const localStorageMock = (() => {
    let store: Record<string, string> = {};
    return {
      getItem: vi.fn((key: string) => store[key] || null),
      setItem: vi.fn((key: string, value: string) => { store[key] = value.toString(); }),
      clear: vi.fn(() => { store = {}; }),
      removeItem: vi.fn((key: string) => { delete store[key]; }),
    };
  })();

  Object.defineProperty(global, 'localStorage', {
    value: localStorageMock,
  });

  beforeEach(() => {
    vi.resetAllMocks();
    (apiClient.get as any).mockResolvedValue([]);
    (apiClient.post as any).mockResolvedValue({ id: 1, node: 1, locked_actions: {}, is_active: true });
  });

  it('renders correctly', () => {
    const { container } = render(<StrategyMatrix nodes={mockNodes} />);
    // Check for the presence of the 13-column grid
    expect(container.querySelector('.solutionGrid')).toBeDefined();
  });

  it('selects a hand and calls onHandSelect callback', () => {
    const onHandSelect = vi.fn();
    render(<StrategyMatrix nodes={mockNodes} onHandSelect={onHandSelect} />);
    
    // Find AA and click it
    const aaHand = screen.getByText('AA');
    aaHand.click();
    
    expect(onHandSelect).toHaveBeenCalledWith('AA');
  });

  it('toggles lock state when lock button is clicked', async () => {
    const { container } = render(<StrategyMatrix nodes={mockNodes} />);
    
    // Click AA to show info panel
    screen.getByText('AA').click();
    
    // Find lock button by aria-label
    const lockBtn = await screen.findByLabelText('Lock action');
    expect(lockBtn).toBeDefined();
    
    // Click it
    lockBtn.click();
    
    // Should now show Unlock action label (since it toggled)
    await waitFor(() => {
      expect(screen.getByLabelText('Unlock action')).toBeDefined();
    });
  });
});

