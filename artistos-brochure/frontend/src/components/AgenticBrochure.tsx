import { useState, useRef, useEffect } from "react";
import { motion, AnimatePresence } from "framer-motion";
import {
  Music, Radio, PieChart, BarChart3, Users, Bot, Globe, Shield,
  Send, X, CheckCircle2, Zap, ArrowRight, Play, FileText, MapPin, Lock,
} from "lucide-react";

// ─── Data ────────────────────────────────────────────────────────────────────

const STATS = [
  { num: "6", label: "Tools replaced" },
  { num: "85%", label: "Revenue kept" },
  { num: "$48K", label: "Avg artist year" },
  { num: "30s", label: "Website built" },
];

const PILLARS = [
  { icon: Music, title: "Distribution", desc: "Get your music everywhere — Spotify, Apple, YouTube, TikTok, Amazon. Unlimited releases, label-grade loudness normalization, ISRC auto-generation." },
  { icon: Shield, title: "Rights & Contracts", desc: "Split sheets captured at upload. AI analyzes any deal you're offered — plain-language red flags, not legalese. Never sign blind again." },
  { icon: Radio, title: "Sync Licensing", desc: "Get your music into games, film, TV, and ads. AI matches your catalog to open briefs. Residual tracking so you get paid every time it re-airs." },
  { icon: Users, title: "Community", desc: "Build and monetize your fanbase directly. Subscription tiers, exclusive content, no middleman. Your audience, owned by you." },
  { icon: BarChart3, title: "Analytics", desc: "Real-time streams, audience geography, chart predictions, release timing recommendations. The same intelligence a major label's data team produces." },
  { icon: Bot, title: "AI Agents", desc: "Six AI agents working for you 24/7 — A&R, Label Manager, Sync Scout, Community Manager, Venue Scout, and Contract Analyzer. The staff of a label, for one artist." },
];

const AGENTS = [
  { name: "Label Manager", job: "Release strategy, playlist pitching, chart prediction" },
  { name: "A&R", job: "Collaborator suggestions, growth strategy, sound direction" },
  { name: "Sync Scout", job: "Matches your catalog to game/film/TV briefs" },
  { name: "Contract Analyzer", job: "Plain-language red-flag analysis on any deal" },
  { name: "Community Manager", job: "Content ideas, posting strategy, fan engagement" },
  { name: "Venue Scout", job: "Booking opportunities by geo and genre" },
];

const PRICING = [
  {
    name: "Entry",
    price: "$9.99",
    period: "/mo",
    badge: "60-DAY PRO TRIAL",
    features: ["Unlimited releases to all DSPs", "Split sheet generator", "Basic analytics", "Community profile", "1 AI agent per month", "60 days of Pro or Label features included"],
    cta: "Start Free Trial",
  },
  {
    name: "Pro",
    price: "$29.99",
    period: "/mo",
    badge: "MOST POPULAR",
    popular: true,
    features: ["Everything in Entry +", "Sync marketplace access", "All 6 AI agents (unlimited)", "AI Contract Analyzer", "Artist website builder", "Advanced real-time analytics", "Merch storefront"],
    cta: "Get Pro",
  },
  {
    name: "Label",
    price: "$49.99",
    period: "/mo",
    badge: "FOR SERIOUS ARTISTS",
    features: ["Everything in Pro +", "Up to 5 artist profiles", "Auto sync-submit to all briefs", "Residual tracking dashboard", "White-label website", "Game-ready stem exports", "Priority AI processing"],
    cta: "Go Label",
  },
];

const QUICK_REPLIES = [
  "How is this different from DistroKid?",
  "What does the AI actually do?",
  "How does sync licensing work?",
  "What's the pricing?",
  "Can I try it today?",
];

interface ChatMessage { role: "user" | "assistant"; content: string; }

// ─── Component ───────────────────────────────────────────────────────────────

