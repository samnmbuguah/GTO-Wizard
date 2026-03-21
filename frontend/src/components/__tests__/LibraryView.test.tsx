import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import { vi, describe, it, expect, beforeEach } from 'vitest';
import LibraryView from '../LibraryView';
import { BrowserRouter } from 'react-router-dom';
import '@testing-library/jest-dom';
import { apiClient } from '../../api/client';

// Mock the API client
vi.mock('../../api/client', () => ({
  apiClient: {
    get: vi.fn(),
    post: vi.fn(),
  },
}));

const mockSolutions = [
  { id: '1', name: 'UTG vs BB 100bb', rake: 0.05, stack_depth: 100, flop_texture: 'High' },
  { id: '2', name: 'BTN vs BB 40bb', rake: 0.025, stack_depth: 40, flop_texture: 'Low' },
];

describe('LibraryView Component', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    (apiClient.get as any).mockResolvedValue(mockSolutions);
  });

  const renderLibrary = () => {
    render(
      <BrowserRouter>
        <LibraryView />
      </BrowserRouter>
    );
  };

  it('renders solutions from apiClient', async () => {
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

  it('shows no matches found state', async () => {
    renderLibrary();
    await waitFor(() => screen.getByText('UTG vs BB 100bb'));

    const searchInput = screen.getByPlaceholderText(/search/i);
    fireEvent.change(searchInput, { target: { value: 'Non-existent' } });

    expect(screen.queryByText('UTG vs BB 100bb')).not.toBeInTheDocument();
    expect(screen.getByText('No matches found')).toBeInTheDocument();
    
    // Test the clear filters button
    const clearBtn = screen.getByText('Clear all filters');
    fireEvent.click(clearBtn);
    
    expect(searchInput).toHaveValue('');
    expect(screen.getByText('UTG vs BB 100bb')).toBeInTheDocument();
  });

  it('handles the upload modal flow', async () => {
    renderLibrary();
    await waitFor(() => screen.getByText('UTG vs BB 100bb'));

    // Open modal
    const uploadBtn = screen.getByRole('button', { name: /Upload Solution/i });
    fireEvent.click(uploadBtn);

    expect(screen.getByText('Import Solver Solution')).toBeInTheDocument();

    // Mock successful upload
    (apiClient.post as any).mockResolvedValue({ status: 'success' });
    
    // Find the file input
    // The input is hidden, but testing-library still finds it by role or label
    // It's inside a label
    const fileInput = document.querySelector('input[type="file"]') as HTMLInputElement;
    expect(fileInput).toBeInTheDocument();

    const file = new File(['dummy content'], 'test.zip', { type: 'application/zip' });
    fireEvent.change(fileInput, { target: { files: [file] } });

    // Validate loading state
    expect(screen.getByText('Processing Data...')).toBeInTheDocument();

    // Validate success state
    await waitFor(() => {
      expect(screen.getByText('Import Success!')).toBeInTheDocument();
    });
    
    expect(apiClient.post).toHaveBeenCalledTimes(1);
    expect(apiClient.get).toHaveBeenCalledTimes(2); // Initial + after upload
  });
  
  it('handles the upload modal error flow', async () => {
    renderLibrary();
    await waitFor(() => screen.getByText('UTG vs BB 100bb'));

    // Open modal
    const uploadBtn = screen.getByRole('button', { name: /Upload Solution/i });
    fireEvent.click(uploadBtn);

    // Mock failed upload
    (apiClient.post as any).mockRejectedValue(new Error('Upload failed spectacularly'));
    
    const fileInput = document.querySelector('input[type="file"]') as HTMLInputElement;
    const file = new File(['dummy content'], 'test.zip', { type: 'application/zip' });
    fireEvent.change(fileInput, { target: { files: [file] } });

    // Validate error state
    await waitFor(() => {
      expect(screen.getByText('Upload failed spectacularly')).toBeInTheDocument();
    });
  });
});
