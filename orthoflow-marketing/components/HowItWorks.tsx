"use client";

import { motion } from "framer-motion";
import { Rocket, Settings, CheckCircle2 } from "lucide-react";

const steps = [
  {
    icon: Rocket,
    step: "01",
    title: "Onboard Your Practice",
    description: "We migrate your data, set up your schedule, and train your team in one week.",
  },
  {
    icon: Settings,
    step: "02",
    title: "Run Your Day",
    description: "Schedule, chart, image, and bill from one screen. AI handles the documentation.",
  },
  {
    icon: CheckCircle2,
    step: "03",
    title: "Get Paid Faster",
    description: "Claims submit automatically. Denials get AI-written appeals. Collections improve month over month.",
  },
];

export default function HowItWorks() {
  return (
    <section id="how-it-works" className="py-20 md:py-28 bg-gray-50">
      <div className="max-w-7xl mx-auto px-6">
        <div className="text-center max-w-2xl mx-auto mb-16">
          <h2 className="text-3xl md:text-4xl font-bold text-gray-900 tracking-tight">
            Live in days, not months.
          </h2>
          <p className="mt-4 text-lg text-gray-600">
            We handle the migration. Your team is productive on day one.
          </p>
        </div>

        <div className="grid md:grid-cols-3 gap-10">
          {steps.map((step, i) => (
            <motion.div
              key={step.step}
              className="text-center"
              initial={{ opacity: 0, y: 20 }}
              whileInView={{ opacity: 1, y: 0 }}
              viewport={{ once: true }}
              transition={{ duration: 0.5, delay: i * 0.15 }}
            >
              <div className="w-16 h-16 mx-auto rounded-full bg-teal-100 flex items-center justify-center mb-5">
                <step.icon size={28} className="text-teal-700" />
              </div>
              <p className="text-sm font-bold text-teal-600 mb-2">{step.step}</p>
              <h3 className="text-xl font-bold text-gray-900 mb-3">{step.title}</h3>
              <p className="text-gray-600 leading-relaxed">{step.description}</p>
            </motion.div>
          ))}
        </div>
      </div>
    </section>
  );
}
