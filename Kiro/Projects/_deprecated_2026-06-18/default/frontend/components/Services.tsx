// components/Services.tsx
'use client'

import { motion } from 'framer-motion'

const services = [
  {
    number: '01',
    title: 'Product Engineering',
    description:
      'End-to-end design and development of scalable web and mobile products that solve real problems for real people.',
  },
  {
    number: '02',
    title: 'Data & AI Solutions',
    description:
      'From machine learning pipelines to intelligent dashboards — we make data work for your mission.',
  },
  {
    number: '03',
    title: 'Cloud & Infrastructure',
    description:
      'Architecting resilient, secure, and cost-efficient cloud environments on AWS, GCP, and Azure.',
  },
  {
    number: '04',
    title: 'Digital Transformation',
    description:
      'Helping organizations modernize legacy systems, adopt agile workflows, and unlock new digital revenue streams.',
  },
  {
    number: '05',
    title: 'Tech Talent Solutions',
    description:
      'Connecting companies with exceptional Black and Brown engineering talent — full-time, contract, or embedded teams.',
  },
  {
    number: '06',
    title: 'Startup Studio',
    description:
      'Co-founding and accelerating early-stage ventures with technical co-founder support, MVP builds, and go-to-market strategy.',
  },
]

export default function Services() {
  return (
    <section
      id="services"
      className="bg-white py-24 lg:py-32"
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
            What We Do
          </span>
          <h2
            className="font-extrabold text-[#1E2E52] text-4xl lg:text-5xl"
            style={{ fontFamily: 'Syne, sans-serif' }}
          >
            Our Services
          </h2>
        </motion.div>

        {/* Grid */}
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-8 lg:gap-10">
          {services.map((service, i) => (
            <motion.div
              key={service.number}
              initial={{ opacity: 0, y: 32 }}
              whileInView={{ opacity: 1, y: 0 }}
              viewport={{ once: true }}
              transition={{ duration: 0.5, delay: i * 0.08 }}
              className="group flex flex-col gap-4 p-8 rounded-2xl border border-[#1E2E52]/10 hover:border-[#B5A84B]/40 hover:shadow-lg transition-all duration-300 bg-[#F5F3EE]/50 hover:bg-white"
            >
              <span
                className="text-[#B5A84B] font-extrabold text-3xl"
                style={{ fontFamily: 'Syne, sans-serif' }}
              >
                {service.number}
              </span>
              <h3
                className="font-extrabold text-[#1E2E52] text-xl"
                style={{ fontFamily: 'Syne, sans-serif' }}
              >
                {service.title}
              </h3>
              <p className="text-[#1E2E52]/70 text-sm leading-relaxed">
                {service.description}
              </p>
            </motion.div>
          ))}
        </div>
      </div>
    </section>
  )
}