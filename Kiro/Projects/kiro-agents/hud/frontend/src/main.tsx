import React, { useState, useEffect } from 'react'
import ReactDOM from 'react-dom/client'
import { AreaChart, Area, BarChart, Bar, XAxis, YAxis, Tooltip, ResponsiveContainer, CartesianGrid } from 'recharts'
import './index.css'

const API = ''  // Same origin — proxied through nginx to backend

// ── Grafana-style Panel ──────────────────────────────────────────────────────
function Panel({ title, subtitle, children, span = 1 }: { title: string; subtitle?: string; children: React.ReactNode; span?: number }) {
  return (
    <div className={`bg-gray-900 border border-gray-800 rounded-lg flex flex-col ${span === 2 ? 'col-span-2' : ''}`}>
      <div className="px-4 py-2.5 border-b border-gray-800/60 flex items-center justify-between shrink-0">
        <span className="text-xs font-medium text-gray-300">{title}</span>
        {subtitle && <span className="text-[10px] text-gray-500">{subtitle}</span>}
      </div>
      <div className="flex-1 p-3 min-h-0">{children}</div>
    </div>
  )
}

function TimeSeriesChart({ data, color, dataKey = 'value', height = 180 }: { data: { time: string; value: number }[]; color: string; dataKey?: string; height?: number }) {
  return (
    <ResponsiveContainer width="100%" height={height}>
      <AreaChart data={data} margin={{ top: 4, right: 4, bottom: 0, left: 0 }}>
        <CartesianGrid strokeDasharray="3 3" stroke="#1f2937" />
        <XAxis dataKey="time" tick={{ fontSize: 9, fill: '#6b7280' }} axisLine={{ stroke: '#374151' }} tickLine={false} interval={Math.max(0, Math.floor(data.length / 8))} />
        <YAxis tick={{ fontSize: 9, fill: '#6b7280' }} axisLine={false} tickLine={false} width={32} />
        <Tooltip contentStyle={{ background: '#111827', border: '1px solid #374151', borderRadius: 6, fontSize: 11, padding: '6px 10px' }} labelStyle={{ color: '#9ca3af', marginBottom: 2 }} cursor={{ stroke: '#4b5563' }} />
        <Area type="monotone" dataKey={dataKey} stroke={color} fill={color} fillOpacity={0.1} strokeWidth={1.5} dot={false} />
      </AreaChart>
    </ResponsiveContainer>
  )
}

function BarPanel({ data, color, prefix = '', height = 180 }: { data: { name: string; value: number }[]; color: string; prefix?: string; height?: number }) {
  return (
    <ResponsiveContainer width="100%" height={height}>
      <BarChart data={data} margin={{ top: 4, right: 4, bottom: 0, left: 0 }}>
        <CartesianGrid strokeDasharray="3 3" stroke="#1f2937" vertical={false} />
        <XAxis dataKey="name" tick={{ fontSize: 9, fill: '#6b7280' }} axisLine={{ stroke: '#374151' }} tickLine={false} />
        <YAxis tick={{ fontSize: 9, fill: '#6b7280' }} axisLine={false} tickLine={false} width={32} />
        <Tooltip contentStyle={{ background: '#111827', border: '1px solid #374151', borderRadius: 6, fontSize: 11, padding: '6px 10px' }} formatter={(v: number) => `${prefix}${typeof v === 'number' ? v.toLocaleString() : v}`} cursor={{ fill: '#1f293780' }} />
        <Bar dataKey="value" fill={color} radius={[3, 3, 0, 0]} />
      </BarChart>
    </ResponsiveContainer>
  )
}

// Legacy aliases used in Dashboard
function MiniChart({ data, color }: { data: { time: string; value: number }[]; color: string }) {
  return <TimeSeriesChart data={data} color={color} height={120} />
}
function BarMini({ data, color, prefix = '' }: { data: { name: string; value: number }[]; color: string; prefix?: string }) {
  return <BarPanel data={data} color={color} prefix={prefix} height={120} />
}

