import { render, screen } from '@testing-library/react';
import { describe, it, expect } from 'vitest';
import BoardSelector from '../components/BoardSelector';

describe('BoardSelector', () => {
  it('renders correctly with default board', () => {
    render(<BoardSelector board={['6h', '6c', 'Ts']} />);
    
    // Rank '6' appears in grid 4 times (1 per suit)
    expect(screen.getAllByText('6')).toHaveLength(4);
    // Rank 'T' appears in grid 4 times 
    expect(screen.getAllByText('T')).toHaveLength(4);
  });

  it('applies correct colors for suits', () => {
    // Render with 4 aces selected
    render(<BoardSelector board={['Ah', 'Ad', 'Ac', 'As']} />);
    
    const hearts = screen.getAllByText('♥')[0];
    const diamonds = screen.getAllByText('♦')[0];
    const clubs = screen.getAllByText('♣')[0];
    const spades = screen.getAllByText('♠')[0];

    // Re-implemented tests verify parent backgrounds according to custom layout
    expect(hearts.parentElement).toHaveClass('bg-[rgba(184,15,10,0.6)]');
    expect(diamonds.parentElement).toHaveClass('bg-[rgba(0,50,73,0.6)]');
    expect(clubs.parentElement).toHaveClass('bg-[#204f00]');
    expect(spades.parentElement).toHaveClass('bg-[#070b0b]');
  });
});
