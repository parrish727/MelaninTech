"use client";

import { motion } from "framer-motion";
import { Check } from "lucide-react";

const plans = [
  {
    name: "Starter",
    description: "Account processing & staff management",
    price: "$299",
    period: "per month",
    features: [
      "Unlimited invoice uploads",
      "AI classification & validation",
      "QuickBooks sync",
      "Approval workflows",
      "Spend analytics",
      "Duplicate detection",
      "Staff time clock (in/out)",
      "Payroll hours tracking",
      "Email + SMS notifications",
      "99.9% uptime",
    ],
    cta: "Request Demo",
    popular: false,
  },
  {
    name: "Clinical",
    description: "Complete practice management platform",
    price: "$599",
    period: "per month",
    features: [
      "Everything in Starter",
      "Column-based scheduler",
      "DA assignment board",
      "Patient clinical charts",
      "Tooth charting",
      "Clinical note assist",
      "Imaging integration",
      "Appointment reminders",
      "Insurance & eligibility",
      "Patient portal",
      "Financial reporting",
      "Denial review & appeals",
    ],
    cta: "Schedule Demo",
    popular: true,
  },
  {
    name: "Enterprise",
    description: "Multi-location practices & DSOs",
    price: "$999",
    period: "per month",
    features: [
      "Everything in Clinical",
      "Multi-location dashboard",
      "Dedicated infrastructure",
      "Data migration included",
      "Custom form builder",
      "Priority support + onboarding",
      "Phone support",
    ],
    cta: "Talk to Sales",
    popular: false,
  },
];

export default function Pricing() {
  return (
    <section id="pricing" className="py-20 md:py-28 bg-white">
      <div className="max-w-7xl mx-auto px-6">
        <div className="text-center max-w-2xl mx-auto mb-16">
          <h2 className="text-3xl md:text-4xl font-bold text-gray-900 tracking-tight">
            Simple, transparent pricing
          </h2>
          <p className="mt-4 text-lg text-gray-600">
            No hidden fees. No per-seat charges. Unlimited users on every plan.
          </p>
        </div>

        <div className="grid md:grid-cols-3 gap-8 max-w-6xl mx-auto">
          {plans.map((plan, i) => (
            <motion.div
              key={plan.name}
              className={`relative p-8 rounded-2xl border-2 ${
                plan.popular
                  ? "border-teal-500 shadow-xl scale-[1.02]"
                  : "border-gray-200"
              }`}
              initial={{ opacity: 0, y: 20 }}
              whileInView={{ opacity: 1, y: 0 }}
              viewport={{ once: true }}
              transition={{ duration: 0.5, delay: i * 0.1 }}
            >
              {plan.popular && (
                <span className="absolute -top-3 left-8 px-3 py-1 bg-teal-600 text-white text-xs font-bold rounded-full">
                  Most Popular
                </span>
              )}

              <h3 className="text-2xl font-bold text-gray-900">{plan.name}</h3>
              <p className="text-gray-600 mt-1 text-sm">{plan.description}</p>

              <div className="mt-6 mb-8">
                <span className="text-4xl font-extrabold text-gray-900">{plan.price}</span>
                <span className="text-gray-500 ml-2">/ {plan.period}</span>
              </div>

              <ul className="space-y-3 mb-8">
                {plan.features.map((feature) => (
                  <li key={feature} className="flex items-start gap-3">
                    <Check size={18} className="text-teal-600 mt-0.5 shrink-0" />
                    <span className="text-gray-700 text-sm">{feature}</span>
                  </li>
                ))}
              </ul>

              <a
                href="#demo"
                className={`block text-center py-3 rounded-lg font-semibold transition-colors ${
                  plan.popular
                    ? "bg-teal-600 text-white hover:bg-teal-700"
                    : "bg-gray-100 text-gray-900 hover:bg-gray-200"
                }`}
              >
                {plan.cta}
              </a>
            </motion.div>
          ))}
        </div>

        <p className="text-center text-sm text-gray-500 mt-8">
          All plans include enterprise-grade security, encrypted data, and full audit trail as standard.
          <br />
          Need self-hosted? Contact us for on-premise pricing.
        </p>
      </div>
    </section>
  );
}
