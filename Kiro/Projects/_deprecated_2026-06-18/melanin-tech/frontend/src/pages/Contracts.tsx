import React, { useState, useEffect } from 'react'
import {
  FileText, DollarSign, Clock, CheckCircle, AlertCircle, Plus,
  Send, Bot, Sparkles, TrendingUp, Calendar, Building2, X
} from 'lucide-react'

interface Contract {
  id: string
  client: string
  staffingFirm: string
  role: string
  billRate: number
  firmMargin: number
  netRate: number
  status: 'active' | 'pending' | 'completed' | 'expired'
  startDate: string
  endDate: string
  hoursPerWeek: number
  totalInvoiced: number
  totalPaid: number
  outstanding: number
}

interface DariusMessage {
  role: 'user' | 'assistant'
  content: string
  timestamp: string
}

const DARIUS_URL = 'http://darius-agent:8000'

const contracts: Contract[] = [
  { id: 'CTR-001', client: 'FinEdge Capital', staffingFirm: 'TechBridge Staffing', role: 'Senior Backend Engineer', billRate: 145, firmMargin: 20, netRate: 116, status: 'active', startDate: '2025-01-15', endDate: '2025-07-15', hoursPerWeek: 40, totalInvoiced: 46400, totalPaid: 37120, outstanding: 9280 },
  { id: 'CTR-002', client: 'NovaMed Health', staffingFirm: 'PrimeSource Solutions', role: 'Full Stack Developer', billRate: 130, firmMargin: 18, netRate: 106.60, status: 'active', startDate: '2025-02-01', endDate: '2025-08-01', hoursPerWeek: 40, totalInvoiced: 34112, totalPaid: 34112, outstanding: 0 },
  { id: 'CTR-003', client: 'Apex Logistics', staffingFirm: 'TechBridge Staffing', role: 'DevOps Engineer', billRate: 155, firmMargin: 22, netRate: 120.90, status: 'pending', startDate: '2025-06-01', endDate: '2025-12-01', hoursPerWeek: 40, totalInvoiced: 0, totalPaid: 0, outstanding: 0 },
  { id: 'CTR-004', client: 'Meridian Bank', staffingFirm: 'Insight Partners', role: 'Cloud Architect', billRate: 175, firmMargin: 25, netRate: 131.25, status: 'active', startDate: '2025-03-10', endDate: '2025-09-10', hoursPerWeek: 32, totalInvoiced: 29400, totalPaid: 25200, outstanding: 4200 },
]