function App() {
  const [token, setToken] = useState(localStorage.getItem('hud_token') || '')
  const [tab, setTab] = useState<'dashboard' | 'agents' | 'infra' | 'darius' | 'projects' | 'tickets' | 'memory' | 'security' | 'clients' | 'contracts' | 'governance' | 'sre-int' | 'sre-ext' | 'graph'>('dashboard')
  const [password, setPassword] = useState('')
  const [data, setData] = useState<any>(null)
  const [agents, setAgents] = useState<any[]>([])
  const [infra, setInfra] = useState<any[]>([])
  const [extra, setExtra] = useState<any>({})
  const [error, setError] = useState('')

  async function login() {
    setError('')
    const totp = (document.getElementById('totp') as HTMLInputElement)?.value || ''
    try {
      const res = await fetch(`${API}/api/login`, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ password, totp }) })
      if (res.ok) { const d = await res.json(); setToken(d.token); localStorage.setItem('hud_token', d.token); setPassword('') }
      else { const d = await res.json(); setError(d.detail || 'Login failed') }
    } catch (e) { setError('Cannot connect to HUD backend') }
  }

  async function load() {
    const h = { Authorization: `Bearer ${token}` }
    const [d, a, i, dar, proj, tix, mem, sec, cli, ctr, gov, si, se] = await Promise.all([
      fetch(`${API}/api/dashboard`, { headers: h }).then(r => r.json()),
      fetch(`${API}/api/agents`, { headers: h }).then(r => r.json()),
      fetch(`${API}/api/infrastructure`, { headers: h }).then(r => r.json()),
      fetch(`${API}/api/darius`, { headers: h }).then(r => r.json()).catch(() => ({})),
      fetch(`${API}/api/projects`, { headers: h }).then(r => r.json()).catch(() => ({})),
      fetch(`${API}/api/tickets`, { headers: h }).then(r => r.json()).catch(() => ({})),
      fetch(`${API}/api/memory`, { headers: h }).then(r => r.json()).catch(() => ({})),
      fetch(`${API}/api/security`, { headers: h }).then(r => r.json()).catch(() => ({})),
      fetch(`${API}/api/clients`, { headers: h }).then(r => r.json()).catch(() => ({})),
      fetch(`${API}/api/contracts`, { headers: h }).then(r => r.json()).catch(() => ({})),
      fetch(`${API}/api/governance`, { headers: h }).then(r => r.json()).catch(() => ({})),
      fetch(`${API}/api/sre/internal`, { headers: h }).then(r => r.json()).catch(() => ({})),
      fetch(`${API}/api/sre/external`, { headers: h }).then(r => r.json()).catch(() => ({})),
    ])
    setData(d); setAgents(a.agents || []); setInfra(i.services || [])
    setExtra({ darius: dar, projects: proj, tickets: tix, memory: mem, security: sec, clients: cli, contracts: ctr, governance: gov, sreInt: si, sreExt: se })
  }

  useEffect(() => { if (token) { load(); const proto = window.location.protocol === 'https:' ? 'wss' : 'ws'; const ws = new WebSocket(`${proto}://${window.location.host}/api/ws`); ws.onmessage = (e) => { try { const d = JSON.parse(e.data); if (d.type === 'live') setData((prev: any) => prev ? {...prev, containers_running: d.containers_running} : prev) } catch {} }; return () => ws.close() } }, [token])

  if (!token) return (
    <div className="min-h-screen bg-gray-950 flex items-center justify-center">
      <div className="bg-gray-900 border border-gray-800 rounded-xl p-8 w-80">
        <h1 className="text-xl font-bold text-white mb-1">Melanin Tech HUD</h1>
        <p className="text-xs text-gray-500 mb-6">Internal monitoring — authorized access only</p>
        <input type="password" value={password} onChange={e => setPassword(e.target.value)} placeholder="Password" className="w-full px-4 py-3 bg-gray-800 border border-gray-700 rounded-lg text-white text-sm mb-3 outline-none focus:border-cyan-500" />
        <input type="text" id="totp" maxLength={6} placeholder="2FA Code" className="w-full px-4 py-3 bg-gray-800 border border-gray-700 rounded-lg text-white text-sm mb-3 outline-none focus:border-cyan-500 tracking-widest text-center" onKeyDown={e => e.key === 'Enter' && login()} />
        {error && <p className="text-red-400 text-xs mb-3">{error}</p>}
        <button onClick={login} className="w-full py-3 bg-cyan-600 hover:bg-cyan-500 text-white font-medium rounded-lg text-sm">Access HUD</button>
      </div>
    </div>
  )

  return (
    <div className="min-h-screen bg-gray-950 text-white">
      <header className="border-b border-gray-800 px-6 py-3 flex items-center justify-between">
        <div className="flex items-center gap-4">
          <h1 className="text-sm font-bold text-cyan-400">MELANIN TECH HUD</h1>
          <div className="flex gap-1">
            {([['dashboard','Executive'],['agents','Agents'],['infra','Infrastructure'],['darius','Darius'],['projects','Projects'],['tickets','Tickets'],['memory','Memory'],['security','Security'],['clients','Clients'],['contracts','Contracts'],['governance','Governance'],['sre-int','SRE Internal'],['sre-ext','SRE External'],['graph','Graph']] as const).map(([t, label]) => (
              <button key={t} onClick={() => setTab(t)} className={`px-3 py-1.5 text-xs font-medium rounded ${tab === t ? 'bg-cyan-600 text-white' : 'text-gray-400 hover:text-white'}`}>
                {label}
              </button>
            ))}
          </div>
        </div>
        <div className="flex items-center gap-3">
          <span className="w-2 h-2 rounded-full bg-emerald-400 animate-pulse" />
          <span className="text-xs text-gray-500">Live</span>
          <button onClick={() => { setToken(''); localStorage.removeItem('hud_token') }} className="text-xs text-gray-500 hover:text-white">Logout</button>
        </div>
      </header>

      <main className="p-6">
        {tab === 'dashboard' && data && <Dashboard data={data} />}
        {tab === 'agents' && <Agents agents={agents} />}
        {tab === 'infra' && <Infrastructure services={infra} />}
        {tab === 'darius' && <GenericTable title="Darius Sessions" data={extra.darius?.recent_sessions || []} summary={`Total sessions: ${extra.darius?.total_sessions || 0}`} />}
        {tab === 'projects' && <ProjectsTab projects={extra.projects?.projects || []} />}
        {tab === 'tickets' && <TicketsTab data={extra.tickets} />}
        {tab === 'memory' && <MemoryTab data={extra.memory} />}
        {tab === 'security' && <SecurityTab data={extra.security} />}
        {tab === 'clients' && <ClientsTab clients={extra.clients?.clients || []} />}
        {tab === 'contracts' && <ContractsTab data={extra.contracts} token={token} />}
        {tab === 'governance' && <GovernanceTab data={extra.governance} token={token} />}
        {tab === 'sre-int' && <SRETab data={extra.sreInt} token={token} scope="internal" title="SRE — Internal Infrastructure" />}
        {tab === 'sre-ext' && <SRETab data={extra.sreExt} token={token} scope="external" title="SRE — External Services" />}
        {tab === 'graph' && <div><h2 className="text-lg font-semibold mb-4">Infrastructure Knowledge Graph</h2><p className="text-xs text-gray-500 mb-4">491 nodes · 769 edges · 38 communities — interactive visualization of your codebase</p><iframe src="/graphify-out/graph.html" className="w-full rounded-xl border border-gray-800" style={{height:'calc(100vh - 200px)'}} sandbox="allow-scripts allow-same-origin" title="Knowledge Graph" /></div>}
      </main>
    </div>
  )
}