export function AgenticBrochure() {
  const [chatOpen, setChatOpen] = useState(false);
  const [messages, setMessages] = useState<ChatMessage[]>([
    { role: "assistant", content: "Hey — I'm the Calistro Creative AI. Ask me anything about the platform, pricing, sync licensing, or how we're different from what you're using now." },
  ]);
  const [input, setInput] = useState("");
  const [isTyping, setIsTyping] = useState(false);
  const chatEndRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    chatEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages]);

  const sendMessage = async (text: string) => {
    if (!text.trim()) return;
    const userMsg = text.trim();
    setInput("");
    setMessages((prev) => [...prev, { role: "user", content: userMsg }]);
    setIsTyping(true);

    try {
      const res = await fetch("/api/chat", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ message: userMsg }),
      });
      const data = await res.json();
      setMessages((prev) => [...prev, { role: "assistant", content: data.reply }]);
    } catch {
      setMessages((prev) => [...prev, { role: "assistant", content: "I'm having trouble connecting right now. Check back shortly or email us at hello@calistrocreative.com" }]);
    } finally {
      setIsTyping(false);
    }
  };

  return (
    <div className="relative">
      {/* ── HERO ── */}
      <section className="relative min-h-screen overflow-hidden px-6 pt-20 pb-32">
        {/* Waveform background */}
        <div className="absolute inset-0 flex items-end opacity-20">
          <div className="flex h-64 w-full items-end gap-[2px] px-12">
            {Array.from({ length: 80 }, (_, i) => {
              const h = 20 + Math.sin(i * 0.15) * 50 + Math.cos(i * 0.3) * 30;
              return <div key={i} className="flex-1 rounded-t bg-amber" style={{ height: `${h}%` }} />;
            })}
          </div>
        </div>

        <div className="relative mx-auto max-w-5xl">
          <motion.div initial={{ opacity: 0, y: 30 }} animate={{ opacity: 1, y: 0 }} transition={{ duration: 0.8 }}>
            <p className="eyebrow text-amber">THE OPERATING SYSTEM FOR INDEPENDENT MUSIC</p>
            <h1 className="display mt-6 text-5xl leading-[1.05] text-paper sm:text-7xl">
              One platform.<br />Six pillars.<br />Your music career,<br />owned by you.
            </h1>
            <p className="mt-8 max-w-2xl text-lg text-ink-muted">
              ArtistOS replaces DistroKid + Patreon + Linktree + a lawyer + a sync agent + a label's entire staff — for $9.99/mo. You keep 85–90% of everything you earn.
            </p>
            <div className="mt-10 flex flex-wrap gap-4">
              <a href="#pricing" className="inline-flex items-center gap-2 rounded-lg bg-amber px-6 py-3 text-sm font-bold text-ink transition hover:bg-amber/90">
                <Play className="h-4 w-4" /> Start Your 60-Day Trial
              </a>
              <button onClick={() => setChatOpen(true)} className="inline-flex items-center gap-2 rounded-lg border border-hair-dark px-6 py-3 text-sm font-medium text-paper transition hover:border-ink-muted">
                <Bot className="h-4 w-4 text-amber" /> Ask the AI
              </button>
            </div>
          </motion.div>

          {/* Stats bar */}
          <motion.div initial={{ opacity: 0 }} animate={{ opacity: 1 }} transition={{ delay: 0.5 }} className="mt-20 grid grid-cols-2 gap-6 sm:grid-cols-4">
            {STATS.map((s) => (
              <div key={s.label} className="rounded-lg border border-hair-dark p-5 text-center">
                <p className="display text-2xl text-amber">{s.num}</p>
                <p className="mt-1 text-xs text-ink-muted">{s.label}</p>
              </div>
            ))}
          </motion.div>
        </div>
      </section>

      {/* ── PILLARS ── */}
      <section className="bg-paper/5 px-6 py-24">
        <div className="mx-auto max-w-5xl">
          <p className="eyebrow text-amber">WHAT'S INSIDE</p>
          <h2 className="display mt-4 text-3xl text-paper sm:text-4xl">Six Pillars. One Platform.</h2>
          <p className="mt-4 max-w-2xl text-ink-muted">Every tool a label's staff uses — distribution, rights, sync, community, analytics, and AI management — collapsed into one system you control.</p>

          <div className="mt-12 grid gap-6 sm:grid-cols-2 lg:grid-cols-3">
            {PILLARS.map((p, i) => (
              <motion.div key={p.title} initial={{ opacity: 0, y: 20 }} whileInView={{ opacity: 1, y: 0 }} viewport={{ once: true }} transition={{ delay: i * 0.1 }} className="rounded-lg border border-hair-dark p-6 transition hover:border-amber/50">
                <p.icon className="h-6 w-6 text-amber" />
                <h3 className="mt-4 font-medium text-paper">{p.title}</h3>
                <p className="mt-2 text-sm leading-relaxed text-ink-muted">{p.desc}</p>
              </motion.div>
            ))}
          </div>
        </div>
      </section>

      {/* ── AI AGENTS ── */}
      <section className="px-6 py-24">
        <div className="mx-auto max-w-5xl">
          <p className="eyebrow text-amber">YOUR AI LABEL TEAM</p>
          <h2 className="display mt-4 text-3xl text-paper">The Staff of a Label. Working for One Artist.</h2>
          <p className="mt-4 max-w-2xl text-ink-muted">Six AI agents, always on, trained on the music industry. They handle what a manager, A&R rep, licensing coordinator, and booking agent would — at a fraction of the cost.</p>

          <div className="mt-12 space-y-3">
            {AGENTS.map((a, i) => (
              <motion.div key={a.name} initial={{ opacity: 0, x: -20 }} whileInView={{ opacity: 1, x: 0 }} viewport={{ once: true }} transition={{ delay: i * 0.08 }} className="flex items-center gap-4 rounded-lg border border-hair-dark px-5 py-4 transition hover:border-amber/40">
                <Bot className="h-5 w-5 flex-shrink-0 text-amber" />
                <div className="flex-1">
                  <p className="text-sm font-medium text-paper">{a.name}</p>
                  <p className="text-xs text-ink-muted">{a.job}</p>
                </div>
                <ArrowRight className="h-4 w-4 text-ink-muted" />
              </motion.div>
            ))}
          </div>
        </div>
      </section>

      {/* ── PRICING ── */}
      <section id="pricing" className="bg-paper/5 px-6 py-24">
        <div className="mx-auto max-w-5xl">
          <p className="eyebrow text-amber">TRANSPARENT PRICING</p>
          <h2 className="display mt-4 text-3xl text-paper">Simple. No Hidden Fees. Cancel Anytime.</h2>
          <p className="mt-4 max-w-2xl text-ink-muted">For every $100 you earn, you keep $85–90. We never take ownership of your music.</p>

          <div className="mt-12 grid gap-6 lg:grid-cols-3">
            {PRICING.map((plan) => (
              <div key={plan.name} className={`relative rounded-xl border p-6 ${plan.popular ? "border-amber bg-amber/5" : "border-hair-dark"}`}>
                {plan.badge && (
                  <span className={`absolute -top-3 left-4 rounded px-2 py-0.5 text-xs font-bold ${plan.popular ? "bg-amber text-ink" : "bg-hair-dark text-ink-muted"}`}>
                    {plan.badge}
                  </span>
                )}
                <h3 className="display mt-2 text-xl text-paper">{plan.name}</h3>
                <div className="mt-2">
                  <span className="display text-3xl text-amber">{plan.price}</span>
                  <span className="text-sm text-ink-muted">{plan.period}</span>
                </div>
                <ul className="mt-6 space-y-2">
                  {plan.features.map((f) => (
                    <li key={f} className="flex items-start gap-2 text-sm text-ink-muted">
                      <CheckCircle2 className="mt-0.5 h-3.5 w-3.5 flex-shrink-0 text-teal" />
                      {f}
                    </li>
                  ))}
                </ul>
                <button className={`mt-6 w-full rounded-lg py-2.5 text-sm font-semibold transition ${plan.popular ? "bg-amber text-ink hover:bg-amber/90" : "border border-hair-dark text-paper hover:border-ink-muted"}`}>
                  {plan.cta}
                </button>
              </div>
            ))}
          </div>

          <p className="mt-8 text-center text-xs text-ink-muted">
            First 3 artists get grandfathered into Pro at the $9.99 Entry price — permanently.
          </p>
        </div>
      </section>

      {/* ── THE PROBLEM WE SOLVE ── */}
      <section className="px-6 py-24">
        <div className="mx-auto max-w-5xl">
          <p className="eyebrow text-amber">THE REAL PROBLEM</p>
          <h2 className="display mt-4 text-3xl text-paper">You're Running a Label's Worth of Work — Alone</h2>
          <p className="mt-4 max-w-2xl text-ink-muted">
            DistroKid, Linktree, Patreon, a website builder, a sync agency, legal counsel for contracts — you already know the list. 
            The problem isn't that those tools are bad. It's that <strong className="text-paper">you're managing six logins, six dashboards, six payment methods, and none of them talk to each other.</strong>
          </p>

          <div className="mt-12 space-y-6">
            {/* Pain points */}
            {[
              {
                pain: "Your splits live in a text thread that'll get buried in 6 months",
                fix: "Split sheets created at upload, emailed to every collaborator, stored permanently. Legally referenceable, not a screenshot of a conversation.",
              },
              {
                pain: "You signed something you didn't fully understand — and didn't have time to get it reviewed first",
                fix: "Upload any contract. AI gives you a plain-language breakdown, flags red flags, tells you what to push back on, and what to specifically ask an attorney about when you're ready.",
              },
              {
                pain: "Sync licensing is closed to you because you don't have agency connections",
                fix: "Direct marketplace access. AI matches your catalog to open briefs. No exclusivity lock, no 50% agency cut. Your music gets submitted while you sleep.",
              },
              {
                pain: "You're copy-pasting the same link into 6 apps and still don't own your audience",
                fix: "One platform. Your community, your fan subscriptions, your merch, your analytics, your website — all in one place, all feeding each other data.",
              },
              {
                pain: "Your collaborators are waiting on payments that take months to figure out",
                fix: "Collaborators link their bank once. Payouts are automatic, weekly, based on the split sheet. No invoicing, no chasing, no mystery.",
              },
            ].map((item, i) => (
              <motion.div key={i} initial={{ opacity: 0, y: 10 }} whileInView={{ opacity: 1, y: 0 }} viewport={{ once: true }} transition={{ delay: i * 0.08 }} className="grid gap-4 rounded-lg border border-hair-dark p-5 sm:grid-cols-2">
                <div>
                  <p className="text-sm font-medium text-red">The pain:</p>
                  <p className="mt-1 text-sm text-ink-muted">{item.pain}</p>
                </div>
                <div>
                  <p className="text-sm font-medium text-teal">The fix:</p>
                  <p className="mt-1 text-sm text-ink-muted">{item.fix}</p>
                </div>
              </motion.div>
            ))}
          </div>

          <p className="mt-10 text-center text-sm text-ink-muted">
            All of this. One login. $9.99/mo. No more toggling between apps that don't know you exist.
          </p>
        </div>
      </section>

      {/* ── SECURITY & PRIVACY ── */}
      <section className="px-6 py-24">
        <div className="mx-auto max-w-5xl">
          <p className="eyebrow text-amber">SECURITY & PRIVACY</p>
          <h2 className="display mt-4 text-3xl text-paper">Your Money. Your Data. Protected.</h2>
          <p className="mt-4 max-w-2xl text-ink-muted">
            We handle payments and sensitive data with bank-level security. Here's what that actually means — not just marketing language.
          </p>

          <div className="mt-12 grid gap-6 sm:grid-cols-2">
            <div className="rounded-lg border border-hair-dark p-6">
              <Shield className="h-6 w-6 text-teal" />
              <h3 className="mt-4 font-medium text-paper">Collaborator Banking is Invisible</h3>
              <p className="mt-2 text-sm leading-relaxed text-ink-muted">
                When a collaborator links their bank to receive payouts, <strong>you never see their account details</strong>. 
                No bank name, no account number, no routing number. You see "bank linked: yes" and payout amounts — nothing else. 
                Their financial data is between them and Plaid.
              </p>
            </div>

            <div className="rounded-lg border border-hair-dark p-6">
              <Lock className="h-6 w-6 text-teal" />
              <h3 className="mt-4 font-medium text-paper">Encrypted at Every Layer</h3>
              <p className="mt-2 text-sm leading-relaxed text-ink-muted">
                Payment tokens are stored server-side only, encrypted at rest, and never included in any API response. 
                Even our own team can't see raw banking credentials. Plaid handles the secure connection — we just trigger payouts.
              </p>
            </div>

            <div className="rounded-lg border border-hair-dark p-6">
              <Shield className="h-6 w-6 text-teal" />
              <h3 className="mt-4 font-medium text-paper">Workspace Isolation</h3>
              <p className="mt-2 text-sm leading-relaxed text-ink-muted">
                Every artist's data is completely isolated. Artist A can never see Artist B's tracks, splits, earnings, or anything else. 
                It's the same architecture used in healthcare software — just applied to music.
              </p>
            </div>

            <div className="rounded-lg border border-hair-dark p-6">
              <Lock className="h-6 w-6 text-teal" />
              <h3 className="mt-4 font-medium text-paper">Your Music Stays Yours</h3>
              <p className="mt-2 text-sm leading-relaxed text-ink-muted">
                We never take ownership of anything you upload. Your masters, your compositions, your splits, your contracts — all yours. 
                If you leave, your music stays on streaming platforms. We don't hold your catalog hostage.
              </p>
            </div>
          </div>

          <div className="mt-8 rounded-lg border border-teal/30 bg-teal/5 p-5">
            <p className="text-sm text-paper/90">
              <strong className="text-teal">In plain terms:</strong> We built this the way we'd want it built if our own music was on the platform. 
              Your collaborators' bank details are invisible to you. Your data is invisible to other artists. 
              And nobody — not us, not a collaborator, not another artist — can access or modify your ownership records without your action.
            </p>
          </div>
        </div>
      </section>

      {/* ── CTA ── */}
      <section className="px-6 py-24 text-center">
        <div className="mx-auto max-w-3xl">
          <h2 className="display text-4xl text-paper">Ready to Own Your Music Career?</h2>
          <p className="mt-4 text-lg text-ink-muted">60-day trial. $9.99/mo. Cancel anytime. Your music stays yours.</p>
          <div className="mt-8 flex flex-wrap justify-center gap-4">
            <a href="#pricing" className="inline-flex items-center gap-2 rounded-lg bg-amber px-8 py-3 text-sm font-bold text-ink transition hover:bg-amber/90">
              Start Now <ArrowRight className="h-4 w-4" />
            </a>
            <button onClick={() => setChatOpen(true)} className="inline-flex items-center gap-2 rounded-lg border border-hair-dark px-8 py-3 text-sm font-medium text-paper transition hover:border-ink-muted">
              <Bot className="h-4 w-4 text-amber" /> Talk to AI First
            </button>
          </div>
        </div>
      </section>

      {/* ── FOOTER ── */}
      <footer className="border-t border-hair-dark px-6 py-12">
        <div className="mx-auto flex max-w-5xl items-center justify-between">
          <div>
            <p className="display text-lg text-paper">Calistro Creative</p>
            <p className="mt-1 text-xs text-ink-muted">Powered by ArtistOS · Built by Melanin Technologies Inc.</p>
          </div>
          <p className="text-xs text-ink-muted">Charlotte, NC · © 2026</p>
        </div>
      </footer>

      {/* ── CHAT WIDGET ── */}
      <AnimatePresence>
        {chatOpen && (
          <motion.div initial={{ opacity: 0, y: 20, scale: 0.95 }} animate={{ opacity: 1, y: 0, scale: 1 }} exit={{ opacity: 0, y: 20, scale: 0.95 }} className="fixed bottom-6 right-6 z-50 flex h-[500px] w-[380px] flex-col rounded-2xl border border-hair-dark bg-ink shadow-2xl">
            {/* Header */}
            <div className="flex items-center justify-between border-b border-hair-dark px-4 py-3">
              <div className="flex items-center gap-2">
                <Bot className="h-5 w-5 text-amber" />
                <span className="text-sm font-medium text-paper">Calistro Creative AI</span>
              </div>
              <button onClick={() => setChatOpen(false)} className="rounded p-1 hover:bg-hair-dark"><X className="h-4 w-4 text-ink-muted" /></button>
            </div>

            {/* Messages */}
            <div className="flex-1 space-y-3 overflow-y-auto p-4">
              {messages.map((m, i) => (
                <div key={i} className={`max-w-[85%] rounded-lg px-3 py-2 text-sm ${m.role === "user" ? "ml-auto bg-amber/20 text-paper" : "bg-hair-dark text-paper/90"}`}>
                  {m.content}
                </div>
              ))}
              {isTyping && <div className="text-xs text-ink-muted">Typing...</div>}
              <div ref={chatEndRef} />
            </div>

            {/* Quick replies */}
            {messages.length <= 2 && (
              <div className="flex flex-wrap gap-1.5 px-4 pb-2">
                {QUICK_REPLIES.map((q) => (
                  <button key={q} onClick={() => sendMessage(q)} className="rounded-full border border-hair-dark px-3 py-1 text-xs text-ink-muted transition hover:border-amber hover:text-amber">
                    {q}
                  </button>
                ))}
              </div>
            )}

            {/* Input */}
            <div className="border-t border-hair-dark p-3">
              <div className="flex gap-2">
                <input type="text" value={input} onChange={(e) => setInput(e.target.value)} onKeyDown={(e) => e.key === "Enter" && sendMessage(input)} placeholder="Ask anything..." className="flex-1 rounded-lg border border-hair-dark bg-ink px-3 py-2 text-sm text-paper placeholder-ink-muted focus:border-amber focus:outline-none" />
                <button onClick={() => sendMessage(input)} className="rounded-lg bg-amber px-3 py-2 text-ink"><Send className="h-4 w-4" /></button>
              </div>
            </div>
          </motion.div>
        )}
      </AnimatePresence>

      {/* ── FAB (when chat closed) — Vinyl Record ── */}
      {!chatOpen && (
        <motion.button
          onClick={() => setChatOpen(true)}
          initial={{ scale: 0 }}
          animate={{ scale: 1 }}
          whileHover={{ scale: 1.1 }}
          className="fixed bottom-6 right-6 z-50 flex h-16 w-16 items-center justify-center rounded-full bg-ink border-2 border-amber shadow-2xl transition group"
        >
          {/* Vinyl record SVG */}
          <svg viewBox="0 0 64 64" className="h-12 w-12 animate-[spin_4s_linear_infinite] group-hover:animate-[spin_1s_linear_infinite]">
            {/* Outer ring */}
            <circle cx="32" cy="32" r="30" fill="#14110F" stroke="#E3963E" strokeWidth="2" />
            {/* Grooves */}
            <circle cx="32" cy="32" r="24" fill="none" stroke="#332E27" strokeWidth="0.5" />
            <circle cx="32" cy="32" r="20" fill="none" stroke="#332E27" strokeWidth="0.5" />
            <circle cx="32" cy="32" r="16" fill="none" stroke="#332E27" strokeWidth="0.5" />
            <circle cx="32" cy="32" r="12" fill="none" stroke="#332E27" strokeWidth="0.5" />
            {/* Label center */}
            <circle cx="32" cy="32" r="8" fill="#E3963E" />
            {/* Spindle hole */}
            <circle cx="32" cy="32" r="2" fill="#14110F" />
            {/* Shine highlight */}
            <path d="M 20 20 Q 32 18 44 20 Q 46 32 44 44" fill="none" stroke="rgba(243,237,224,0.1)" strokeWidth="1" />
          </svg>
        </motion.button>
      )}
    </div>
  );
}
