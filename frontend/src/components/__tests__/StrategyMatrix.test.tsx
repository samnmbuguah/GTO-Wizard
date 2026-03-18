import { render, screen } from '@testing-library/react';
import { describe, it, expect, vi } from 'vitest';
import StrategyMatrix from '../StrategyMatrix';

describe('StrategyMatrix', () => {
  const mockNodes = [
    {
      path: 'root',
      hand: 'AA',
      actions: { 'raise': 1.0 },
      ev: 10.5,
      equity: 0.85,
    },
    {
      path: 'root',
      hand: 'AKs',
      actions: { 'raise': 0.7, 'call': 0.3 },
      ev: 5.2,
      equity: 0.65,
    },
  ];

  it('renders correctly', () => {
    render(<StrategyMatrix nodes={mockNodes} />);
    // Check if some hand cells are rendered
    expect(screen.getByText('AA')).toBeInTheDocument();
    expect(screen.getByText('AKs')).toBeInTheDocument();
  });

  it('calls onHandSelect when a cell is clicked', () => {
    const onSelect = vi.fn();
    render(<StrategyMatrix nodes={mockNodes} onHandSelect={onSelect} />);
    
    const aaCell = screen.getByText('AA');
    aaCell.click();
    
    expect(onSelect).toHaveBeenCalledWith('AA');
  });
});
