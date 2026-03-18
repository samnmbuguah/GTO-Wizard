import '@testing-library/jest-dom';

if (typeof document !== 'undefined' && !document.elementFromPoint) {
  document.elementFromPoint = (_x: number, _y: number) => {
    return null; // Basic shim
  };
}
