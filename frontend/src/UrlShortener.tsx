import { useState } from 'react';
import { ArrowUpRight, Check, Copy, Link2, RefreshCw } from 'lucide-react';
import { api } from './api';

export function UrlShortener() {
  const [url, setUrl] = useState('');
  const [expiry, setExpiry] = useState('');
  const [result, setResult] = useState<{ code: string; shortUrl: string } | null>(null);
  const [analytics, setAnalytics] = useState<Record<string, unknown> | null>(null);
  const [error, setError] = useState('');
  const [busy, setBusy] = useState(false);
  const [copied, setCopied] = useState(false);
  const loadAnalytics = async (code: string) => setAnalytics(await api(`/api/urls/${encodeURIComponent(code)}/analytics`));
  async function create(event: React.FormEvent) {
    event.preventDefault(); setBusy(true); setError(''); setCopied(false); setResult(null); setAnalytics(null);
    try {
      const body = { url, ...(expiry ? { expiresAt: new Date(expiry).toISOString() } : {}) };
      const created = await api<{ code: string; shortUrl: string }>('/api/urls', body);
      setResult(created); await loadAnalytics(created.code);
    } catch (err) { setError(err instanceof Error ? err.message : 'Could not create link'); }
    finally { setBusy(false); }
  }
  return <div className="shortener-page">
    <div className="page-heading"><span className="eyebrow">THE SOFTWARE BEING BUILT</span><h1>Long link. Short journey.</h1><p>Create a link, follow it, and inspect the service’s actual click analytics.</p></div>
    <section className="card shorten-card"><div className="feature-icon"><Link2 size={25} /></div><h2>Shorten a URL</h2><p>Requests go directly to the Java service. Creating a link does not start an agent run.</p>
      <form onSubmit={create}><label htmlFor="long-url">Destination URL</label><input id="long-url" type="url" required maxLength={2048} placeholder="https://example.com/a-long-link" value={url} onChange={e => setUrl(e.target.value)} />
        <label htmlFor="expiry">Expiration <span className="muted">optional · available after the expiry enhancement</span></label><input id="expiry" type="datetime-local" value={expiry} onChange={e => setExpiry(e.target.value)} />
        <button className="primary" disabled={busy}>{busy ? 'Creating…' : 'Shorten URL'}<ArrowUpRight size={16} /></button>
      </form>
      {error ? <div className="notice error" role="alert">{error}</div> : null}
      {result ? <div className="link-result"><span className="eyebrow">YOUR SHORT LINK</span><div className="result-row"><a href={result.shortUrl} target="_blank" rel="noopener noreferrer">{result.shortUrl}</a><button className="icon-button" aria-label="Copy short link" onClick={async () => { try { await navigator.clipboard.writeText(result.shortUrl); setCopied(true); } catch { setError('Copy is unavailable; select the link text to copy it.'); } }}>{copied ? <Check size={17} /> : <Copy size={17} />}</button></div></div> : null}
    </section>
    {result && analytics ? <section className="card analytics-card"><div className="section-heading"><h2>Link analytics</h2><button className="secondary" onClick={() => loadAnalytics(result.code).catch(err => setError(err.message))}><RefreshCw size={14} />Refresh</button></div><div className="analytics-grid"><div><span>Successful redirects</span><strong>{String(analytics.clickCount ?? 'Unavailable')}</strong></div><div><span>Created</span><strong className="date-value">{analytics.createdAt ? new Date(String(analytics.createdAt)).toLocaleString() : 'Unavailable'}</strong></div><div><span>Last accessed</span><strong className="date-value">{analytics.lastAccessedAt ? new Date(String(analytics.lastAccessedAt)).toLocaleString() : 'No visits yet'}</strong></div></div></section> : null}
  </div>;
}
