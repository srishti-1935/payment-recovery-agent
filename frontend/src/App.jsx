import { useState, useEffect } from 'react'
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

  for (const e of events) {
    if (e.classification === 'success') continue
    atRisk += e.amount

    if (e.action_taken === 'auto_retry') {
      recovered += e.amount
    }
    if (e.action_taken === 'escalate_to_merchant') escalatedCount += 1
    if (e.action_taken === 'wait_and_reassure' || e.action_taken === 'no_action') {
      correctlyNoAction += 1
    }
  }

  const unresolved = atRisk - recovered
  return { atRisk, recovered, unresolved, escalatedCount, correctlyNoAction }
}

export default function App() {
  const [events, setEvents] = useState([])
  const [loading, setLoading] = useState(true)
  const [expandedId, setExpandedId] = useState(null)
  const [activeFilter, setActiveFilter] = useState('all')
  const [sortByAmount, setSortByAmount] = useState(null) // null | 'asc' | 'desc'

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

  if (loading) return <div className="loading">Loading payment events...</div>

  const metrics = computeMetrics(events)

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
        <h1>PayResQ — Payment Recovery Dashboard</h1>
        <p className="subtitle">{events.length} payment events tracked</p>
      </header>

      <section className="metrics">
        <div className="metric-card risk">
          <span className="label">₹ At Risk</span>
          <span className="value">{formatRupees(metrics.atRisk)}</span>
        </div>
        <div className="metric-card recovered">
          <span className="label">₹ Recovered</span>
          <span className="value">{formatRupees(metrics.recovered)}</span>
        </div>
        <div className="metric-card unresolved">
          <span className="label">₹ Unresolved</span>
          <span className="value">{formatRupees(metrics.unresolved)}</span>
        </div>
        <div className="metric-card">
          <span className="label">Escalated</span>
          <span className="value">{metrics.escalatedCount}</span>
        </div>
        <div className="metric-card">
          <span className="label">Correctly held back</span>
          <span className="value">{metrics.correctlyNoAction}</span>
        </div>
      </section>

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
                    {isRealPayment(e.payment_id) && (
                      <span className="real-badge" title="Verified via live Razorpay API">LIVE</span>
                    )}
                    {e.payment_id}
                  </td>
                  <td>{formatRupees(e.amount)}</td>
                  <td>
                    <span className={`status-badge ${e.status}`}>{e.status}</span>
                  </td>
                  <td>{e.classification || '—'}</td>
                  <td>{ACTION_LABELS[e.action_taken] || e.action_taken || '—'}</td>
                </tr>
                {expandedId === e.payment_id && (
                  <tr className="reasoning-row">
                    <td colSpan={5}>
                      <strong>Reasoning:</strong> {e.reasoning || 'No reasoning recorded (rules-based, no LLM call needed).'}
                      {e.error_description && (
                        <div className="error-desc"><strong>Error:</strong> {e.error_description}</div>
                      )}
                    </td>
                  </tr>
                )}
              </>
            ))}
          </tbody>
        </table>
        {displayedEvents.length === 0 && (
          <div className="empty-state">No events match this filter.</div>
        )}
      </section>
    </div>
  )
}