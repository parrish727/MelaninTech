// components/HowWeWork.tsx
'use client'

import { motion } from 'framer-motion'

const steps = [
  {
    step: '01',
    title: 'Discover',
    description:
      'We immerse ourselves in your world — your users, your goals, your constraints — to surface what matters most.',
  },
  {
    step: '02',
    title: 'Define',
    description:
      'We shape a clear strategy and roadmap, aligning stakeholders and setting measurable outcomes.',
  },
  {
    step: '03',
    title: 'Design & Build',
    description:
      'Rapid, iterative delivery with engineering rigour. We ship early, learn fast, and refine constantly.',
  },
  {
    step: '04',
    title: 'Scale & Support',
    description:
      'We stand by our work — with ongoing support, performance monitoring, and continuous improvement.',
  },
]

export default function HowWeWork() {
  return (
    <section
      id="how-we-work"
      className="bg-[#1E2E52] py-24 lg:py-32"
    >
      <div className="max-w-7xl mx-auto px-6 lg:px-12">
        {/* Header */}
        <motion.div
          initial={{ opacity: 0, y: 24 }}
          whileInView={{ opacity: 1, y: 0 }}
          viewport={{ once: true }}
          transition={{ duration: 0.6 }}
          className="text-center mb-16 lg:mb-20"
        >
          <span className="inline-block text-[#B5A84B] text-sm font-semibold tracking-widest uppercase mb-4">
            Our Process
          </span>
          <h2
            className="font-extrabold text-white text-4xl lg:text-5xl"
            style={{ fontFamily: 'Syne, sans-serif' }}
          >
            How We Work
          </h2>
        </motion.div>

        {/* Steps */}
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-8 lg:gap-10">
          {steps.map((s, i) => (
            <motion.div
              key={s.step}
              initial={{ opacity: 0, y: 32 }}
              whileInView={{ opacity: 1, y: 0 }}
              viewport={{ once: true }}
              transition={{ duration: 0.5, delay: i * 0.1 }}
              className="flex flex-col items-center text-center gap-4"
            >
              <div className="w-14 h-14 rounded-full bg-[#B5A84B]/20 border border-[#B5A84B]/40 flex items-center justify-center mb-2">
                <span
                  className="text-[#B5A84B] font-extrabold text-lg"
                  style={{ fontFamily: 'Syne, sans-serif' }}
                >
                  {s.step}
                </span>
              </div>
              <h3
                className="font-extrabold text-white text-xl"
                style={{ fontFamily: 'Syne, sans-serif' }}
              >
                {s.title}
              </h3>
              <p className="text-white/60 text-sm leading-relaxed">
                {s.description}
              </p>
            </motion.div>
          ))}
        </div>
      </div>
    </section>
  )
}