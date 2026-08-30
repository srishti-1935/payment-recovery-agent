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

function formatRupees(paise) {
  return `₹${(paise / 100).toLocaleString('en-IN', { minimumFractionDigits: 2 })}`
}

function computeMetrics(events) {
  let atRisk = 0
  let recovered = 0
  let unresolved = 0
  let escalatedCount = 0
  let correctlyNoAction = 0

  for (const e of events) {
    if (e.classification === 'success') continue
    atRisk += e.amount

    if (e.action_taken === 'capture_and_notify' || e.action_taken === 'auto_retry') {
      recovered += e.amount
    } else {
      unresolved += e.amount
    }

    if (e.action_taken === 'escalate_to_merchant') escalatedCount += 1
    if (e.action_taken === 'wait_and_reassure' || e.action_taken === 'no_action') {
      correctlyNoAction += 1
    }
  }

  return { atRisk, recovered, unresolved, escalatedCount, correctlyNoAction }
}

export default function App() {
  const [events, setEvents] = useState([])
  const [loading, setLoading] = useState(true)
  const [expandedId, setExpandedId] = useState(null)

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
    const interval = setInterval(fetchEvents, 8000) // simple polling, no websockets
    return () => clearInterval(interval)
  }, [])

  if (loading) return <div className="loading">Loading payment events...</div>

  const metrics = computeMetrics(events)

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

      <section className="table-section">
        <table>
          <thead>
            <tr>
              <th>Payment ID</th>
              <th>Amount</th>
              <th>Status</th>
              <th>Classification</th>
              <th>Action</th>
            </tr>
          </thead>
          <tbody>
            {events.map((e) => (
              <>
                <tr
                  key={e.payment_id}
                  className="event-row"
                  onClick={() => setExpandedId(expandedId === e.payment_id ? null : e.payment_id)}
                >
                  <td>{e.payment_id}</td>
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
      </section>
    </div>
  )
}