function Dashboard({ data }: { data: any }) {
  const [charts, setCharts] = React.useState<any>(null)
  const token = localStorage.getItem('hud_token') || ''

  React.useEffect(() => {
    fetch(`${API}/api/charts/executive`, { headers: { Authorization: `Bearer ${token}` } })
      .then(r => r.json()).then(setCharts).catch(() => null)
  }, [])

  return (
    <div>
      <div className="flex items-center justify-between mb-4">
        <h2 className="text-lg font-semibold">Executive Dashboard</h2>
        <span className="text-[10px] text-gray-600">Auto-refresh · 30s</span>
      </div>

      <div className="grid grid-cols-2 lg:grid-cols-4 gap-3 mb-4">
        <Stat label="Containers Running" value={data.containers_running} color="text-cyan-400" />
        <Stat label="Memory Entries" value={data.memory_entries} color="text-violet-400" />
        <Stat label="Tickets Done" value={data.tickets?.done || 0} color="text-emerald-400" />
        <Stat label="Tickets Open" value={(data.tickets?.open || 0) + (data.tickets?.in_progress || 0)} color="text-amber-400" />
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-3 mb-3" style={{ gridAutoRows: '240px' }}>
        {charts?.snapshots?.length > 0 && (
          <Panel title="Container Health" subtitle="24h">
            <TimeSeriesChart data={charts.snapshots.map((s: any) => ({ time: s.created_at?.slice(11, 16) || '', value: s.containers_running || 0 }))} color="#22d3ee" />
          </Panel>
        )}
        {charts?.snapshots?.length > 0 && (
          <Panel title="Memory Growth" subtitle="24h">
            <TimeSeriesChart data={charts.snapshots.map((s: any) => ({ time: s.created_at?.slice(11, 16) || '', value: s.memory_entries || 0 }))} color="#a78bfa" />
          </Panel>
        )}
        {charts?.agent_distribution?.length > 0 && (
          <Panel title="Tasks by Agent" subtitle="all time">
            <BarPanel data={charts.agent_distribution.map((a: any) => ({ name: a.agent?.replace('Agent', '') || '?', value: a.count }))} color="#34d399" />
          </Panel>
        )}
        {charts?.llm_usage?.length > 0 && (
          <Panel title="LLM Spend" subtitle="7 days">
            <BarPanel data={charts.llm_usage.map((u: any) => ({ name: u.date?.slice(5) || '', value: u.cost }))} color="#fbbf24" prefix="$" />
          </Panel>
        )}
      </div>

      <Panel title="Recent Tickets" subtitle={`${data.recent_tickets?.length || 0} latest`}>
        <div className="space-y-2 overflow-y-auto max-h-48">
          {data.recent_tickets?.map((t: any) => (
            <div key={t.id} className="flex items-center justify-between text-sm">
              <div className="flex items-center gap-2">
                <span className={`w-2 h-2 rounded-full ${t.status === 'done' ? 'bg-emerald-400' : t.status === 'open' ? 'bg-amber-400' : 'bg-blue-400'}`} />
                <span className="text-gray-300">#{t.id}</span>
                <span className="text-gray-500 truncate max-w-md">{t.task}</span>
              </div>
              <span className="text-xs text-gray-600">{t.agent}</span>
            </div>
          ))}
        </div>
      </Panel>
    </div>
  )
}

function Agents({ agents }: { agents: any[] }) {
  const [charts, setCharts] = React.useState<any>(null)
  const token = localStorage.getItem('hud_token') || ''
  React.useEffect(() => {
    fetch(`${API}/api/charts/agents`, { headers: { Authorization: `Bearer ${token}` } })
      .then(r => r.json()).then(setCharts).catch(() => null)
  }, [])

  const running = agents.filter(a => a.status === 'running').length

  return (
    <div>
      <div className="flex items-center justify-between mb-4">
        <h2 className="text-lg font-semibold">Agents</h2>
        <span className="text-xs text-gray-500">{running}/{agents.length} running</span>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-3 mb-4" style={{ gridAutoRows: '240px' }}>
        {charts?.by_agent?.length > 0 && (
          <Panel title="Total Tasks per Agent" subtitle="all time">
            <BarPanel data={charts.by_agent.map((a: any) => ({ name: a.agent?.replace('Agent', '') || '?', value: a.total }))} color="#34d399" />
          </Panel>
        )}
        {charts?.by_agent?.length > 0 && (
          <Panel title="Completion Rate %" subtitle="done / total">
            <BarPanel data={charts.by_agent.map((a: any) => ({ name: a.agent?.replace('Agent', '') || '?', value: a.total > 0 ? Math.round((a.done / a.total) * 100) : 0 }))} color="#22d3ee" />
          </Panel>
        )}
      </div>

      <Panel title="Agent Status" subtitle="live">
        <div className="grid gap-2 overflow-y-auto max-h-80">
          {agents.map(a => (
            <div key={a.name} className="flex items-center justify-between px-3 py-2 rounded-md bg-gray-800/40">
              <div className="flex items-center gap-3">
                <span className={`w-2 h-2 rounded-full ${a.status === 'running' ? 'bg-emerald-400' : 'bg-red-400'}`} />
                <span className="text-sm text-white">{a.name}</span>
              </div>
              <div className="flex items-center gap-4">
                <span className={`text-xs ${a.status === 'running' ? 'text-emerald-400' : 'text-red-400'}`}>{a.status}</span>
                {a.uptime && <span className="text-xs text-gray-600">up since {new Date(a.uptime).toLocaleDateString()}</span>}
              </div>
            </div>
          ))}
        </div>
      </Panel>
    </div>
  )
}

