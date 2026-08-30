import { useState, useEffect } from 'react'
import { PieChart, Pie, Cell, BarChart, Bar, XAxis, YAxis, Tooltip, ResponsiveContainer } from 'recharts'
import { supabase } from './supabaseClient'
import './App.css'

const ACTION_LABELS = {
  auto_retry: 'Auto-retried',
  wait_and_reassure: 'Waiting (no retry)',
  notify_customer_action_required: 'Customer notified',
  capture_and_notify: 'Captured',
  no_action: 'No action',
  escalate_to_merchant: 'Escalated',
}

const FILTERS = [
  { key: 'all', label: 'All' },
  { key: 'success', label: 'Success' },
  { key: 'late_auth', label: 'Late-Auth' },
  { key: 'ambiguous', label: 'Ambiguous' },
  { key: 'no_retry', label: 'No-Retry' },
  { key: 'escalate', label: 'Escalated' },
  { key: 'cancelled', label: 'Cancelled' },
  { key: 'safe_retry', label: 'Safe-Retry' },
]

const CLASSIFICATION_COLORS = {
  success: '#3f7d5c',
  late_auth: '#b8863b',
  ambiguous: '#6b7a3f',
  no_retry: '#c1553c',
  cancelled: '#a39d83',
  escalate: '#8b3a3a',
  safe_retry: '#3f7d5c',
}

function isRealPayment(paymentId) {
  return !paymentId.startsWith('pay_sim_')
}

function formatRupees(paise) {
  return `₹${(paise / 100).toLocaleString('en-IN', { minimumFractionDigits: 2 })}`
}

function computeMetrics(events) {
  let atRisk = 0
  let recovered = 0
  let escalatedCount = 0
  let correctlyNoAction = 0
  let totalAmount = 0

  for (const e of events) {
    totalAmount += e.amount
    if (e.classification === 'success') continue
    atRisk += e.amount

    if (e.action_taken === 'auto_retry') recovered += e.amount
    if (e.action_taken === 'escalate_to_merchant') escalatedCount += 1
    if (e.action_taken === 'wait_and_reassure' || e.action_taken === 'no_action') {
      correctlyNoAction += 1
    }
  }

  const unresolved = atRisk - recovered
  return { atRisk, recovered, unresolved, escalatedCount, correctlyNoAction, totalAmount }
}

function computeChartData(events) {
  const classificationCounts = {}
  const statusCounts = {}

  for (const e of events) {
    const c = e.classification || 'unclassified'
    classificationCounts[c] = (classificationCounts[c] || 0) + 1
    statusCounts[e.status] = (statusCounts[e.status] || 0) + 1
  }

  const pieData = Object.entries(classificationCounts).map(([name, value]) => ({
    name,
    value,
    color: CLASSIFICATION_COLORS[name] || '#8a93a6',
  }))

  const barData = Object.entries(statusCounts).map(([name, count]) => ({ name, count }))

  return { pieData, barData }
}

