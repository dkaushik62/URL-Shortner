import { Check, Circle, GitBranch, LoaderCircle, LockKeyhole, MessageSquare, ShieldCheck } from 'lucide-react';
import type { Run } from './types';

export const titles: Record<string, string> = { requirements: 'Understand', clarification: 'Clarify', plan: 'Plan', architecture: 'Architecture', test_design: 'Test design', change_approval: 'Change approval', implementation: 'Implement', tests: 'Validate', documentation: 'Document', review: 'Review', release_approval: 'Release approval', github_delivery: 'Create GitHub PR', local_release_approval: 'Local demo choice', promotion: 'Promote locally', summary: 'Engineering summary' };
const rows = [['requirements'], ['clarification'], ['plan'], ['architecture', 'test_design'], ['change_approval'], ['implementation'], ['tests', 'documentation'], ['review'], ['release_approval'], ['github_delivery'], ['local_release_approval'], ['promotion'], ['summary']];

export function WorkflowGraph({ run, mode, selected, onSelect, edges }: { run: Run | null; mode: string; selected: string; onSelect: (node: string) => void; edges: [string, string][] }) {
  const visibleRows = rows.filter(row => mode === 'enhancement' || !['github_delivery', 'local_release_approval'].includes(row[0]));
  const visibleEdges = edges.filter(([source, target]) => mode === 'enhancement' ? !(source === 'release_approval' && target === 'promotion') : !['github_delivery','local_release_approval'].includes(source) && !['github_delivery','local_release_approval'].includes(target));
  return <div className="workflow" aria-label="Engineering dependency graph">
    {visibleRows.map((row, index) => <div className="graph-row-wrap" key={row.join('-')}>
      {index > 0 ? <div className="connector"><span />{row.length > 1 ? <small><GitBranch size={12} /> parallel branches</small> : null}</div> : null}
      <div className={`graph-row ${row.length > 1 ? 'parallel' : ''}`}>
        {row.map(node => {
          let status = run?.nodes[node]?.status || 'pending';
          if (run?.pending?.kind === 'clarification' && node === 'clarification') status = 'waiting';
          if (run?.pending?.kind === 'change' && node === 'change_approval') status = 'waiting';
          if (['promotion','github'].includes(run?.pending?.kind ?? '') && node === 'release_approval') status = 'waiting';
          if (run?.pending?.kind === 'optional_promotion' && node === 'local_release_approval') status = 'waiting';
          const Icon = status === 'passed' ? Check : status === 'running' ? LoaderCircle : status === 'waiting' ? LockKeyhole : node.includes('approval') ? ShieldCheck : node === 'clarification' ? MessageSquare : Circle;
          return <button type="button" key={node} title={`Incoming dependencies: ${visibleEdges.filter(([, target]) => target === node).map(([source]) => titles[source]).join(', ') || 'Start'}${node === 'clarification' ? ' (conditional)' : ''}`} onClick={() => onSelect(node)} className={`graph-node ${status} ${selected === node ? 'selected' : ''}`} aria-pressed={selected === node}>
            <span className="node-icon"><Icon size={16} /></span><span>{node === 'release_approval' && mode === 'enhancement' ? 'PR approval' : titles[node]}</span><small>{status}</small>
          </button>;
        })}
      </div>
    </div>)}
    <div className="repair-loop"><GitBranch size={14} /> Validation or review failure returns to Implement · maximum 2 repairs</div>
  </div>;
}
