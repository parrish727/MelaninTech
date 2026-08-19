import React, { useState, useEffect } from 'react'
import { 
  Building2, 
  FileText, 
  DollarSign, 
  Users, 
  TrendingUp, 
  Clock, 
  CheckCircle, 
  AlertCircle,
  Plus,
  ChevronRight,
  Briefcase,
  ArrowUpRight,
  BarChart3,
  Sparkles
} from 'lucide-react'
import { Link } from 'react-router-dom'

function useDariusInsight() {
  const [insight, setInsight] = useState<string | null>(null)
  useEffect(() => {
    fetch('http://darius-agent:8000/task', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        task: 'Provide a single brief actionable insight (1-2 sentences) about contract management for a tech consulting firm with 4 active staffing contracts generating ~$38K/month. Focus on rate optimization, renewal timing, or cash flow.',
        project: 'melanin-contracts',
        session_id: 'dashboard-insight'
      })
    })
      .then(r => r.json())
      .then(d => setInsight(d?.args?.proposal || null))
      .catch(() => null)
  }, [])
  return insight
}

const stats = [
  {
    label: 'Active Contracts',
    value: '4',
    change: '+2 this quarter',
    icon: Briefcase,
    color: 'bg-violet-600',
    light: 'bg-violet-50',
    text: 'text-violet-600'
  },
  {
    label: 'Monthly Revenue',
    value: '$38,400',
    change: '+12% vs last month',
    icon: DollarSign,
    color: 'bg-emerald-600',
    light: 'bg-emerald-50',
    text: 'text-emerald-600'
  },
  {
    label: 'Outstanding Invoices',
    value: '$14,200',
    change: '3 pending',
    icon: FileText,
    color: 'bg-amber-500',
    light: 'bg-amber-50',
    text: 'text-amber-600'
  },
  {
    label: 'YTD Earnings',
    value: '$186,500',
    change: 'On track for $220K',
    icon: TrendingUp,
    color: 'bg-sky-600',
    light: 'bg-sky-50',
    text: 'text-sky-600'
  }
]

const recentContracts = [
  {
    id: 'CTR-001',
    client: 'FinEdge Capital',
    staffingFirm: 'TechBridge Staffing',
    role: 'Senior Backend Engineer',
    rate: 145,
    firmMargin: 20,
    ourRate: 116,
    status: 'active',
    startDate: 'Jan 15, 2025',
    endDate: 'Jul 15, 2025',
    hoursPerWeek: 40
  },
  {
    id: 'CTR-002',
    client: 'NovaMed Health',
    staffingFirm: 'PrimeSource Solutions',
    role: 'Full Stack Developer',
    rate: 130,
    firmMargin: 18,
    ourRate: 106.60,
    status: 'active',
    startDate: 'Feb 1, 2025',
    endDate: 'Aug 1, 2025',
    hoursPerWeek: 40
  },
  {
    id: 'CTR-003',
    client: 'Apex Logistics',
    staffingFirm: 'TechBridge Staffing',
    role: 'DevOps Engineer',
    rate: 155,
    firmMargin: 22,
    ourRate: 120.90,
    status: 'pending',
    startDate: 'Mar 1, 2025',
    endDate: 'Sep 1, 2025',
    hoursPerWeek: 32
  },
  {
    id: 'CTR-004',
    client: 'Stellar Retail Group',
    staffingFirm: 'ClearPath Talent',
    role: 'Data Engineer',
    rate: 140,
    firmMargin: 15,
    ourRate: 119,
    status: 'completed',
    startDate: 'Oct 1, 2024',
    endDate: 'Jan 31, 2025',
    hoursPerWeek: 40
  }
]

const recentInvoices = [
  { id: 'INV-2025-012', contract: 'CTR-001', period: 'Feb 17–21', amount: 4640, status: 'paid', dueDate: 'Mar 7, 2025' },
  { id: 'INV-2025-011', contract: 'CTR-002', period: 'Feb 17–21', amount: 4264, status: 'sent', dueDate: 'Mar 7, 2025' },
  { id: 'INV-2025-010', contract: 'CTR-001', period: 'Feb 10–14', amount: 4640, status: 'paid', dueDate: 'Feb 28, 2025' },
  { id: 'INV-2025-009', contract: 'CTR-003', period: 'Feb 10–14', amount: 3869, status: 'overdue', dueDate: 'Feb 28, 2025' }
]

