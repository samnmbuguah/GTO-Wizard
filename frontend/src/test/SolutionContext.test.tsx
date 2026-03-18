import { render, act, screen } from '@testing-library/react';
import { describe, it, expect, beforeEach, vi } from 'vitest';
import { MemoryRouter } from 'react-router-dom';
import { SolutionProvider, useSolution } from '../contexts/SolutionContext';
import React from 'react';

// Helper component to test the hook
const TestComponent = () => {
  const { activeSolutionId, setActiveSolutionId } = useSolution();
  return (
    <div>
      <span data-testid="active-id">{activeSolutionId || 'none'}</span>
      <button onClick={() => setActiveSolutionId('new-id')}>Set ID</button>
    </div>
  );
};

// Manual mock for localStorage
const localStorageMock = (() => {
  let store: Record<string, string> = {};
  return {
    getItem: (key: string) => store[key] || null,
    setItem: (key: string, value: string) => { store[key] = value.toString(); },
    clear: () => { store = {}; },
    removeItem: (key: string) => { delete store[key]; },
  };
})();
Object.defineProperty(window, 'localStorage', { value: localStorageMock });

describe('SolutionContext', () => {
  beforeEach(() => {
    window.localStorage.clear();
    vi.clearAllMocks();
  });

  it('initializes from localStorage', () => {
    window.localStorage.setItem('gto_active_solution', 'stored-id');
    
    render(
      <MemoryRouter>
        <SolutionProvider>
          <TestComponent />
        </SolutionProvider>
      </MemoryRouter>
    );

    expect(screen.getByTestId('active-id').textContent).toBe('stored-id');
  });

  it('updates localStorage when ID changes', () => {
    render(
      <MemoryRouter>
        <SolutionProvider>
          <TestComponent />
        </SolutionProvider>
      </MemoryRouter>
    );

    act(() => {
      screen.getByText('Set ID').click();
    });

    expect(screen.getByTestId('active-id').textContent).toBe('new-id');
    expect(window.localStorage.getItem('gto_active_solution')).toBe('new-id');
  });
});
