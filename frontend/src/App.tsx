import { useCallback, useEffect, useRef, useState } from 'react';
import { Activity, ArrowDownToLine, ArrowRight, Check, CheckCircle2, ChevronRight, Clock3, Code2, FileText, GitBranch, History, Link2, Play, RotateCcw, ShieldCheck, Square, Terminal, Workflow, X } from 'lucide-react';
import { api, session } from './api';
import type { Metrics, Run, RunEvent, RunSummary, RuntimeConfig, Settings } from './types';
import { titles, WorkflowGraph } from './WorkflowGraph';
import { UrlShortener } from './UrlShortener';

const defaults: RuntimeConfig = { provider: 'codex', model: '', limits: { max_model_calls: 24, active_minutes: 30, call_timeout_seconds: 240, max_repair_cycles: 2 } };
const terminal = new Set(['succeeded', 'failed', 'stopped']);
const pretty = (value: string) => value.replaceAll('_', ' ');
const duration = (seconds?: number | null) => seconds == null ? 'Not available' : seconds < 60 ? `${seconds.toFixed(1)}s` : `${Math.floor(seconds / 60)}m ${Math.round(seconds % 60)}s`;

function Status({ value }: { value: string }) { return <span className={`status ${value}`}><span />{pretty(value)}</span>; }