function Infrastructure({ services }: { services: any[] }) {
  const running = services.filter(s => s.status === 'running').length
  return (
    <div>
      <div className="flex items-center justify-between mb-4">
        <h2 className="text-lg font-semibold">Infrastructure</h2>
        <span className="text-xs text-gray-500">{running}/{services.length} running</span>
      </div>
      <Panel title="All Containers" subtitle={`${services.length} services`}>
        <div className="overflow-y-auto max-h-[calc(100vh-240px)]">
          <table className="w-full text-sm">
            <thead><tr className="text-gray-500 text-xs">
              <th className="text-left pb-2">Container</th>
              <th className="text-left pb-2">Status</th>
              <th className="text-left pb-2">Started</th>
            </tr></thead>
            <tbody>
              {services.map(s => (
                <tr key={s.name} className="border-t border-gray-800/40">
                  <td className="py-1.5 text-gray-300">{s.name}</td>
                  <td className="py-1.5"><span className={`text-xs ${s.status === 'running' ? 'text-emerald-400' : 'text-red-400'}`}>{s.status}</span></td>
                  <td className="py-1.5 text-xs text-gray-600">{s.started ? new Date(s.started).toLocaleString() : '—'}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </Panel>
    </div>
  )
}

function Stat({ label, value, color }: { label: string; value: number | string; color: string }) {
  return (
    <div className="bg-gray-900 border border-gray-800 rounded-xl p-4">
      <p className={`text-2xl font-bold ${color}`}>{value}</p>
      <p className="text-xs text-gray-500 mt-1">{label}</p>
    </div>
  )
}

function GenericTable({ title, data, summary }: { title: string; data: any[]; summary?: string }) {
  return (
    <div>
      <h2 className="text-lg font-semibold mb-2">{title}</h2>
      {summary && <p className="text-sm text-gray-500 mb-4">{summary}</p>}
      <div className="bg-gray-900 border border-gray-800 rounded-xl p-4 space-y-2">
        {data.length === 0 ? <p className="text-gray-600 text-sm">No data</p> : data.map((r, i) => (
          <div key={i} className="text-sm text-gray-300 flex justify-between">
            <span>{r.session_id || r.name || JSON.stringify(r).slice(0, 60)}</span>
            <span className="text-gray-600">{r.turns || r.count || ''} turns</span>
          </div>
        ))}
      </div>
    </div>
  )
}

function ProjectsTab({ projects }: { projects: any[] }) {
  return (
    <div>
      <h2 className="text-lg font-semibold mb-4">Projects</h2>
      <div className="grid gap-3">
        {projects.map(p => (
          <div key={p.name} className="bg-gray-900 border border-gray-800 rounded-xl p-4 flex items-center justify-between">
            <div>
              <p className="text-sm font-medium text-white">{p.name}</p>
              <a href={p.url} target="_blank" className="text-xs text-cyan-500">{p.url}</a>
            </div>
            <span className={`text-xs ${p.status === 'running' ? 'text-emerald-400' : 'text-red-400'}`}>{p.status}</span>
          </div>
        ))}
      </div>
    </div>
  )
}

function TicketsTab({ data }: { data: any }) {
  const [charts, setCharts] = React.useState<any>(null)
  const token = localStorage.getItem('hud_token') || ''
  React.useEffect(() => {
    fetch(`${API}/api/charts/tickets`, { headers: { Authorization: `Bearer ${token}` } })
      .then(r => r.json()).then(setCharts).catch(() => null)
  }, [])

  return (
    <div>
      <div className="flex items-center justify-between mb-4">
        <h2 className="text-lg font-semibold">Tickets</h2>
        <div className="flex gap-2">
          {Object.entries(data?.summary || {}).map(([k, v]) => (
            <span key={k} className="text-[10px] bg-gray-800 px-2.5 py-1 rounded-full text-gray-400">{k}: {v as number}</span>
          ))}
        </div>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-3 mb-4" style={{ gridAutoRows: '240px' }}>
        {charts?.opened_trend?.length > 0 && (
          <Panel title="Tickets Opened" subtitle="30 days">
            <TimeSeriesChart data={charts.opened_trend.map((r: any) => ({ time: r.date?.slice(5) || '', value: r.opened }))} color="#fbbf24" />
          </Panel>
        )}
        {charts?.by_agent?.length > 0 && (
          <Panel title="Volume by Agent" subtitle="30 days">
            <BarPanel data={charts.by_agent.map((a: any) => ({ name: a.agent?.replace('Agent', '') || '?', value: a.count }))} color="#a78bfa" />
          </Panel>
        )}
      </div>

      <Panel title="Recent Tickets" subtitle={`${(data?.tickets || []).length} shown`}>
        <div className="space-y-1.5 overflow-y-auto max-h-72">
          {(data?.tickets || []).map((t: any) => (
            <div key={t.id} className="flex items-center justify-between text-sm px-2 py-1.5 rounded bg-gray-800/30">
              <div className="flex items-center gap-2">
                <span className={`w-2 h-2 rounded-full ${t.status === 'done' ? 'bg-emerald-400' : t.status === 'cancelled' ? 'bg-gray-600' : 'bg-amber-400'}`} />
                <span className="text-gray-500 text-xs">#{t.id}</span>
                <span className="text-gray-300 truncate max-w-lg">{t.task}</span>
              </div>
              <span className="text-xs text-gray-600">{t.agent}</span>
            </div>
          ))}
        </div>
      </Panel>
    </div>
  )
}

function MemoryTab({ data }: { data: any }) {
  return (
    <div>
      <h2 className="text-lg font-semibold mb-2">Memory</h2>
      <div className="flex gap-3 mb-4">
        <span className="text-xs bg-gray-800 px-3 py-1 rounded-full text-violet-400">Task memory: {data?.task_count || 0}</span>
        <span className="text-xs bg-gray-800 px-3 py-1 rounded-full text-cyan-400">Conversation: {data?.conv_count || 0}</span>
      </div>
      <div className="grid lg:grid-cols-2 gap-4">
        <div className="bg-gray-900 border border-gray-800 rounded-xl p-4">
          <h3 className="text-sm text-gray-400 mb-3">Recent Task Decisions</h3>
          <div className="space-y-2">
            {(data?.task_memory || []).slice(0, 10).map((m: any) => (
              <div key={m.id} className="text-xs">
                <span className={`${m.decision === 'approved' ? 'text-emerald-400' : 'text-red-400'}`}>[{m.decision}]</span>
                <span className="text-gray-400 ml-2">{m.agent}</span>
                <span className="text-gray-600 ml-2">{m.task?.slice(0, 60)}</span>
              </div>
            ))}
          </div>
        </div>
        <div className="bg-gray-900 border border-gray-800 rounded-xl p-4">
          <h3 className="text-sm text-gray-400 mb-3">Conversation Memory</h3>
          <div className="space-y-2">
            {(data?.conversation_memory || []).slice(0, 10).map((m: any) => (
              <div key={m.id} className="text-xs">
                <span className="text-cyan-400">[{m.role}]</span>
                <span className="text-gray-500 ml-2">{m.content}</span>
              </div>
            ))}
          </div>
        </div>
      </div>
    </div>
  )
}

function SecurityTab({ data }: { data: any }) {
  return (
    <div>
      <h2 className="text-lg font-semibold mb-4">Security</h2>
      <div className="grid gap-3">
        <div className="bg-gray-900 border border-gray-800 rounded-xl p-4 flex justify-between">
          <span className="text-sm text-gray-300">TLS Certificate Expiry</span>
          <span className="text-sm text-emerald-400">{data?.cert_expiry || 'unknown'}</span>
        </div>
        <div className="bg-gray-900 border border-gray-800 rounded-xl p-4 flex justify-between">
          <span className="text-sm text-gray-300">fail2ban</span>
          <span className={`text-sm ${data?.fail2ban === 'running' ? 'text-emerald-400' : 'text-red-400'}`}>{data?.fail2ban || 'unknown'}</span>
        </div>
        <div className="bg-gray-900 border border-gray-800 rounded-xl p-4 flex justify-between">
          <span className="text-sm text-gray-300">NPM Audit</span>
          <span className="text-sm text-gray-500">{data?.npm_audit || 'unknown'}</span>
        </div>
      </div>
    </div>
  )
}

function ClientsTab({ clients }: { clients: any[] }) {
  return (
    <div>
      <h2 className="text-lg font-semibold mb-4">Clients (OrthoFlow)</h2>
      <div className="bg-gray-900 border border-gray-800 rounded-xl overflow-hidden">
        <table className="w-full text-sm">
          <thead><tr className="border-b border-gray-800">
            <th className="px-4 py-2 text-left text-xs text-gray-500">Practice</th>
            <th className="px-4 py-2 text-left text-xs text-gray-500">Invoices</th>
            <th className="px-4 py-2 text-left text-xs text-gray-500">Since</th>
          </tr></thead>
          <tbody>
            {clients.map((c: any) => (
              <tr key={c.id} className="border-b border-gray-800/50">
                <td className="px-4 py-2 text-gray-300">{c.name}</td>
                <td className="px-4 py-2 text-gray-400">{c.invoice_count}</td>
                <td className="px-4 py-2 text-xs text-gray-600">{c.created_at ? new Date(c.created_at).toLocaleDateString() : '—'}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  )
}

function DariusMarkdown({ text }: { text: string }) {
  const lines = text.split('\n')
  return (
    <div className="space-y-1.5">
      {lines.map((line, i) => {
        if (line.startsWith('### ')) return <p key={i} className="font-semibold text-white mt-2">{line.slice(4)}</p>
        if (line.startsWith('## ')) return <p key={i} className="font-bold text-white mt-3">{line.slice(3)}</p>
        if (line.startsWith('# ')) return <p key={i} className="font-bold text-white text-sm mt-3">{line.slice(2)}</p>
        if (line.startsWith('- ') || line.startsWith('• ')) return <p key={i} className="pl-3 before:content-['•'] before:mr-2 before:text-violet-400">{renderInline(line.slice(2))}</p>
        if (line.startsWith('```')) return <div key={i} className="border-l-2 border-violet-500/30 pl-2 font-mono text-[10px] text-gray-400" />
        if (line.match(/^\d+\.\s/)) return <p key={i} className="pl-3">{renderInline(line)}</p>
        if (line.startsWith('|')) return <p key={i} className="font-mono text-[10px] text-gray-400">{line}</p>
        if (line.startsWith('---') || line.startsWith('━')) return <hr key={i} className="border-gray-700 my-2" />
        if (line.trim() === '') return <div key={i} className="h-1" />
        return <p key={i}>{renderInline(line)}</p>
      })}
    </div>
  )
}

function renderInline(text: string): React.ReactNode {
  // Bold: **text** or __text__
  const parts = text.split(/(\*\*[^*]+\*\*|__[^_]+__|\*[^*]+\*|`[^`]+`)/)
  return parts.map((part, i) => {
    if (part.startsWith('**') && part.endsWith('**')) return <strong key={i} className="text-white font-semibold">{part.slice(2, -2)}</strong>
    if (part.startsWith('*') && part.endsWith('*')) return <em key={i} className="text-gray-200">{part.slice(1, -1)}</em>
    if (part.startsWith('`') && part.endsWith('`')) return <code key={i} className="bg-gray-700/50 px-1 rounded text-violet-300 text-[10px]">{part.slice(1, -1)}</code>
    return <span key={i}>{part}</span>
  })
}

function ContractsTab({ data, token }: { data: any; token: string }) {
  const [dariusOpen, setDariusOpen] = React.useState(false)
  const [messages, setMessages] = React.useState<{role:string;content:string}[]>([{role:'assistant',content:'I\'m Darius — your contract intelligence assistant. Ask me about rate optimization, renewal timing, or invoicing strategy.'}])
  const [input, setInput] = React.useState('')
  const [loading, setLoading] = React.useState(false)
  const [charts, setCharts] = React.useState<any>(null)
  const contracts = data?.contracts || []
  const stats = data?.stats || {}

  React.useEffect(() => {
    fetch(`${API}/api/charts/contracts`, { headers: { Authorization: `Bearer ${token}` } })
      .then(r => r.json()).then(setCharts).catch(() => null)
  }, [])

  async function askDarius() {
    if (!input.trim()) return
    setMessages(p => [...p, {role:'user',content:input}])
    setInput(''); setLoading(true)
    try {
      const r = await fetch(`${API}/api/contracts/darius`, {method:'POST',headers:{'Authorization':`Bearer ${token}`,'Content-Type':'application/json'},body:JSON.stringify({message:input})})
      const d = await r.json()
      setMessages(p => [...p, {role:'assistant',content:d.reply}])
    } catch { setMessages(p => [...p, {role:'assistant',content:'Darius unavailable.'}]) }
    setLoading(false)
  }

  const statusColor: Record<string,string> = {active:'bg-emerald-400',pending:'bg-amber-400',completed:'bg-blue-400',expired:'bg-red-400'}

  return (
    <div>
      <div className="flex items-center justify-between mb-6">
        <h2 className="text-lg font-semibold">Contracts</h2>
        <button onClick={() => setDariusOpen(!dariusOpen)} className={`px-3 py-1.5 text-xs font-medium rounded ${dariusOpen ? 'bg-violet-600 text-white' : 'bg-gray-800 text-violet-400 border border-violet-500/30'}`}>
          ✦ Darius AI
        </button>
      </div>

      <div className="grid grid-cols-2 lg:grid-cols-4 gap-4 mb-6">
        <div className="bg-gray-900 border border-gray-800 rounded-xl p-4"><p className="text-xs text-gray-500 mb-1">Active</p><p className="text-xl font-bold text-cyan-400">{stats.active || 0}</p></div>
        <div className="bg-gray-900 border border-gray-800 rounded-xl p-4"><p className="text-xs text-gray-500 mb-1">Monthly Revenue</p><p className="text-xl font-bold text-emerald-400">${(stats.monthly_revenue || 0).toLocaleString()}</p></div>
        <div className="bg-gray-900 border border-gray-800 rounded-xl p-4"><p className="text-xs text-gray-500 mb-1">Outstanding</p><p className="text-xl font-bold text-amber-400">${(stats.outstanding || 0).toLocaleString()}</p></div>
        <div className="bg-gray-900 border border-gray-800 rounded-xl p-4"><p className="text-xs text-gray-500 mb-1">Avg Net Rate</p><p className="text-xl font-bold">${stats.avg_net_rate || 0}/hr</p></div>
      </div>

      {charts && (charts.revenue_by_client?.length > 0 || charts.outstanding_by_client?.length > 0) && (
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-3 mb-4" style={{ gridAutoRows: '240px' }}>
          {charts.revenue_by_client?.length > 0 && (
            <Panel title="Monthly Revenue by Client" subtitle="active contracts">
              <BarPanel data={charts.revenue_by_client} color="#34d399" prefix="$" />
            </Panel>
          )}
          {charts.outstanding_by_client?.length > 0 && (
            <Panel title="Outstanding Balance" subtitle="unpaid">
              <BarPanel data={charts.outstanding_by_client} color="#fbbf24" prefix="$" />
            </Panel>
          )}
        </div>
      )}

      <div className="flex gap-4">
        <div className={`${dariusOpen ? 'w-[60%]' : 'w-full'} bg-gray-900 border border-gray-800 rounded-xl overflow-hidden`}>
          <table className="w-full text-sm">
            <thead><tr className="border-b border-gray-800 text-gray-500 text-xs">
              <th className="text-left px-4 py-3">ID</th><th className="text-left px-4 py-3">Role</th><th className="text-left px-4 py-3">Client</th><th className="text-left px-4 py-3">Firm</th><th className="text-right px-4 py-3">Net Rate</th><th className="text-right px-4 py-3">Outstanding</th><th className="px-4 py-3">Status</th>
            </tr></thead>
            <tbody>
              {contracts.map((c: any) => (
                <tr key={c.id} className="border-b border-gray-800/50 hover:bg-gray-800/30">
                  <td className="px-4 py-3 font-mono text-xs text-gray-500">{c.id}</td>
                  <td className="px-4 py-3 text-gray-200">{c.role}</td>
                  <td className="px-4 py-3 text-gray-400">{c.client}</td>
                  <td className="px-4 py-3 text-gray-500 text-xs">{c.staffing_firm}</td>
                  <td className="px-4 py-3 text-right text-emerald-400 font-medium">${c.net_rate}/hr</td>
                  <td className="px-4 py-3 text-right">{c.outstanding > 0 ? <span className="text-amber-400">${c.outstanding.toLocaleString()}</span> : <span className="text-gray-600">—</span>}</td>
                  <td className="px-4 py-3 text-center"><span className={`inline-block w-2 h-2 rounded-full ${statusColor[c.status] || 'bg-gray-500'}`} /></td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>

        {dariusOpen && (
          <div className="w-[40%] bg-gray-900 border border-violet-500/20 rounded-xl flex flex-col h-[500px]">
            <div className="px-4 py-3 border-b border-gray-800 text-xs font-medium text-violet-400">✦ Darius — Contract Intelligence</div>
            <div className="flex-1 overflow-y-auto p-3 space-y-3">
              {messages.map((m, i) => (
                <div key={i} className={`text-xs leading-relaxed px-3 py-2 rounded-lg max-w-[90%] ${m.role === 'user' ? 'ml-auto bg-blue-600/20 border border-blue-500/30 text-blue-100' : 'bg-gray-800 border border-gray-700 text-gray-300'}`}>
                  {m.role === 'assistant' ? <DariusMarkdown text={m.content} /> : m.content}
                </div>
              ))}
              {loading && <div className="text-xs text-gray-500 animate-pulse px-3">Thinking...</div>}
            </div>
            <div className="p-3 border-t border-gray-800 flex gap-2">
              <input value={input} onChange={e => setInput(e.target.value)} onKeyDown={e => e.key === 'Enter' && askDarius()} placeholder="Ask Darius..." className="flex-1 bg-gray-800 border border-gray-700 rounded-lg px-3 py-2 text-xs text-white outline-none focus:border-violet-500" />
              <button onClick={askDarius} disabled={loading} className="px-3 py-2 bg-violet-600 rounded-lg text-xs disabled:opacity-50">→</button>
            </div>
          </div>
        )}
      </div>
    </div>
  )
}

function SRETab({ data, token, scope, title }: { data: any; token: string; scope: string; title: string }) {
  const [dariusOpen, setDariusOpen] = React.useState(false)
  const [messages, setMessages] = React.useState<{role:string;content:string}[]>([{role:'assistant',content:`I'm Darius — your SRE assistant for ${scope} infrastructure. Ask about service health, latency, incidents, capacity, or troubleshooting.`}])
  const [input, setInput] = React.useState('')
  const [loading, setLoading] = React.useState(false)
  const [charts, setCharts] = React.useState<any>(null)
  const services = data?.services || []
  const endpoints = data?.endpoints || []
  const summary = data?.summary || {}

  React.useEffect(() => {
    fetch(`${API}/api/charts/sre`, { headers: { Authorization: `Bearer ${token}` } })
      .then(r => r.json()).then(setCharts).catch(() => null)
  }, [])

  async function askDarius() {
    if (!input.trim()) return
    setMessages(p => [...p, {role:'user',content:input}])
    setInput(''); setLoading(true)
    try {
      const r = await fetch(`${API}/api/sre/darius`, {method:'POST',headers:{'Authorization':`Bearer ${token}`,'Content-Type':'application/json'},body:JSON.stringify({message:input, scope})})
      const d = await r.json()
      setMessages(p => [...p, {role:'assistant',content:d.reply}])
    } catch { setMessages(p => [...p, {role:'assistant',content:'Darius unavailable.'}]) }
    setLoading(false)
  }

  return (
    <div>
      <div className="flex items-center justify-between mb-4">
        <h2 className="text-lg font-semibold">{title}</h2>
        <button onClick={() => setDariusOpen(!dariusOpen)} className={`px-3 py-1.5 text-xs font-medium rounded ${dariusOpen ? 'bg-violet-600 text-white' : 'bg-gray-800 text-violet-400 border border-violet-500/30'}`}>
          ✦ Darius AI
        </button>
      </div>

      <div className="grid grid-cols-2 lg:grid-cols-4 gap-3 mb-4">
        <Stat label="Running" value={summary.running || 0} color="text-emerald-400" />
        <Stat label="Down" value={summary.down || 0} color="text-red-400" />
        <Stat label="Total" value={summary.total || 0} color="text-cyan-400" />
        {summary.db_health && <Stat label="Database" value={summary.db_health} color={summary.db_health === 'healthy' ? 'text-emerald-400' : 'text-red-400'} />}
      </div>

      <div className="flex gap-3">
        <div className={`${dariusOpen ? 'w-[60%]' : 'w-full'} space-y-3`}>
          {charts?.snapshots?.length > 0 && (
            <div className="grid grid-cols-1 lg:grid-cols-2 gap-3" style={{ gridAutoRows: '240px' }}>
              <Panel title="Containers Running" subtitle="24h">
                <TimeSeriesChart data={charts.snapshots.map((s: any) => ({ time: s.created_at?.slice(11, 16) || '', value: s.containers_running || 0 }))} color="#22d3ee" />
              </Panel>
              <Panel title="Open Tickets" subtitle="24h">
                <TimeSeriesChart data={charts.snapshots.map((s: any) => ({ time: s.created_at?.slice(11, 16) || '', value: s.tickets_open || 0 }))} color="#fbbf24" />
              </Panel>
            </div>
          )}

          {endpoints.length > 0 && (
            <Panel title="Endpoint Health" subtitle="live">
              <div className="divide-y divide-gray-800/50">
                {endpoints.map((ep: any) => (
                  <div key={ep.name} className="flex items-center justify-between py-2">
                    <div className="flex items-center gap-2">
                      <span className={`w-2 h-2 rounded-full ${ep.status === 'up' ? 'bg-emerald-400' : 'bg-red-400'}`} />
                      <span className="text-sm text-gray-300">{ep.name}</span>
                    </div>
                    <div className="flex items-center gap-4">
                      <span className="text-xs text-gray-500">{ep.code || '—'}</span>
                      {ep.latency_ms > 0 && <span className="text-xs text-emerald-400/70">{ep.latency_ms}ms</span>}
                    </div>
                  </div>
                ))}
              </div>
            </Panel>
          )}

          <Panel title="Services" subtitle={`${services.length} total`}>
            <div className="overflow-y-auto max-h-64">
              <table className="w-full text-sm">
                <thead><tr className="text-gray-500 text-xs">
                  <th className="text-left pb-2">Service</th><th className="text-left pb-2">Status</th><th className="text-left pb-2">Started</th>
                </tr></thead>
                <tbody>
                  {services.map((s: any) => (
                    <tr key={s.name} className="border-t border-gray-800/40">
                      <td className="py-1.5 text-gray-300">{s.name}</td>
                      <td className="py-1.5"><span className={`text-xs ${s.status === 'running' ? 'text-emerald-400' : 'text-red-400'}`}>{s.status}</span></td>
                      <td className="py-1.5 text-xs text-gray-600">{s.started ? new Date(s.started).toLocaleString() : '—'}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </Panel>
        </div>

        {dariusOpen && (
          <div className="w-[40%] bg-gray-900 border border-violet-500/20 rounded-lg flex flex-col h-[600px]">
            <div className="px-4 py-2.5 border-b border-gray-800 text-xs font-medium text-violet-400 shrink-0">✦ Darius — SRE ({scope})</div>
            <div className="flex-1 overflow-y-auto p-3 space-y-3">
              {messages.map((m, i) => (
                <div key={i} className={`text-xs leading-relaxed px-3 py-2 rounded-lg max-w-[90%] ${m.role === 'user' ? 'ml-auto bg-blue-600/20 border border-blue-500/30 text-blue-100' : 'bg-gray-800 border border-gray-700 text-gray-300'}`}>
                  {m.role === 'assistant' ? <DariusMarkdown text={m.content} /> : m.content}
                </div>
              ))}
              {loading && <div className="text-xs text-gray-500 animate-pulse px-3">Thinking...</div>}
            </div>
            <div className="p-3 border-t border-gray-800 flex gap-2 shrink-0">
              <input value={input} onChange={e => setInput(e.target.value)} onKeyDown={e => e.key === 'Enter' && askDarius()} placeholder="Ask about services..." className="flex-1 bg-gray-800 border border-gray-700 rounded-lg px-3 py-2 text-xs text-white outline-none focus:border-violet-500" />
              <button onClick={askDarius} disabled={loading} className="px-3 py-2 bg-violet-600 rounded-lg text-xs disabled:opacity-50">→</button>
            </div>
          </div>
        )}
      </div>
    </div>
  )
}

function GovernanceTab({ data, token }: { data: any; token: string }) {
  const [dariusOpen, setDariusOpen] = React.useState(false)
  const [messages, setMessages] = React.useState<{role:string;content:string}[]>([{role:'assistant',content:'I\'m Darius — your governance & compliance assistant. Ask me about HIPAA controls, security gaps, policy status, or compliance readiness.'}])
  const [input, setInput] = React.useState('')
  const [loading, setLoading] = React.useState(false)
  const summary = data?.summary || {}
  const policies = data?.policies || []
  const tickets = data?.tickets || []

  async function askDarius() {
    if (!input.trim()) return
    setMessages(p => [...p, {role:'user',content:input}])
    setInput(''); setLoading(true)
    try {
      const r = await fetch(`${API}/api/governance/darius`, {method:'POST',headers:{'Authorization':`Bearer ${token}`,'Content-Type':'application/json'},body:JSON.stringify({message:input})})
      const d = await r.json()
      setMessages(p => [...p, {role:'assistant',content:d.reply}])
    } catch { setMessages(p => [...p, {role:'assistant',content:'Darius unavailable.'}]) }
    setLoading(false)
  }

  return (
    <div>
      <div className="flex items-center justify-between mb-6">
        <h2 className="text-lg font-semibold">Governance & Compliance</h2>
        <button onClick={() => setDariusOpen(!dariusOpen)} className={`px-3 py-1.5 text-xs font-medium rounded ${dariusOpen ? 'bg-violet-600 text-white' : 'bg-gray-800 text-violet-400 border border-violet-500/30'}`}>
          ✦ Darius AI
        </button>
      </div>

      <div className="grid grid-cols-2 lg:grid-cols-4 gap-4 mb-6">
        <div className="bg-gray-900 border border-gray-800 rounded-xl p-4"><p className="text-xs text-gray-500 mb-1">Policies</p><p className="text-xl font-bold text-cyan-400">{summary.total_policies || 0}</p></div>
        <div className="bg-gray-900 border border-gray-800 rounded-xl p-4"><p className="text-xs text-gray-500 mb-1">Controls Passed</p><p className="text-xl font-bold text-emerald-400">{summary.controls_passed || 0}</p></div>
        <div className="bg-gray-900 border border-gray-800 rounded-xl p-4"><p className="text-xs text-gray-500 mb-1">Controls Pending</p><p className="text-xl font-bold text-amber-400">{summary.controls_pending || 0}</p></div>
        <div className="bg-gray-900 border border-gray-800 rounded-xl p-4"><p className="text-xs text-gray-500 mb-1">Open Tickets</p><p className="text-xl font-bold text-red-400">{summary.open_tickets || 0}</p></div>
      </div>

      <div className="flex gap-4">
        <div className={`${dariusOpen ? 'w-[60%]' : 'w-full'} space-y-4`}>
          <div className="bg-gray-900 border border-gray-800 rounded-xl overflow-hidden">
            <div className="px-4 py-3 border-b border-gray-800 text-xs font-medium text-gray-400">Policy Documents</div>
            <div className="divide-y divide-gray-800/50">
              {policies.map((p: any) => (
                <div key={p.file} className="px-4 py-3 flex items-center justify-between">
                  <span className="text-sm text-gray-300">{p.name}</span>
                  <span className="text-xs text-gray-600">{p.lines} lines</span>
                </div>
              ))}
            </div>
          </div>

          {tickets.length > 0 && (
            <div className="bg-gray-900 border border-gray-800 rounded-xl overflow-hidden">
              <div className="px-4 py-3 border-b border-gray-800 text-xs font-medium text-gray-400">Governance Tickets</div>
              <div className="divide-y divide-gray-800/50">
                {tickets.map((t: any) => (
                  <div key={t.id} className="px-4 py-3 flex items-center justify-between">
                    <div className="flex items-center gap-2">
                      <span className={`w-2 h-2 rounded-full ${t.status === 'done' ? 'bg-emerald-400' : 'bg-amber-400'}`} />
                      <span className="text-xs text-gray-500">#{t.id}</span>
                      <span className="text-sm text-gray-300 truncate max-w-md">{t.task}</span>
                    </div>
                    <span className="text-xs text-gray-600">{t.status}</span>
                  </div>
                ))}
              </div>
            </div>
          )}
        </div>

        {dariusOpen && (
          <div className="w-[40%] bg-gray-900 border border-violet-500/20 rounded-xl flex flex-col h-[500px]">
            <div className="px-4 py-3 border-b border-gray-800 text-xs font-medium text-violet-400">✦ Darius — Governance & Compliance</div>
            <div className="flex-1 overflow-y-auto p-3 space-y-3">
              {messages.map((m, i) => (
                <div key={i} className={`text-xs leading-relaxed px-3 py-2 rounded-lg max-w-[90%] ${m.role === 'user' ? 'ml-auto bg-blue-600/20 border border-blue-500/30 text-blue-100' : 'bg-gray-800 border border-gray-700 text-gray-300'}`}>
                  {m.role === 'assistant' ? <DariusMarkdown text={m.content} /> : m.content}
                </div>
              ))}
              {loading && <div className="text-xs text-gray-500 animate-pulse px-3">Thinking...</div>}
            </div>
            <div className="p-3 border-t border-gray-800 flex gap-2">
              <input value={input} onChange={e => setInput(e.target.value)} onKeyDown={e => e.key === 'Enter' && askDarius()} placeholder="Ask about compliance..." className="flex-1 bg-gray-800 border border-gray-700 rounded-lg px-3 py-2 text-xs text-white outline-none focus:border-violet-500" />
              <button onClick={askDarius} disabled={loading} className="px-3 py-2 bg-violet-600 rounded-lg text-xs disabled:opacity-50">→</button>
            </div>
          </div>
        )}
      </div>
    </div>
  )
}

ReactDOM.createRoot(document.getElementById('root')!).render(<React.StrictMode><App /></React.StrictMode>)