export default function Contracts() {
  const [selected, setSelected] = useState<Contract | null>(null)
  const [dariusOpen, setDariusOpen] = useState(false)
  const [messages, setMessages] = useState<DariusMessage[]>([
    { role: 'assistant', content: 'I\'m Darius, your contract intelligence assistant. I can analyze your contracts, suggest rate optimizations, flag renewal deadlines, and help with invoicing strategy. What would you like to know?', timestamp: new Date().toISOString() }
  ])
  const [input, setInput] = useState('')
  const [loading, setLoading] = useState(false)

  const statusColors: Record<string, string> = {
    active: 'bg-emerald-500/20 text-emerald-400 border-emerald-500/30',
    pending: 'bg-amber-500/20 text-amber-400 border-amber-500/30',
    completed: 'bg-blue-500/20 text-blue-400 border-blue-500/30',
    expired: 'bg-red-500/20 text-red-400 border-red-500/30',
  }

  const totalMonthlyRevenue = contracts.filter(c => c.status === 'active').reduce((sum, c) => sum + (c.netRate * c.hoursPerWeek * 4.33), 0)
  const totalOutstanding = contracts.reduce((sum, c) => sum + c.outstanding, 0)
  const activeCount = contracts.filter(c => c.status === 'active').length

  async function sendToDarius() {
    if (!input.trim()) return
    const userMsg: DariusMessage = { role: 'user', content: input, timestamp: new Date().toISOString() }
    setMessages(prev => [...prev, userMsg])
    setInput('')
    setLoading(true)

    try {
      const context = `Active contracts: ${activeCount}. Monthly revenue: $${Math.round(totalMonthlyRevenue).toLocaleString()}. Outstanding: $${totalOutstanding.toLocaleString()}. Contracts: ${JSON.stringify(contracts.map(c => ({ id: c.id, client: c.client, role: c.role, netRate: c.netRate, status: c.status, endDate: c.endDate, outstanding: c.outstanding })))}`
      const res = await fetch(`${DARIUS_URL}/task`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ task: `[Contract Management Context] ${context}\n\nUser question: ${input}`, project: 'melanin-contracts', session_id: 'contracts-assistant' })
      })
      const data = await res.json()
      const reply = data?.args?.proposal || 'I couldn\'t process that request. Try again.'
      setMessages(prev => [...prev, { role: 'assistant', content: reply, timestamp: new Date().toISOString() }])
    } catch {
      setMessages(prev => [...prev, { role: 'assistant', content: 'Connection to Darius unavailable. Check that the agent is running.', timestamp: new Date().toISOString() }])
    }
    setLoading(false)
  }

  return (
    <div className="min-h-screen bg-gray-950 text-white p-6">
      {/* Header */}
      <div className="flex items-center justify-between mb-8">
        <div>
          <h1 className="text-2xl font-bold">Contracts</h1>
          <p className="text-sm text-gray-500">Staffing engagements & invoicing</p>
        </div>
        <div className="flex gap-3">
          <button onClick={() => setDariusOpen(!dariusOpen)} className="flex items-center gap-2 px-4 py-2 bg-violet-600/20 border border-violet-500/30 rounded-lg text-violet-300 hover:bg-violet-600/30 transition-colors text-sm">
            <Bot className="w-4 h-4" /> Darius AI
          </button>
          <button className="flex items-center gap-2 px-4 py-2 bg-blue-600 rounded-lg text-white hover:bg-blue-700 transition-colors text-sm">
            <Plus className="w-4 h-4" /> New Contract
          </button>
        </div>
      </div>

      {/* Stats Row */}
      <div className="grid grid-cols-1 md:grid-cols-4 gap-4 mb-8">
        <div className="bg-gray-900 border border-gray-800 rounded-xl p-5">
          <div className="flex items-center gap-2 text-gray-400 text-xs mb-2"><Building2 className="w-3.5 h-3.5" /> Active Contracts</div>
          <p className="text-2xl font-bold">{activeCount}</p>
        </div>
        <div className="bg-gray-900 border border-gray-800 rounded-xl p-5">
          <div className="flex items-center gap-2 text-gray-400 text-xs mb-2"><DollarSign className="w-3.5 h-3.5" /> Monthly Revenue</div>
          <p className="text-2xl font-bold text-emerald-400">${Math.round(totalMonthlyRevenue).toLocaleString()}</p>
        </div>
        <div className="bg-gray-900 border border-gray-800 rounded-xl p-5">
          <div className="flex items-center gap-2 text-gray-400 text-xs mb-2"><Clock className="w-3.5 h-3.5" /> Outstanding</div>
          <p className="text-2xl font-bold text-amber-400">${totalOutstanding.toLocaleString()}</p>
        </div>
        <div className="bg-gray-900 border border-gray-800 rounded-xl p-5">
          <div className="flex items-center gap-2 text-gray-400 text-xs mb-2"><TrendingUp className="w-3.5 h-3.5" /> Avg Net Rate</div>
          <p className="text-2xl font-bold">${(contracts.filter(c => c.status === 'active').reduce((s, c) => s + c.netRate, 0) / activeCount).toFixed(0)}/hr</p>
        </div>
      </div>

      <div className="flex gap-6">
        {/* Contract List */}
        <div className={`flex-1 ${dariusOpen ? 'max-w-[60%]' : ''}`}>
          <div className="bg-gray-900 border border-gray-800 rounded-xl overflow-hidden">
            <div className="px-5 py-4 border-b border-gray-800 flex items-center justify-between">
              <h2 className="font-semibold text-sm">All Contracts</h2>
              <span className="text-xs text-gray-500">{contracts.length} total</span>
            </div>
            <div className="divide-y divide-gray-800">
              {contracts.map(c => (
                <div key={c.id} onClick={() => setSelected(selected?.id === c.id ? null : c)} className={`px-5 py-4 cursor-pointer hover:bg-gray-800/50 transition-colors ${selected?.id === c.id ? 'bg-gray-800/70' : ''}`}>
                  <div className="flex items-center justify-between mb-2">
                    <div className="flex items-center gap-3">
                      <span className="text-xs text-gray-500 font-mono">{c.id}</span>
                      <span className="font-medium text-sm">{c.role}</span>
                    </div>
                    <span className={`text-xs px-2 py-0.5 rounded-full border ${statusColors[c.status]}`}>{c.status}</span>
                  </div>
                  <div className="flex items-center justify-between">
                    <div className="flex items-center gap-4 text-xs text-gray-400">
                      <span>{c.client}</span>
                      <span>via {c.staffingFirm}</span>
                    </div>
                    <span className="text-sm font-semibold text-emerald-400">${c.netRate}/hr</span>
                  </div>
                  {selected?.id === c.id && (
                    <div className="mt-4 pt-4 border-t border-gray-700 grid grid-cols-2 md:grid-cols-4 gap-4 text-xs">
                      <div><span className="text-gray-500 block">Bill Rate</span><span className="font-medium">${c.billRate}/hr</span></div>
                      <div><span className="text-gray-500 block">Firm Margin</span><span className="font-medium text-amber-400">{c.firmMargin}%</span></div>
                      <div><span className="text-gray-500 block">Hours/Week</span><span className="font-medium">{c.hoursPerWeek}</span></div>
                      <div><span className="text-gray-500 block">End Date</span><span className="font-medium">{c.endDate}</span></div>
                      <div><span className="text-gray-500 block">Total Invoiced</span><span className="font-medium">${c.totalInvoiced.toLocaleString()}</span></div>
                      <div><span className="text-gray-500 block">Total Paid</span><span className="font-medium text-emerald-400">${c.totalPaid.toLocaleString()}</span></div>
                      <div><span className="text-gray-500 block">Outstanding</span><span className={`font-medium ${c.outstanding > 0 ? 'text-amber-400' : 'text-gray-400'}`}>${c.outstanding.toLocaleString()}</span></div>
                      <div><span className="text-gray-500 block">Monthly Net</span><span className="font-medium">${Math.round(c.netRate * c.hoursPerWeek * 4.33).toLocaleString()}</span></div>
                    </div>
                  )}
                </div>
              ))}
            </div>
          </div>
        </div>

        {/* Darius AI Panel */}
        {dariusOpen && (
          <div className="w-[40%] bg-gray-900 border border-violet-500/20 rounded-xl flex flex-col h-[calc(100vh-220px)]">
            <div className="px-5 py-4 border-b border-gray-800 flex items-center justify-between">
              <div className="flex items-center gap-2">
                <Sparkles className="w-4 h-4 text-violet-400" />
                <h2 className="font-semibold text-sm">Darius — Contract Intelligence</h2>
              </div>
              <button onClick={() => setDariusOpen(false)} className="text-gray-500 hover:text-white"><X className="w-4 h-4" /></button>
            </div>

            <div className="flex-1 overflow-y-auto p-4 space-y-4">
              {messages.map((msg, i) => (
                <div key={i} className={`flex ${msg.role === 'user' ? 'justify-end' : 'justify-start'}`}>
                  <div className={`max-w-[85%] px-4 py-3 rounded-xl text-sm leading-relaxed ${msg.role === 'user' ? 'bg-blue-600/20 border border-blue-500/30 text-blue-100' : 'bg-gray-800 border border-gray-700 text-gray-200'}`}>
                    {msg.content}
                  </div>
                </div>
              ))}
              {loading && (
                <div className="flex justify-start">
                  <div className="bg-gray-800 border border-gray-700 rounded-xl px-4 py-3 text-sm text-gray-400">
                    <span className="animate-pulse">Darius is thinking...</span>
                  </div>
                </div>
              )}
            </div>

            <div className="p-4 border-t border-gray-800">
              <div className="flex gap-2">
                <input
                  value={input}
                  onChange={e => setInput(e.target.value)}
                  onKeyDown={e => e.key === 'Enter' && sendToDarius()}
                  placeholder="Ask about rates, renewals, invoicing..."
                  className="flex-1 bg-gray-800 border border-gray-700 rounded-lg px-4 py-2.5 text-sm text-white placeholder-gray-500 focus:outline-none focus:border-violet-500"
                />
                <button onClick={sendToDarius} disabled={loading} className="px-4 py-2.5 bg-violet-600 rounded-lg hover:bg-violet-700 transition-colors disabled:opacity-50">
                  <Send className="w-4 h-4" />
                </button>
              </div>
              <div className="flex gap-2 mt-2">
                {['Rate optimization', 'Upcoming renewals', 'Invoice summary'].map(q => (
                  <button key={q} onClick={() => { setInput(q); }} className="text-xs px-2.5 py-1 bg-gray-800 border border-gray-700 rounded-lg text-gray-400 hover:text-white hover:border-gray-600 transition-colors">
                    {q}
                  </button>
                ))}
              </div>
            </div>
          </div>
        )}
      </div>
    </div>
  )
}