export default function App() {
  const [tab, setTab] = useState<'workbench' | 'shortener' | 'history'>('workbench');
  const [settings, setSettings] = useState<Settings | null>(null);
  const [history, setHistory] = useState<RunSummary[]>([]);
  const [metrics, setMetrics] = useState<Metrics | null>(null);
  const [scenario, setScenario] = useState('greenfield');
  const [requirement, setRequirement] = useState('');
  const [config, setConfig] = useState(defaults);
  const [apiKey, setApiKey] = useState('');
  const [fault, setFault] = useState(false);
  const [runId, setRunId] = useState<string | null>(null);
  const [run, setRun] = useState<Run | null>(null);
  const [events, setEvents] = useState<RunEvent[]>([]);
  const [selectedNode, setSelectedNode] = useState('requirements');
  const [inspection, setInspection] = useState<'output' | 'diff' | 'checks'>('output');
  const [error, setError] = useState('');
  const [busy, setBusy] = useState(false);
  const [answers, setAnswers] = useState('Accept the local single-instance scope: 20 URL creations per minute per client, configurable, with 429 and Retry-After; redirects remain unlimited.');
  const [revisionText, setRevisionText] = useState('');
  const [connected, setConnected] = useState(false);
  const cursor = useRef(0);

  const refreshHistory = useCallback(async () => {
    const [nextHistory, nextMetrics] = await Promise.all([api<RunSummary[]>('/engineering/runs'), api<Metrics>('/engineering/metrics')]);
    setHistory(nextHistory); setMetrics(nextMetrics);
  }, []);

  useEffect(() => {
    let cancelled = false;
    (async () => {
      try {
        await session();
        const [nextSettings, nextHistory, nextMetrics] = await Promise.all([api<Settings>('/engineering/config'), api<RunSummary[]>('/engineering/runs'), api<Metrics>('/engineering/metrics')]);
        if (cancelled) return;
        setSettings(nextSettings); setRequirement(nextSettings.scenarios.greenfield.requirement); setHistory(nextHistory); setMetrics(nextMetrics);
        if (nextHistory.length) setRunId(nextHistory.find(r => !terminal.has(r.status))?.id || nextHistory[0].id);
      } catch (err) { if (!cancelled) setError(err instanceof Error ? err.message : 'Could not connect'); }
    })();
    return () => { cancelled = true; };
  }, []);

  useEffect(() => {
    if (!runId) return;
    const controller = new AbortController();
    let timer: ReturnType<typeof setTimeout> | undefined;
    cursor.current = 0; setEvents([]); setConnected(false); setRun(null);
    const refresh = () => api<Run>(`/engineering/runs/${runId}`, undefined, controller.signal).then(setRun).catch(err => { if (!controller.signal.aborted) setError(err.message); });
    refresh();
    const source = new EventSource(`/engineering/runs/${runId}/events`);
    source.onopen = () => setConnected(true);
    source.onerror = () => { setConnected(false); session().catch(() => {}); };
    source.onmessage = message => {
      const event: RunEvent = JSON.parse(message.data);
      if (event.seq <= cursor.current) return;
      cursor.current = event.seq;
      setEvents(previous => [...previous.slice(-79), event]);
      if (timer) clearTimeout(timer);
      timer = setTimeout(() => { refresh(); refreshHistory().catch(err => setError(err.message)); }, 250);
    };
    return () => { controller.abort(); source.close(); if (timer) clearTimeout(timer); };
  }, [runId, refreshHistory]);

  async function action(path: string, body: unknown) {
    setBusy(true); setError('');
    try { await api(path, body); if (runId) setRun(await api(`/engineering/runs/${runId}`)); await refreshHistory(); }
    catch (err) { setError(err instanceof Error ? err.message : 'Action failed'); }
    finally { setBusy(false); }
  }

  async function execute(event: React.FormEvent) {
    event.preventDefault(); setBusy(true); setError('');
    try {
      const next = await api<Run>('/engineering/runs', { scenario, requirement, config, inject_fault: fault, ...(apiKey ? { api_key: apiKey } : {}) });
      setRunId(next.id); setSelectedNode('requirements'); setTab('workbench'); await refreshHistory();
    } catch (err) { setError(err instanceof Error ? err.message : 'Could not start run'); }
    finally { setApiKey(''); setBusy(false); }
  }

  function chooseScenario(value: string) { setScenario(value); setRequirement(settings?.scenarios[value]?.requirement || ''); }
  const active = history.some(item => !terminal.has(item.status));
  const pending = run?.pending;
  const nodeArtifact = run?.artifacts[selectedNode];
  const tests = run?.artifacts.tests;

  return <div className="app-shell">
    <aside className="sidebar"><a className="brand" href="/" aria-label="Engineering Workbench home"><span><GitBranch size={21} /></span><div>URL Shortner<small>ENGINEERING WORKBENCH</small></div></a>
      <div className="nav-label">WORKSPACE</div><nav aria-label="Main navigation">
        <button className={tab === 'workbench' ? 'active' : ''} onClick={() => setTab('workbench')}><Workflow size={18} />Agent Workbench<ChevronRight size={14} /></button>
        <button className={tab === 'shortener' ? 'active' : ''} onClick={() => setTab('shortener')}><Link2 size={18} />URL Shortener</button>
        <button className={tab === 'history' ? 'active' : ''} onClick={() => setTab('history')}><History size={18} />Run History<span className="count">{history.length}</span></button>
      </nav>
      <div className="sidebar-note"><ShieldCheck size={19} /><strong>Controlled autonomy</strong><p>Isolated changes. Executed tests. Explicit approvals.</p><span className="local-dot" />Local environment</div>
      <div className="sidebar-bottom"><Terminal size={16} /><div>ChatGPT login by default<small>API billing is opt-in</small></div></div>
    </aside>
    <main><header className="topbar"><span>Workspace <ChevronRight size={14} /><strong>{tab === 'workbench' ? 'Agent Workbench' : tab === 'shortener' ? 'URL Shortener' : 'Run History'}</strong></span><div><span className="local-badge"><span />LOCAL</span><span className="avatar">EW</span></div></header>
      <div className="main-content">
        {error ? <div className="notice error" role="alert">{error}<button aria-label="Dismiss error" onClick={() => setError('')}><X size={16} /></button></div> : null}
        {tab === 'shortener' ? <UrlShortener /> : tab === 'history' ? <>
          <div className="page-heading"><span className="eyebrow">DECISIONS, CHANGES & EVIDENCE</span><h1>Run history</h1><p>Inspect saved executions, including stopped and unsuccessful runs.</p></div>
          <div className="metric-strip"><Metric label="Runs" value={String(metrics?.runs ?? 0)} /><Metric label="Success rate" value={metrics?.success_rate == null ? 'Not available' : `${Math.round(metrics.success_rate * 100)}%`} /><Metric label="Retries / rollbacks" value={`${metrics?.retries ?? 0} / ${metrics?.rollbacks ?? 0}`} /><Metric label="Mean recovery" value={duration(metrics?.mean_recovery_seconds)} /></div>
          <section className="card history-card"><div className="section-heading"><h2>All executions</h2><span className="muted">Persisted locally</span></div>{history.length ? <div className="table-scroll"><table><thead><tr><th>Scenario & requirement</th><th>Status</th><th>Revision</th><th>Active time</th><th>Calls</th><th>Created</th></tr></thead><tbody>{history.map(item => <tr key={item.id}><td><button className="run-link" onClick={() => { setRunId(item.id); setTab('workbench'); }}>{pretty(item.scenario)}<ArrowRight size={14} /></button><p>{item.requirement.slice(0,90)}{item.requirement.length > 90 ? '…' : ''}</p></td><td><Status value={item.status} /></td><td>r{item.revision}</td><td>{duration(item.active_seconds)}</td><td>{item.model_calls}</td><td>{new Date(item.created_at).toLocaleString()}</td></tr>)}</tbody></table></div> : <Empty title="No executions yet" text="Start an engineering requirement in the Workbench. Its evidence will appear here." />}</section>
          <p className="footnote">Success rate includes all terminal runs, including operator stops and rejected approvals. Recovery time is measured only for runs that recovered from failed validation.</p>
        </> : <>
          <div className="page-heading heading-row"><div><span className="eyebrow">REQUIREMENT → REVIEWABLE ENGINEERING OUTCOME</span><h1>Agent Workbench</h1><p>Build and evolve the URL service, with every decision in view.</p></div><span className="quiet-tag"><ShieldCheck size={15} />Governed execution</span></div>
          <section className="card requirement-card"><div className="section-heading"><h2><span className="section-number">01</span>Engineering requirement</h2><span className="muted">Scope: Java URL service</span></div>
            <form onSubmit={execute}><div className="scenario-selector" role="group" aria-label="Scenario">{['greenfield', 'brownfield', 'ambiguous'].map(value => <button key={value} type="button" className={scenario === value ? 'selected' : ''} aria-pressed={scenario === value} onClick={() => chooseScenario(value)}>{pretty(value)}<small>{settings?.scenarios[value]?.title}</small></button>)}</div>
              <label className="sr-only" htmlFor="requirement">Engineering requirement</label><textarea id="requirement" required maxLength={12000} value={requirement} onChange={e => setRequirement(e.target.value)} placeholder="Describe the change and its acceptance criteria…" />
              <div className="configuration-row"><label>Model connection<select value={config.provider} onChange={e => { setConfig({ ...config, provider: e.target.value as RuntimeConfig['provider'] }); setApiKey(''); }}>{settings?.providers.map(provider => <option key={provider.id} value={provider.id} disabled={!provider.enabled}>{provider.label}{!provider.enabled ? ' · disabled' : ''}</option>)}</select></label><label>Model <span className="muted">optional for Codex</span><input value={config.model} maxLength={100} placeholder="Use CLI default" onChange={e => setConfig({ ...config, model: e.target.value })} autoComplete="off" /></label><button className="primary execute" disabled={busy || active || !settings}><Play size={15} />{busy ? 'Starting…' : 'Execute requirement'}</button></div>
              {config.provider !== 'codex' ? <><div className="notice warning">This provider bills API usage to the key owner. Keys are held in server memory for this run and cleared at completion.</div><label>Provider API key<input type="password" value={apiKey} onChange={e => setApiKey(e.target.value)} autoComplete="off" required /></label></> : null}
              <div className="config-footer"><span><LockIcon />No automatic paid fallback</span><details><summary>Execution limits & fault exercise</summary><div className="limits-grid">{([['max_model_calls', 'Maximum model calls', 1, 24], ['active_minutes', 'Active minutes', 1, 30], ['call_timeout_seconds', 'Call timeout (seconds)', 30, 300], ['max_repair_cycles', 'Repair cycles', 0, 2]] as const).map(([key, title, min, max]) => <label key={key}>{title}<input type="number" min={min} max={max} value={config.limits[key]} onChange={e => setConfig({ ...config, limits: { ...config.limits, [key]: Number(e.target.value) } })} /></label>)}</div><label className="checkbox"><input type="checkbox" checked={fault} onChange={e => setFault(e.target.checked)} />Inject a labelled redirect source fault to exercise repair</label></details></div>
              {active ? <p className="footnote">One run is already active or waiting. Finish or stop it before starting another.</p> : null}
            </form>
          </section>
          <div className="run-heading"><div><h2>Execution workspace</h2><span className="muted">{run ? `${pretty(run.scenario)} · ${run.id.slice(0,12)} · revision ${run.revision}` : 'Start a run to populate the graph and evidence'}</span></div><div>{run ? <><Status value={run.status} />{!terminal.has(run.status) ? <button className="secondary danger" disabled={busy} onClick={() => action(`/engineering/runs/${run.id}/stop`, {})}><Square size={13} />Stop safely</button> : null}</> : <span className="quiet-tag">No run selected</span>}</div></div>
          {run?.stop_reason ? <div className="notice warning"><ShieldCheck size={17} />{run.stop_reason}</div> : null}
          {run?.status === 'stopped' && run.platform_failure ? <button className="secondary" disabled={busy} onClick={() => action(`/engineering/runs/${run.id}/retry`, { ...(apiKey ? { api_key: apiKey } : {}) })}><RotateCcw size={14} />Retry after infrastructure repair · retain budgets</button> : null}
          {pending?.kind === 'clarification' ? <section className="card checkpoint"><div className="checkpoint-icon"><FileText size={21} /></div><div><span className="eyebrow">HUMAN CHECKPOINT</span><h3>Resolve the requirement</h3>{pending.questions?.map(question => <p key={question.id}>{question.text}</p>)}<label htmlFor="clarification">Your acceptance criteria</label><textarea id="clarification" value={answers} onChange={e => setAnswers(e.target.value)} /><button className="primary" disabled={busy} onClick={() => action(`/engineering/runs/${run!.id}/clarification`, { expected_revision: run!.revision, answers })}>Submit clarification<ArrowRight size={15} /></button></div></section> : null}
          {pending && pending.kind !== 'clarification' ? <section className="card checkpoint"><div className="checkpoint-icon"><ShieldCheck size={23} /></div><div><span className="eyebrow">HUMAN CHECKPOINT · REVISION {run?.revision}</span><h3>{pending.kind === 'promotion' ? 'Review before local release' : 'Review the proposed change'}</h3><p>{pending.reason}</p><p className="footnote">Approval is bound to the displayed source and artifact revision. A requirement change invalidates it.</p><div className="button-row"><button className="primary" disabled={busy} onClick={() => action(`/engineering/runs/${run!.id}/approval`, { expected_revision: run!.revision, approval_id: pending.approval_id, artifact_hash: pending.artifact_hash, approved: true, reason: 'Approved through the local Workbench UI' })}><Check size={15} />Approve & continue</button><button className="secondary danger" disabled={busy} onClick={() => action(`/engineering/runs/${run!.id}/approval`, { expected_revision: run!.revision, approval_id: pending.approval_id, artifact_hash: pending.artifact_hash, approved: false, reason: 'Rejected through the local Workbench UI' })}><X size={15} />Reject & stop</button></div></div></section> : null}
          {run && ['interrupted','awaiting_approval','awaiting_clarification'].includes(run.status) ? <details className="card revise-card"><summary><RotateCcw size={15} />Change requirement or resume configuration</summary><label htmlFor="revised-requirement">New requirement · creates revision {run.revision + 1}</label><textarea id="revised-requirement" value={revisionText} onChange={e => setRevisionText(e.target.value)} placeholder={run.requirement} /><div className="button-row"><button className="secondary" disabled={busy || revisionText.length < 10} onClick={() => action(`/engineering/runs/${run.id}/requirements`, { expected_revision: run.revision, requirement: revisionText })}>Invalidate downstream outputs & re-plan</button><button className="secondary" disabled={busy} onClick={() => { action(`/engineering/runs/${run.id}/resume`, { config, ...(apiKey ? { api_key: apiKey } : {}) }); setApiKey(''); }}>Apply configuration{run.status === 'interrupted' ? ' & resume' : ''}</button></div></details> : null}
          <div className="execution-grid"><section className="card graph-card"><div className="section-heading"><h2><Workflow size={17} />Dependency graph</h2><span className={`stream-state ${connected ? 'connected' : ''}`}><span />{run ? connected ? 'Live events' : 'Reconnecting' : 'Ready'}</span></div><div className="graph-scroll"><WorkflowGraph run={run} selected={selectedNode} onSelect={setSelectedNode} /></div><div className="graph-legend"><span><i className="passed" />Passed</span><span><i className="running" />Running</span><span><i className="waiting" />Approval</span><span><i className="pending" />Pending</span></div></section>
            <section className="card inspector"><div className="section-heading"><h2><Code2 size={17} />{titles[selectedNode]}</h2>{nodeArtifact ? <a className="icon-button" aria-label={`Download ${titles[selectedNode]} artifact`} href={`/engineering/runs/${runId}/artifacts/${selectedNode}`}><ArrowDownToLine size={16} /></a> : null}</div><div className="inspector-tabs" role="group" aria-label="Evidence view">{(['output','diff','checks'] as const).map(value => <button className={inspection === value ? 'selected' : ''} key={value} onClick={() => setInspection(value)}>{value === 'output' ? 'Agent output' : value === 'diff' ? 'Source diff' : 'Test evidence'}</button>)}</div>
              <div className="inspector-content">{inspection === 'output' ? nodeArtifact ? <><span className="eyebrow">{nodeArtifact.source_sha ? `SOURCE ${nodeArtifact.source_sha.slice(0,10)}` : 'RECORDED ARTIFACT'}</span>{nodeArtifact.output?.summary ? <p className="artifact-summary">{nodeArtifact.output.summary}</p> : null}<pre>{JSON.stringify(nodeArtifact, null, 2)}</pre></> : <Empty title="No output yet" text="Select a graph stage to inspect its recorded decisions, inputs and output." /> : inspection === 'diff' ? run?.diff ? <pre className="source-diff">{run.diff}</pre> : <Empty title="No source changes yet" text="The trusted repository tools will record a diff when implementation begins." /> : tests ? <><div className="validation-heading"><Status value={tests.passed ? 'succeeded' : 'failed'} /><span>{tests.unit?.tests ?? 0} JUnit tests · {duration(tests.duration_seconds)}</span></div>{tests.acceptance?.cases?.map((test: { name: string; passed: boolean; details: string }) => <div className={`test-case ${test.passed ? 'passed' : 'failed'}`} key={test.name}>{test.passed ? <CheckCircle2 size={15} /> : <X size={15} />}<div>{test.name}{!test.passed ? <small>{test.details}</small> : null}</div></div>)}<details><summary>Build log & unit suites</summary><pre>{JSON.stringify({ unit: tests.unit, exit_code: tests.exit_code }, null, 2)}{'\n'}{tests.log}</pre></details></> : <Empty title="Validation hasn’t run" text="JUnit results and independent HTTP checks appear after real execution." />}</div>
            </section></div>
          <div className="metric-strip run-metrics"><Metric label="Model calls" value={`${run?.model_calls ?? 0} / ${run?.config.limits.max_model_calls ?? 24}`} /><Metric label="Repairs / retries" value={`${run?.repair_cycles ?? 0} / ${run?.retries ?? 0}`} /><Metric label="Active execution" value={duration(run?.active_seconds)} /><Metric label="Audit chain" value={run ? run.audit_chain_valid ? 'Verified' : 'Check failed' : 'No evidence yet'} /></div>
          <section className="card events-card"><div className="section-heading"><h2><Activity size={17} />Execution journal</h2><span className="muted">{events.length ? `Latest ${events.length} events` : 'No events yet'}</span></div><div className="event-list">{events.length ? [...events].reverse().map(event => <div className="event" key={event.seq}><span className="event-seq">{String(event.seq).padStart(3,'0')}</span><span className="event-time">{new Date(event.at).toLocaleTimeString()}</span><div><strong>{pretty(event.kind)}</strong><p>{Object.entries(event.data).filter(([key]) => !['questions','cases','config','requirement','invalidated'].includes(key)).map(([key,value]) => `${pretty(key)}: ${typeof value === 'object' ? JSON.stringify(value) : String(value)}`).join(' · ')}</p></div></div>) : <p className="muted">Stage transitions, retries, decisions and validation receipts will appear here.</p>}</div></section>
          <p className="footnote">The frontend observes and controls the Python workflow. Model outputs are proposals; isolated execution and protected checks establish their validation status.</p>
        </>}
      </div>
    </main>
  </div>;
}

function Metric({ label, value }: { label: string; value: string }) { return <div className="metric"><span>{label}</span><strong>{value}</strong></div>; }
function Empty({ title, text }: { title: string; text: string }) { return <div className="empty"><FileText size={24} /><strong>{title}</strong><p>{text}</p></div>; }
function LockIcon() { return <ShieldCheck size={13} />; }