export default function App() {
  const [events, setEvents] = useState([])
  const [loading, setLoading] = useState(true)
  const [expandedId, setExpandedId] = useState(null)
  const [activeFilter, setActiveFilter] = useState('all')
  const [sortByAmount, setSortByAmount] = useState(null)

  async function fetchEvents() {
    const { data, error } = await supabase
      .from('payment_events')
      .select('*')
      .order('created_at', { ascending: false })

    if (error) {
      console.error('Error fetching events:', error)
      return
    }
    setEvents(data)
    setLoading(false)
  }

  useEffect(() => {
    fetchEvents()
    const interval = setInterval(fetchEvents, 8000)
    return () => clearInterval(interval)
  }, [])

  if (loading) return <div className="loading">Loading payment events…</div>

  const metrics = computeMetrics(events)
  const { pieData, barData } = computeChartData(events)
  const recoveredPct = metrics.totalAmount ? (metrics.recovered / metrics.totalAmount) * 100 : 0
  const unresolvedPct = metrics.totalAmount ? (metrics.unresolved / metrics.totalAmount) * 100 : 0
  const safePct = 100 - recoveredPct - unresolvedPct

  let displayedEvents = activeFilter === 'all'
    ? events
    : events.filter((e) => e.classification === activeFilter)

  if (sortByAmount) {
    displayedEvents = [...displayedEvents].sort((a, b) =>
      sortByAmount === 'asc' ? a.amount - b.amount : b.amount - a.amount
    )
  }

  function toggleAmountSort() {
    if (sortByAmount === null) setSortByAmount('desc')
    else if (sortByAmount === 'desc') setSortByAmount('asc')
    else setSortByAmount(null)
  }

  return (
    <div className="dashboard">
      <header>
        <h1>PayResQ</h1>
        <p className="subtitle">AI-powered payment recovery for Razorpay checkouts</p>
      </header>

      <section className="metrics">
        <div className="metric-card risk">
          <span className="label">At Risk</span>
          <span className="value">{formatRupees(metrics.atRisk)}</span>
        </div>
        <div className="metric-card recovered">
          <span className="label">Recovered</span>
          <span className="value">{formatRupees(metrics.recovered)}</span>
        </div>
        <div className="metric-card unresolved">
          <span className="label">Unresolved</span>
          <span className="value">{formatRupees(metrics.unresolved)}</span>
        </div>
        <div className="metric-card">
          <span className="label">Escalated</span>
          <span className="value">{metrics.escalatedCount}</span>
        </div>
        <div className="metric-card">
          <span className="label">Held Back</span>
          <span className="value">{metrics.correctlyNoAction}</span>
        </div>
      </section>

      <section className="charts-row">
        <div className="chart-card">
          <h3>Classification breakdown</h3>
          <div className="chart-body">
            <ResponsiveContainer width="100%" height={200}>
              <PieChart>
                <Pie data={pieData} dataKey="value" nameKey="name" innerRadius={55} outerRadius={80} paddingAngle={3}>
                  {pieData.map((entry, i) => (
                    <Cell key={i} fill={entry.color} stroke="none" />
                  ))}
                </Pie>
                <Tooltip contentStyle={{ background: '#fffefb', border: '1px solid #e6ddc6', borderRadius: 8, fontSize: 12, color: '#2f2a1f' }} />
              </PieChart>
            </ResponsiveContainer>
            <div className="chart-legend">
              {pieData.map((entry, i) => (
                <div key={i} className="chart-legend-item">
                  <span className="dot" style={{ background: entry.color }} />
                  {entry.name} ({entry.value})
                </div>
              ))}
            </div>
          </div>
        </div>

        <div className="chart-card">
          <h3>Payments by status</h3>
          <ResponsiveContainer width="100%" height={240}>
            <BarChart data={barData}>
              <XAxis dataKey="name" tick={{ fill: '#7a7357', fontSize: 12 }} axisLine={{ stroke: '#e6ddc6' }} tickLine={false} /><YAxis tick={{ fill: '#7a7357', fontSize: 12 }} axisLine={false} tickLine={false} />
              <Tooltip contentStyle={{ background: '#fffefb', border: '1px solid #e6ddc6', borderRadius: 8, fontSize: 12, color: '#2f2a1f' }} cursor={{ fill: 'rgba(75,83,32,0.06)' }} />
              <Bar dataKey="count" fill="#4b5320" radius={[6, 6, 0, 0]} />
            </BarChart>
          </ResponsiveContainer>
        </div>
      </section>

      <div className="recovery-bar-wrap">
        <div className="recovery-bar-label">
          <span>Batch composition</span>
          <span>{formatRupees(metrics.totalAmount)} total</span>
        </div>
        <div className="recovery-bar">
          <div className="segment safe" style={{ width: `${safePct}%` }} />
          <div className="segment recovered" style={{ width: `${recoveredPct}%` }} />
          <div className="segment unresolved" style={{ width: `${unresolvedPct}%` }} />
        </div>
        <div className="recovery-bar-legend">
          <span><span className="legend-dot safe" /> Never at risk</span>
          <span><span className="legend-dot recovered" /> Recovered</span>
          <span><span className="legend-dot unresolved" /> Unresolved</span>
        </div>
      </div>

      <div className="filter-bar">
        {FILTERS.map((f) => (
          <button
            key={f.key}
            className={`filter-pill ${activeFilter === f.key ? 'active' : ''}`}
            onClick={() => setActiveFilter(f.key)}
          >
            {f.label}
          </button>
        ))}
      </div>

      <section className="table-section">
        <table>
          <thead>
            <tr>
              <th>Payment ID</th>
              <th className="sortable" onClick={toggleAmountSort}>
                Amount {sortByAmount === 'desc' ? '↓' : sortByAmount === 'asc' ? '↑' : ''}
              </th>
              <th>Status</th>
              <th>Classification</th>
              <th>Action</th>
            </tr>
          </thead>
          <tbody>
            {displayedEvents.map((e) => (
              <>
                <tr
                  key={e.payment_id}
                  className="event-row"
                  onClick={() => setExpandedId(expandedId === e.payment_id ? null : e.payment_id)}
                >
                  <td>
                    {isRealPayment(e.payment_id) && <span className="real-badge">LIVE</span>}
                    {e.payment_id}
                  </td>
                  <td>{formatRupees(e.amount)}</td>
                  <td><span className={`status-badge ${e.status}`}>{e.status}</span></td>
                  <td>{e.classification || '—'}</td>
                  <td>{ACTION_LABELS[e.action_taken] || e.action_taken || '—'}</td>
                </tr>
                {expandedId === e.payment_id && (
                  <tr className="reasoning-row">
                    <td colSpan={5}>
                      <strong>Reasoning:</strong> {e.reasoning || 'No reasoning recorded (rules-based, no LLM call needed).'}
                      {e.error_description && <div className="error-desc"><strong>Error:</strong> {e.error_description}</div>}
                    </td>
                  </tr>
                )}
              </>
            ))}
          </tbody>
        </table>
        {displayedEvents.length === 0 && <div className="empty-state">No events match this filter.</div>}
      </section>
    </div>
  )
}