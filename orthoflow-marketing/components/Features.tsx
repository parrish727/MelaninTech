"use client";

import { motion } from "framer-motion";
import {
  CalendarDays,
  Users,
  FileImage,
  Stethoscope,
  FileText,
  Brain,
  Zap,
  Shield,
  RefreshCw,
  BarChart3,
  UserCircle,
  Sparkles,
  Clock,
  Bell,
  AlertTriangle,
  ArrowRightLeft,
} from "lucide-react";

const clinicalFeatures = [
  {
    icon: CalendarDays,
    title: "Column-Based Scheduling",
    description: "See every chair, every patient, every DA at a glance. Drag-and-drop appointments with real-time updates.",
  },
  {
    icon: Users,
    title: "DA Assignment Board",
    description: "Assign dental assistants per appointment with one click. No whiteboards, no walkie-talkies, no confusion.",
  },
  {
    icon: FileImage,
    title: "Integrated Imaging",
    description: "X-rays, pano, ceph, CBCT: upload directly from your machines and view inside the patient chart. No separate software.",
  },
  {
    icon: Stethoscope,
    title: "Clinical Charting",
    description: "Orthodontic-specific tooth chart with bracket placement, arch wires, and treatment notes. AI-assisted dictation built in.",
  },
];

const financialFeatures = [
  {
    icon: FileText,
    title: "Instant Invoice Upload",
    description: "Drag and drop invoices from any vendor. OCR extracts data automatically; no manual entry ever again.",
  },
  {
    icon: Brain,
    title: "AI Classification",
    description: "Our AI learns your categories and vendors. Invoices are classified in seconds with 99% accuracy.",
  },
  {
    icon: Zap,
    title: "QuickBooks Sync",
    description: "Approved invoices sync directly to QuickBooks. No double-entry, no export/import gymnastics.",
  },
  {
    icon: Shield,
    title: "Insurance & Eligibility",
    description: "Automatic eligibility checks the morning of appointments. AI-powered claim submission and denial detection.",
  },
  {
    icon: RefreshCw,
    title: "Approval Workflow",
    description: "Route invoices for approval with one click. Practice owners approve from their phone in seconds.",
  },
  {
    icon: BarChart3,
    title: "Spend Intelligence",
    description: "See where your money goes. Vendor insights, spending trends, budget alerts, and duplicate detection, all automatic.",
  },
];

const patientFeatures = [
  {
    icon: UserCircle,
    title: "Patient Portal",
    description: "Patients view appointments, fill forms, message the office, and track treatment progress — all from their phone.",
  },
  {
    icon: Sparkles,
    title: "AI Clinical Notes",
    description: "Your DA types shorthand, and AI formats it into proper clinical documentation. Charting in half the time.",
  },
  {
    icon: Clock,
    title: "Treatment Timeline",
    description: "AI predicts remaining months, next milestones, and flags patients at risk of falling behind schedule.",
  },
  {
    icon: Bell,
    title: "Automated Reminders",
    description: "Appointment reminders via email with confirmation workflows. No-shows drop, your chairs stay full.",
  },
  {
    icon: AlertTriangle,
    title: "Denial Detection & Appeals",
    description: "AI analyzes insurance denials, generates appeal letters, and tracks recovery potential — so money doesn't slip through the cracks.",
  },
  {
    icon: ArrowRightLeft,
    title: "Seamless Migration",
    description: "Import from Dolphin, Ortho2, or Eaglesoft in 5 steps. We handle the heavy lifting so you switch without downtime.",
  },
];

