declare module '@holdem-poker-tools/hand-matrix' {
  import React from 'react';

  export interface Combo {
    combo: string;
    color?: string;
    label?: string;
  }

  export interface HandMatrixProps {
    combos?: Combo[];
    onSelect?: (combo: string) => void;
    // Add other props as needed based on the library's documentation
  }

  export const HandMatrix: React.FC<HandMatrixProps>;
}
