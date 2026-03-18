import { render, screen } from '@testing-library/react';
import { describe, it, expect } from 'vitest';
import BoardSelector from '../components/BoardSelector';

describe('BoardSelector', () => {
  it('renders correctly with default board', () => {
    render(<BoardSelector board={['6h', '6c', 'Ts']} />);
    
    // Rank '6' appears in board display (2) + grid (1 per suit = 4) = 6 times
    expect(screen.getAllByText('6')).toHaveLength(6);
    // Rank 'T' appears in board display (1) + grid (4) = 5 times
    expect(screen.getAllByText('T')).toHaveLength(5);
    // Reset is now an icon button with title
    expect(screen.getByTitle(/Clear Board/i)).toBeInTheDocument();
  });

  it('applies correct colors for suits', () => {
    render(<BoardSelector board={['Ah', 'Ad', 'Ac', 'As']} />);
    
    const hearts = screen.getAllByText('♥')[0];
    const diamonds = screen.getAllByText('♦')[0];
    const clubs = screen.getAllByText('♣')[0];
    const spades = screen.getAllByText('♠')[0];

    expect(hearts).toHaveClass('text-rose-500');
    expect(diamonds).toHaveClass('text-blue-500');
    expect(clubs).toHaveClass('text-emerald-500');
    expect(spades).toHaveClass('text-white');
  });
});