export default function Features() {
  return (
    <section id="features" className="py-20 md:py-28 bg-white">
      <div className="max-w-7xl mx-auto px-6">
        {/* Clinical Features */}
        <div className="mb-20">
          <div className="text-center max-w-2xl mx-auto mb-12">
            <p className="text-teal-600 text-sm font-semibold tracking-wide uppercase mb-2">Clinical Platform</p>
            <h2 className="text-3xl md:text-4xl font-bold text-gray-900 tracking-tight">
              Everything your clinical team needs in one screen
            </h2>
            <p className="mt-4 text-lg text-gray-600">
              Scheduling, charting, imaging, and DA management, designed for how orthodontic offices actually work.
            </p>
          </div>

          <div className="grid md:grid-cols-2 lg:grid-cols-4 gap-6">
            {clinicalFeatures.map((feature, i) => (
              <motion.div
                key={feature.title}
                className="p-6 rounded-xl border border-gray-200 hover:border-teal-200 hover:shadow-lg transition-all"
                initial={{ opacity: 0, y: 20 }}
                whileInView={{ opacity: 1, y: 0 }}
                viewport={{ once: true }}
                transition={{ duration: 0.5, delay: i * 0.1 }}
              >
                <div className="w-12 h-12 rounded-lg bg-teal-50 flex items-center justify-center mb-4">
                  <feature.icon size={24} className="text-teal-600" />
                </div>
                <h3 className="text-lg font-semibold text-gray-900 mb-2">{feature.title}</h3>
                <p className="text-gray-600 leading-relaxed text-sm">{feature.description}</p>
              </motion.div>
            ))}
          </div>
        </div>

        {/* Financial Features */}
        <div className="mb-20">
          <div className="text-center max-w-2xl mx-auto mb-12">
            <p className="text-emerald-600 text-sm font-semibold tracking-wide uppercase mb-2">Financial Automation</p>
            <h2 className="text-3xl md:text-4xl font-bold text-gray-900 tracking-tight">
              AI-powered billing that pays for itself
            </h2>
            <p className="mt-4 text-lg text-gray-600">
              From invoice upload to QuickBooks sync, your back office runs on autopilot.
            </p>
          </div>

          <div className="grid md:grid-cols-2 lg:grid-cols-3 gap-8">
            {financialFeatures.map((feature, i) => (
              <motion.div
                key={feature.title}
                className="p-6 rounded-xl border border-gray-200 hover:border-emerald-200 hover:shadow-lg transition-all"
                initial={{ opacity: 0, y: 20 }}
                whileInView={{ opacity: 1, y: 0 }}
                viewport={{ once: true }}
                transition={{ duration: 0.5, delay: i * 0.1 }}
              >
                <div className="w-12 h-12 rounded-lg bg-emerald-50 flex items-center justify-center mb-4">
                  <feature.icon size={24} className="text-emerald-600" />
                </div>
                <h3 className="text-lg font-semibold text-gray-900 mb-2">{feature.title}</h3>
                <p className="text-gray-600 leading-relaxed">{feature.description}</p>
              </motion.div>
            ))}
          </div>
        </div>

        {/* Patient Experience & Intelligence */}
        <div>
          <div className="text-center max-w-2xl mx-auto mb-12">
            <p className="text-violet-600 text-sm font-semibold tracking-wide uppercase mb-2">Patient Experience & Intelligence</p>
            <h2 className="text-3xl md:text-4xl font-bold text-gray-900 tracking-tight">
              Smarter patient engagement, powered by AI
            </h2>
            <p className="mt-4 text-lg text-gray-600">
              From portal access to predictive timelines, give patients a modern experience while your team works faster.
            </p>
          </div>

          <div className="grid md:grid-cols-2 lg:grid-cols-3 gap-8">
            {patientFeatures.map((feature, i) => (
              <motion.div
                key={feature.title}
                className="p-6 rounded-xl border border-gray-200 hover:border-violet-200 hover:shadow-lg transition-all"
                initial={{ opacity: 0, y: 20 }}
                whileInView={{ opacity: 1, y: 0 }}
                viewport={{ once: true }}
                transition={{ duration: 0.5, delay: i * 0.1 }}
              >
                <div className="w-12 h-12 rounded-lg bg-violet-50 flex items-center justify-center mb-4">
                  <feature.icon size={24} className="text-violet-600" />
                </div>
                <h3 className="text-lg font-semibold text-gray-900 mb-2">{feature.title}</h3>
                <p className="text-gray-600 leading-relaxed">{feature.description}</p>
              </motion.div>
            ))}
          </div>
        </div>
      </div>
    </section>
  );
}