const statusBadge = (status: string) => {
  const map: Record<string, string> = {
    active: 'bg-emerald-100 text-emerald-700',
    pending: 'bg-amber-100 text-amber-700',
    completed: 'bg-slate-100 text-slate-600',
    paid: 'bg-emerald-100 text-emerald-700',
    sent: 'bg-blue-100 text-blue-700',
    overdue: 'bg-red-100 text-red-700',
    draft: 'bg-slate-100 text-slate-600'
  }
  return map[status] || 'bg-slate-100 text-slate-600'
}

export default function ContractDashboard() {
  const dariusInsight = useDariusInsight()
  return (
    <div className="min-h-screen bg-slate-50">
      {/* Darius AI Insight Banner */}
      {dariusInsight && (
        <div className="bg-gradient-to-r from-violet-600 to-indigo-600 px-4 py-2.5">
          <div className="max-w-7xl mx-auto flex items-center gap-2 text-white text-sm">
            <Sparkles className="w-4 h-4 flex-shrink-0" />
            <span className="font-medium">Darius:</span>
            <span className="opacity-90 truncate">{dariusInsight}</span>
            <Link to="/contracts" className="ml-auto text-xs bg-white/20 px-2.5 py-1 rounded-md hover:bg-white/30 flex-shrink-0">Details</Link>
          </div>
        </div>
      )}
      {/* Header */}
      <header className="bg-white border-b border-slate-200 sticky top-0 z-30">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
          <div className="flex items-center justify-between h-16">
            <div className="flex items-center gap-3">
              <div className="w-8 h-8 rounded-lg bg-gradient-to-br from-violet-600 to-indigo-700 flex items-center justify-center">
                <span className="text-white font-bold text-sm">MT</span>
              </div>
              <div>
                <p className="font-bold text-slate-900 text-sm leading-none">Melanin Technologies Inc.</p>
                <p className="text-xs text-slate-500 leading-none mt-0.5">Contract Management</p>
              </div>
            </div>
            <nav className="hidden md:flex items-center gap-1">
              {['Dashboard', 'Contracts', 'Invoices', 'Clients', 'Reports'].map((item) => (
                <Link
                  key={item}
                  to={`/${item.toLowerCase()}`}
                  className={`px-3 py-1.5 rounded-md text-sm font-medium transition-colors ${
                    item === 'Dashboard' 
                      ? 'bg-violet-50 text-violet-700' 
                      : 'text-slate-600 hover:bg-slate-100 hover:text-slate-900'
                  }`}
                >
                  {item}
                </Link>
              ))}
            </nav>
            <div className="flex items-center gap-2">
              <button className="hidden sm:flex items-center gap-2 bg-violet-600 text-white px-3 py-1.5 rounded-lg text-sm font-medium hover:bg-violet-700 transition-colors">
                <Plus className="w-4 h-4" />
                New Contract
              </button>
              <div className="w-8 h-8 rounded-full bg-gradient-to-br from-violet-500 to-indigo-600 flex items-center justify-center text-white text-xs font-bold">
                MT
              </div>
            </div>
          </div>
        </div>
      </header>

      <main className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
        {/* Page Title */}
        <div className="mb-8">
          <h1 className="text-2xl font-bold text-slate-900">Dashboard Overview</h1>
          <p className="text-slate-500 mt-1">Track contracts, invoices, and revenue across all staffing engagements.</p>
        </div>

        {/* Stats */}
        <div className="grid grid-cols-2 lg:grid-cols-4 gap-4 mb-8">
          {stats.map((s) => (
            <div key={s.label} className="bg-white rounded-xl border border-slate-200 p-4 hover:shadow-md transition-shadow">
              <div className="flex items-start justify-between mb-3">
                <div className={`w-9 h-9 rounded-lg ${s.light} flex items-center justify-center`}>
                  <s.icon className={`w-5 h-5 ${s.text}`} />
                </div>
                <ArrowUpRight className="w-4 h-4 text-slate-400" />
              </div>
              <p className="text-2xl font-bold text-slate-900">{s.value}</p>
              <p className="text-xs text-slate-500 mt-0.5">{s.label}</p>
              <p className={`text-xs font-medium mt-1 ${s.text}`}>{s.change}</p>
            </div>
          ))}
        </div>

        {/* Flow Diagram */}
        <div className="bg-gradient-to-r from-violet-600 to-indigo-700 rounded-2xl p-6 mb-8 text-white">
          <div className="flex items-center justify-between mb-4">
            <h2 className="font-semibold text-lg">Revenue Flow Structure</h2>
            <span className="text-violet-200 text-sm">B2B Corp-to-Corp Model</span>
          </div>
          <div className="flex flex-col sm:flex-row items-center justify-between gap-4">
            <FlowNode icon={Building2} label="End Client" sub="Pays full rate" color="bg-white/20" />
            <FlowArrow label="Invoices client" />
            <FlowNode icon={Users} label="Staffing Firm" sub="Takes 15–25% margin" color="bg-white/20" />
            <FlowArrow label="Engages Melanin Tech" />
            <FlowNode icon={Briefcase} label="Melanin Technologies" sub="Invoices staffing firm" color="bg-violet-500/50" highlight />
            <FlowArrow label="Delivers work" />
            <FlowNode icon={CheckCircle} label="Consultant" sub="1099 / W-2 via MTI" color="bg-white/20" />
          </div>
        </div>

        <div className="grid lg:grid-cols-5 gap-6 mb-6">
          {/* Contracts */}
          <div className="lg:col-span-3 bg-white rounded-xl border border-slate-200">
            <div className="flex items-center justify-between p-5 border-b border-slate-100">
              <h2 className="font-semibold text-slate-900">Active Contracts</h2>
              <Link to="/contracts" className="text-violet-600 text-sm font-medium flex items-center gap-1 hover:gap-2 transition-all">
                View all <ChevronRight className="w-4 h-4" />
              </Link>
            </div>
            <div className="divide-y divide-slate-100">
              {recentContracts.slice(0, 3).map((c) => (
                <div key={c.id} className="p-4 hover:bg-slate-50 transition-colors">
                  <div className="flex items-start justify-between gap-2">
                    <div className="flex-1 min-w-0">
                      <div className="flex items-center gap-2 flex-wrap">
                        <span className="font-medium text-slate-900 text-sm">{c.client}</span>
                        <span className={`text-xs px-2 py-0.5 rounded-full font-medium ${statusBadge(c.status)}`}>
                          {c.status}
                        </span>
                      </div>
                      <p className="text-xs text-slate-500 mt-0.5">via {c.staffingFirm} · {c.role}</p>
                      <div className="flex items-center gap-3 mt-2">
                        <span className="text-xs text-slate-500 flex items-center gap-1">
                          <Clock className="w-3 h-3" /> {c.hoursPerWeek}h/wk
                        </span>
                        <span className="text-xs text-slate-500">{c.startDate} → {c.endDate}</span>
                      </div>
                    </div>
                    <div className="text-right shrink-0">
                      <p className="text-sm font-bold text-slate-900">${c.ourRate.toFixed(0)}<span className="font-normal text-slate-400">/hr</span></p>
                      <p className="text-xs text-slate-500">Client pays ${c.rate}/hr</p>
                      <p className="text-xs text-amber-600 font-medium">{c.firmMargin}% margin</p>
                    </div>
                  </div>
                </div>
              ))}
            </div>
          </div>

          {/* Rate Breakdown */}
          <div className="lg:col-span-2 bg-white rounded-xl border border-slate-200">
            <div className="p-5 border-b border-slate-100">
              <h2 className="font-semibold text-slate-900">Rate Breakdown</h2>
              <p className="text-xs text-slate-500 mt-0.5">CTR-001 · FinEdge Capital</p>
            </div>
            <div className="p-5 space-y-4">
              <RateBar label="End Client Rate" amount={145} max={145} color="bg-violet-600" percent={100} />
              <RateBar label="Staffing Firm (20%)" amount={29} max={145} color="bg-amber-400" percent={20} subtract />
              <RateBar label="MTI Net Rate" amount={116} max={145} color="bg-emerald-500" percent={80} />
              
              <div className="border-t border-slate-100 pt-4 space-y-2">
                <div className="flex justify-between text-sm">
                  <span className="text-slate-500">Weekly (40h)</span>
                  <span className="font-semibold text-slate-900">$4,640</span>
                </div>
                <div className="flex justify-between text-sm">
                  <span className="text-slate-500">Monthly (~4.33 wks)</span>
                  <span className="font-semibold text-slate-900">$20,090</span>
                </div>
                <div className="flex justify-between text-sm">
                  <span className="text-slate-500">Contract Total (6 mo)</span>
                  <span className="font-bold text-emerald-600">$120,540</span>
                </div>
              </div>
            </div>
          </div>
        </div>

        {/* Recent Invoices */}
        <div className="bg-white rounded-xl border border-slate-200">
          <div className="flex items-center justify-between p-5 border-b border-slate-100">
            <h2 className="font-semibold text-slate-900">Recent Invoices</h2>
            <div className="flex items-center gap-3">
              <Link to="/invoices" className="text-violet-600 text-sm font-medium flex items-center gap-1 hover:gap-2 transition-all">
                View all <ChevronRight className="w-4 h-4" />
              </Link>
              <button className="flex items-center gap-1.5 bg-violet-600 text-white px-3 py-1.5 rounded-lg text-sm font-medium hover:bg-violet-700 transition-colors">
                <Plus className="w-3.5 h-3.5" /> New Invoice
              </button>
            </div>
          </div>
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b border-slate-100 bg-slate-50">
                  <th className="text-left px-5 py-3 text-xs font-medium text-slate-500 uppercase tracking-wider">Invoice</th>
                  <th className="text-left px-5 py-3 text-xs font-medium text-slate-500 uppercase tracking-wider">Contract</th>
                  <th className="text-left px-5 py-3 text-xs font-medium text-slate-500 uppercase tracking-wider hidden sm:table-cell">Period</th>
                  <th className="text-left px-5 py-3 text-xs font-medium text-slate-500 uppercase tracking-wider hidden md:table-cell">Due Date</th>
                  <th className="text-right px-5 py-3 text-xs font-medium text-slate-500 uppercase tracking-wider">Amount</th>
                  <th className="text-left px-5 py-3 text-xs font-medium text-slate-500 uppercase tracking-wider">Status</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-100">
                {recentInvoices.map((inv) => (
                  <tr key={inv.id} className="hover:bg-slate-50 transition-colors">
                    <td className="px-5 py-3.5 font-medium text-violet-700">{inv.id}</td>
                    <td className="px-5 py-3.5 text-slate-600">{inv.contract}</td>
                    <td className="px-5 py-3.5 text-slate-500 hidden sm:table-cell">{inv.period}</td>
                    <td className="px-5 py-3.5 text-slate-500 hidden md:table-cell">{inv.dueDate}</td>
                    <td className="px-5 py-3.5 text-right font-semibold text-slate-900">${inv.amount.toLocaleString()}</td>
                    <td className="px-5 py-3.5">
                      <span className={`text-xs px-2.5 py-1 rounded-full font-medium ${statusBadge(inv.status)}`}>
                        {inv.status}
                      </span>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      </main>
    </div>
  )
}

function FlowNode({ icon: Icon, label, sub, color, highlight }: {
  icon: React.ElementType
  label: string
  sub: string
  color: string
  highlight?: boolean
}) {
  return (
    <div className={`flex flex-col items-center text-center px-4 py-3 rounded-xl ${color} ${highlight ? 'ring-2 ring-white/40' : ''}`}>
      <Icon className="w-6 h-6 mb-1.5" />
      <span className="font-semibold text-sm">{label}</span>
      <span className="text-xs text-violet-200 mt-0.5">{sub}</span>
    </div>
  )
}

function FlowArrow({ label }: { label: string }) {
  return (
    <div className="flex flex-col items-center gap-1 text-violet-200">
      <span className="text-xs hidden sm:block">{label}</span>
      <ChevronRight className="w-5 h-5 rotate-90 sm:rotate-0" />
    </div>
  )
}

function RateBar({ label, amount, max, color, percent, subtract }: {
  label: string
  amount: number
  max: number
  color: string
  percent: number
  subtract?: boolean
}) {
  return (
    <div>
      <div className="flex justify-between items-center mb-1">
        <span className="text-xs text-slate-600">{label}</span>
        <span className={`text-xs font-semibold ${subtract ? 'text-amber-600' : 'text-slate-900'}`}>
          {subtract ? '-' : ''}${amount}/hr
        </span>
      </div>
      <div className="h-2 bg-slate-100 rounded-full overflow-hidden">
        <div
          className={`h-full ${color} rounded-full transition-all`}
          style={{ width: `${percent}%` }}
        />
      </div>
    </div>
  )
}