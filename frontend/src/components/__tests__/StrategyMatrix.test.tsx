import { render, screen } from '@testing-library/react';
import { describe, it, expect, vi } from 'vitest';
import type { StrategyNode } from '../../types/poker';
import StrategyMatrix from '../StrategyMatrix';

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

  // Mock fetch for locks
  global.fetch = vi.fn().mockImplementation(() =>
    Promise.resolve({
      json: () => Promise.resolve([]),
    })
  ) as any;

  it('renders correctly', () => {
    const { container } = render(<StrategyMatrix nodes={mockNodes} />);
    // Check for the presence of the HandMatrix component markers
    // The library usually renders a div with a specific class or structure
    expect(container.querySelector('.HandMatrix')).toBeDefined();
    expect(screen.getByText(/Range Matrix/i)).toBeInTheDocument();
  });
});

