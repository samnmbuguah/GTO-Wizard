import '@testing-library/jest-dom';
import { vi } from 'vitest';

if (typeof document !== 'undefined' && !document.elementFromPoint) {
  document.elementFromPoint = (x: number, y: number) => {
    return null; // Basic shim
  };
}
