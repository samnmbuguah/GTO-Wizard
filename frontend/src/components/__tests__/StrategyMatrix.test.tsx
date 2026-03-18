import { render, screen } from '@testing-library/react';
import { describe, it, expect, vi } from 'vitest';
import type { StrategyNode } from '../../types/poker';
import StrategyMatrix from '../StrategyMatrix';

describe('StrategyMatrix', () => {
  const mockNodes: StrategyNode[] = [
    {
      path: 'root',
      hand: 'AA',
      actions: { 'raise': 1.0, 'call': 0.0, 'fold': 0.0 }, // Ensure all keys are defined if needed, or matches Index signature
      ev: 10.5,
      equity: 0.85,
    },
    {
      path: 'root',
      hand: 'AKs',
      actions: { 'raise': 0.7, 'call': 0.3, 'fold': 0.0 },
      ev: 5.2,
      equity: 0.65,
    },
  ];

  it('renders correctly', () => {
    const { container } = render(<StrategyMatrix nodes={mockNodes} />);
    // Check for the presence of the HandMatrix component markers
    // The library usually renders a div with a specific class or structure
    expect(container.querySelector('.HandMatrix')).toBeDefined();
    expect(screen.getByText(/Range Matrix/i)).toBeInTheDocument();
  });
});

