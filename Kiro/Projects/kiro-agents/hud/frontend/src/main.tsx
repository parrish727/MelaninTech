import React, { useState, useEffect } from 'react'
import ReactDOM from 'react-dom/client'
import './index.css'

const API = ''  // Same origin — proxied through nginx to backend

function App() {
  const [token, setToken] = useState(localStorage.getItem('hud_token') || '')
  const [tab, setTab] = useState<'dashboard' | 'agents' | 'infra' | 'darius' | 'projects' | 'tickets' | 'memory' | 'security' | 'clients'>('dashboard')
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
    const [d, a, i, dar, proj, tix, mem, sec, cli] = await Promise.all([
      fetch(`${API}/api/dashboard`, { headers: h }).then(r => r.json()),
      fetch(`${API}/api/agents`, { headers: h }).then(r => r.json()),
      fetch(`${API}/api/infrastructure`, { headers: h }).then(r => r.json()),
      fetch(`${API}/api/darius`, { headers: h }).then(r => r.json()).catch(() => ({})),
      fetch(`${API}/api/projects`, { headers: h }).then(r => r.json()).catch(() => ({})),
      fetch(`${API}/api/tickets`, { headers: h }).then(r => r.json()).catch(() => ({})),
      fetch(`${API}/api/memory`, { headers: h }).then(r => r.json()).catch(() => ({})),
      fetch(`${API}/api/security`, { headers: h }).then(r => r.json()).catch(() => ({})),
      fetch(`${API}/api/clients`, { headers: h }).then(r => r.json()).catch(() => ({})),
    ])
    setData(d); setAgents(a.agents || []); setInfra(i.services || [])
    setExtra({ darius: dar, projects: proj, tickets: tix, memory: mem, security: sec, clients: cli })
  }

  useEffect(() => { if (token) { load(); const i = setInterval(load, 30000); return () => clearInterval(i) } }, [token])

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
            {([['dashboard','Executive'],['agents','Agents'],['infra','Infrastructure'],['darius','Darius'],['projects','Projects'],['tickets','Tickets'],['memory','Memory'],['security','Security'],['clients','Clients']] as const).map(([t, label]) => (
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
      </main>
    </div>
  )
}

function Dashboard({ data }: { data: any }) {
  return (
    <div>
      <h2 className="text-lg font-semibold mb-4">Executive Dashboard</h2>
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-4 mb-6">
        <Stat label="Containers Running" value={data.containers_running} color="text-cyan-400" />
        <Stat label="Memory Entries" value={data.memory_entries} color="text-violet-400" />
        <Stat label="Tickets Done" value={data.tickets?.done || 0} color="text-emerald-400" />
        <Stat label="Tickets Open" value={(data.tickets?.open || 0) + (data.tickets?.in_progress || 0)} color="text-amber-400" />
      </div>
      <div className="bg-gray-900 border border-gray-800 rounded-xl p-4">
        <h3 className="text-sm font-medium text-gray-400 mb-3">Recent Tickets</h3>
        <div className="space-y-2">
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
      </div>
    </div>
  )
}

function Agents({ agents }: { agents: any[] }) {
  return (
    <div>
      <h2 className="text-lg font-semibold mb-4">Agent Status</h2>
      <div className="grid gap-3">
        {agents.map(a => (
          <div key={a.name} className="bg-gray-900 border border-gray-800 rounded-xl p-4 flex items-center justify-between">
            <div className="flex items-center gap-3">
              <span className={`w-2.5 h-2.5 rounded-full ${a.status === 'running' ? 'bg-emerald-400' : 'bg-red-400'}`} />
              <span className="text-sm font-medium text-white">{a.name}</span>
            </div>
            <div className="flex items-center gap-4">
              <span className="text-xs text-gray-500">{a.status}</span>
              {a.uptime && <span className="text-xs text-gray-600">Since {new Date(a.uptime).toLocaleDateString()}</span>}
            </div>
          </div>
        ))}
      </div>
    </div>
  )
}

function Infrastructure({ services }: { services: any[] }) {
  return (
    <div>
      <h2 className="text-lg font-semibold mb-4">Infrastructure</h2>
      <div className="bg-gray-900 border border-gray-800 rounded-xl overflow-hidden">
        <table className="w-full text-sm">
          <thead><tr className="border-b border-gray-800">
            <th className="px-4 py-2 text-left text-xs text-gray-500">Container</th>
            <th className="px-4 py-2 text-left text-xs text-gray-500">Status</th>
            <th className="px-4 py-2 text-left text-xs text-gray-500">Started</th>
          </tr></thead>
          <tbody>
            {services.map(s => (
              <tr key={s.name} className="border-b border-gray-800/50">
                <td className="px-4 py-2 text-gray-300">{s.name}</td>
                <td className="px-4 py-2"><span className={`text-xs ${s.status === 'running' ? 'text-emerald-400' : 'text-red-400'}`}>{s.status}</span></td>
                <td className="px-4 py-2 text-xs text-gray-600">{s.started ? new Date(s.started).toLocaleString() : '—'}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
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
  return (
    <div>
      <h2 className="text-lg font-semibold mb-2">Tickets</h2>
      <div className="flex gap-3 mb-4">
        {Object.entries(data?.summary || {}).map(([k, v]) => (
          <span key={k} className="text-xs bg-gray-800 px-3 py-1 rounded-full text-gray-300">{k}: {v as number}</span>
        ))}
      </div>
      <div className="bg-gray-900 border border-gray-800 rounded-xl p-4 space-y-2">
        {(data?.tickets || []).map((t: any) => (
          <div key={t.id} className="flex items-center justify-between text-sm">
            <div className="flex items-center gap-2">
              <span className={`w-2 h-2 rounded-full ${t.status === 'done' ? 'bg-emerald-400' : t.status === 'cancelled' ? 'bg-gray-600' : 'bg-amber-400'}`} />
              <span className="text-gray-400">#{t.id}</span>
              <span className="text-gray-300 truncate max-w-lg">{t.task}</span>
            </div>
            <span className="text-xs text-gray-600">{t.agent}</span>
          </div>
        ))}
      </div>
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

ReactDOM.createRoot(document.getElementById('root')!).render(<React.StrictMode><App /></React.StrictMode>)
