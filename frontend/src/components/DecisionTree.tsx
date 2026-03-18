import React from 'react';

interface DecisionTreeProps {
  path: string[];
  actions: string[];
  onActionClick: (action: string) => void;
  onBreadcrumbClick: (index: number) => void;
}

const DecisionTree: React.FC<DecisionTreeProps> = ({ path, actions, onActionClick, onBreadcrumbClick }) => {
  return (
    <div className="flex flex-col gap-4 p-6 bg-slate-800/50 backdrop-blur-md rounded-xl border border-slate-700 shadow-xl">
      <div className="flex items-center gap-2 text-sm text-slate-400">
        {path.map((item, index) => (
          <React.Fragment key={index}>
            <button 
              onClick={() => onBreadcrumbClick(index)}
              className="hover:text-poker-accent transition-colors"
            >
              {item}
            </button>
            {index < path.length - 1 && <span>/</span>}
          </React.Fragment>
        ))}
      </div>
      
      <div className="flex flex-wrap gap-2">
        {actions.map(action => (
          <button
            key={action}
            onClick={() => onActionClick(action)}
            className="px-4 py-2 bg-slate-700 hover:bg-poker-accent text-white rounded-lg transition-all active:scale-95 border border-slate-600 shadow-md uppercase text-xs font-bold tracking-wider"
          >
            {action}
          </button>
        ))}
      </div>
    </div>
  );
};

export default DecisionTree;
