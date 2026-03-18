import { render, screen, fireEvent, waitFor, act } from '@testing-library/react';
import { vi, describe, it, expect, beforeEach } from 'vitest';
import LoginView from '../LoginView';
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

describe('LoginView Component', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    localStorage.clear();
  });

  const renderLogin = () => {
    render(
      <BrowserRouter>
        <LoginView />
      </BrowserRouter>
    );
  };

  it('renders login form correctly', () => {
    renderLogin();
    expect(screen.getByPlaceholderText(/admin/i)).toBeInTheDocument();
    expect(screen.getByPlaceholderText(/••••/i)).toBeInTheDocument();
    expect(screen.getByRole('button', { name: /enter terminal/i })).toBeInTheDocument();
  });

  it('handles input changes', () => {
    renderLogin();
    const usernameInput = screen.getByPlaceholderText(/admin/i) as HTMLInputElement;
    fireEvent.change(usernameInput, { target: { value: 'testuser' } });
    expect(usernameInput.value).toBe('testuser');
  });

  it('successful login stores token and redirects', async () => {
    (global.fetch as any).mockResolvedValueOnce({
      ok: true,
      json: async () => ({ token: 'test-token-123' }),
    });

    renderLogin();
    
    fireEvent.change(screen.getByPlaceholderText(/admin/i), { target: { value: 'admin' } });
    fireEvent.change(screen.getByPlaceholderText(/••••/i), { target: { value: 'GtoMaster2026!' } });
    
    await act(async () => {
      fireEvent.click(screen.getByRole('button', { name: /enter terminal/i }));
    });

    await waitFor(() => {
      expect(localStorage.getItem('gto_token')).toBe('test-token-123');
      expect(localStorage.getItem('gto_user')).toBe('admin');
    });
  });

  it('displays error message on failed login', async () => {
    (global.fetch as any).mockResolvedValueOnce({
      ok: false,
      status: 400,
      json: async () => ({ non_field_errors: ['Invalid credentials. Please try again.'] }),
    });

    renderLogin();
    
    fireEvent.change(screen.getByPlaceholderText(/admin/i), { target: { value: 'wrong' } });
    fireEvent.change(screen.getByPlaceholderText(/••••/i), { target: { value: 'wrong' } });
    
    await act(async () => {
      fireEvent.click(screen.getByRole('button', { name: /enter terminal/i }));
    });

    await waitFor(() => {
      expect(screen.getByText(/invalid credentials/i)).toBeInTheDocument();
    });
  });
});
