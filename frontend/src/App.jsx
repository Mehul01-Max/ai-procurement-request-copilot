import React, { useEffect, useState } from 'react';

const REC_LABEL = {
  approve_to_proceed: 'Approve to proceed (with required approvals)',
  use_existing_tool: 'Use existing tool',
  request_more_info: 'Request more info',
  escalate_to_human: 'Escalate to human',
  reject: 'Reject',
};

function Pill({ children, tone }) {
  return <span className={'pill ' + (tone || '')}>{children}</span>;
}

export default function App() {
  const [samples, setSamples] = useState([]);
  const [requestId, setRequestId] = useState('');
  const [arch, setArch] = useState('single');
  const [custom, setCustom] = useState('');
  const [useCustom, setUseCustom] = useState(false);
  const [result, setResult] = useState(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');
  const [review, setReview] = useState({});

  useEffect(() => {
    fetch('/api/requests').then((r) => r.json()).then((d) => {
      setSamples(d.requests || []);
      if (d.requests && d.requests.length) setRequestId(d.requests[0].request_id);
    }).catch(() => setError('Backend not reachable. Start it with: python run_local.py'));
  }, []);

  const selected = samples.find((r) => r.request_id === requestId);

  async function analyze() {
    setLoading(true); setError(''); setResult(null);
    try {
      let body;
      if (useCustom) {
        let parsed;
        try { parsed = JSON.parse(custom); }
        catch (e) { throw new Error('Custom request is not valid JSON.'); }
        body = { architecture: arch, custom_request: parsed, request_id: parsed.request_id || 'REQ-CUSTOM' };
      } else {
        body = { architecture: arch, request_id: requestId };
      }
      const res = await fetch('/api/analyze', {
        method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(body),
      });
      const data = await res.json();
      if (!res.ok) throw new Error(data.detail || 'Analysis failed');
      setResult(data);
    } catch (e) { setError(String(e.message || e)); }
    finally { setLoading(false); }
  }

  function humanDecision(dec) {
    if (!result) return;
    const next = {}; next[result.request_id + arch] = dec;
    setReview(Object.assign({}, review, next));
  }

  const tools = (result && result.tool_results) || {};
  const escalated = result && (result.recommendation === 'escalate_to_human' || result.recommendation === 'request_more_info');

  return (
    <React.Fragment>
      <header>
        <h1>AI Procurement Request Copilot</h1>
        <p>Advisory only — a human owns every purchase decision. AI recommends; CODE checks thresholds; HUMAN approves.</p>
      </header>
      <div className="layout">
        <section className="card">
          <h2>1 - Request details</h2>
          <label>Architecture</label>
          <div className="toggle">
            <button className={arch === 'single' ? 'active' : ''} onClick={() => setArch('single')}>A - Single agent</button>
            <button className={arch === 'staged' ? 'active' : ''} onClick={() => setArch('staged')}>B - Staged (2-agent)</button>
          </div>
          <label>Sample request</label>
          <select value={requestId} onChange={(e) => setRequestId(e.target.value)} disabled={useCustom}>
            {samples.map((r) => <option key={r.request_id} value={r.request_id}>{r.request_id} - {r.product_name}</option>)}
          </select>
          <label><input type="checkbox" style={{ width: 'auto' }} checked={useCustom} onChange={(e) => setUseCustom(e.target.checked)} /> Type a custom request (JSON)</label>
          {useCustom ? (
            <textarea value={custom} onChange={(e) => setCustom(e.target.value)} placeholder='{"request_id":"REQ-CUSTOM","requester_id":"E004","vendor_name":"SignFlow","annual_cost_usd":500}' />
          ) : selected && (
            <dl className="kv">
              <dt>Product</dt><dd>{selected.product_name}</dd>
              <dt>Vendor</dt><dd>{selected.vendor_name}</dd>
              <dt>Cost</dt><dd>{selected.annual_cost_usd == null ? '- (missing)' : selected.annual_cost_usd}</dd>
              <dt>Users</dt><dd>{selected.user_count == null ? '- (missing)' : selected.user_count}</dd>
              <dt>Data</dt><dd>{selected.data_access_level}</dd>
              <dt>Purpose</dt><dd>{selected.business_justification}</dd>
            </dl>
          )}
          <button onClick={analyze} disabled={loading}>{loading ? 'Analyzing...' : 'Run analysis'}</button>
          {error && <p className="error">{error}</p>}
        </section>
        <section className="card">
          <h2>2 - Evidence panel</h2>
          {!result && <p className="meta">Run an analysis to see every tool call with its source IDs.</p>}
          {result && Object.keys(tools).map((name) => (
            <div key={name}>
              <h4 style={{ margin: '10px 0 4px' }}>{name}</h4>
              <pre className="tool">{JSON.stringify(tools[name], null, 1).slice(0, 2500)}</pre>
            </div>
          ))}
          {result && result.analyst_pack && (
            <div><h4>Analyst evidence pack (Agent B, step 1)</h4>
              <pre className="tool">{JSON.stringify(result.analyst_pack, null, 1).slice(0, 2000)}</pre></div>
          )}
        </section>
        <section className="card">
          <h2>3 - Recommendation and action</h2>
          {!result && <p className="meta">The structured decision appears here.</p>}
          {result && (
            <div>
              <p><strong>{REC_LABEL[result.recommendation] || result.recommendation}</strong></p>
              <p><Pill tone={escalated ? 'warn' : 'good'}>{escalated ? 'Sent to human reviewer' : 'Ready for approval chain'}</Pill>
                <Pill>latency {result.latency_ms} ms</Pill>
                <Pill>LLM {(result.telemetry && result.telemetry.llm_calls) || 0}</Pill>
                <Pill>tools {(result.telemetry && result.telemetry.tool_calls) || 0}</Pill></p>
              <label>Approvals required</label>
              <div>{(result.required_approvals || []).map((a) => <Pill key={a}>{a}</Pill>)}</div>
              <label>Risk flags</label>
              <div>{(result.risk_flags || []).map((f) => <Pill key={f} tone="bad">{f}</Pill>)}</div>
              <label>Missing information</label>
              <div>{(result.missing_information || []).length ? result.missing_information.map((m) => <Pill key={m} tone="warn">{m}</Pill>) : <span className="meta">none</span>}</div>
              <label>Evidence</label>
              <ul>{(result.evidence || []).map((e, i) => <li key={i} style={{ fontSize: 13 }}><strong>{e.source}</strong> [{e.reference}]: {e.finding}</li>)}</ul>
              <label>Next step</label>
              <p style={{ fontSize: 14 }}>{result.next_step}</p>
              {escalated && (
                <div className="escalate">
                  <strong>Handoff: human review queue</strong>
                  <p className="meta">This case needs a person. Record the reviewer decision:</p>
                  <div className="review-row">
                    <button className="approve" onClick={() => humanDecision('approved')}>Approve</button>
                    <button className="reject" onClick={() => humanDecision('rejected')}>Reject</button>
                    <button className="info" onClick={() => humanDecision('info-requested')}>Request info</button>
                  </div>
                  {review[result.request_id + arch] && <p><Pill tone="good">reviewer: {review[result.request_id + arch]}</Pill></p>}
                </div>
              )}
            </div>
          )}
        </section>
      </div>
    </React.Fragment>
  );
}
