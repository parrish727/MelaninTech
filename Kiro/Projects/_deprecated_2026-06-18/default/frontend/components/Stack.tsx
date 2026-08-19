// components/Stack.tsx
'use client'

import { motion } from 'framer-motion'

const categories = [
  {
    category: 'Frontend',
    items: ['React', 'Next.js', 'TypeScript', 'Tailwind CSS', 'React Native'],
  },
  {
    category: 'Backend',
    items: ['Node.js', 'Python', 'Go', 'GraphQL', 'REST APIs'],
  },
  {
    category: 'Data & AI',
    items: ['TensorFlow', 'PyTorch', 'Apache Spark', 'dbt', 'Snowflake'],
  },
  {
    category: 'Cloud & DevOps',
    items: ['AWS', 'GCP', 'Azure', 'Kubernetes', 'Terraform'],
  },
]

export default function Stack() {
  return (
    <section
      id="stack"
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
            Technology
          </span>
          <h2
            className="font-extrabold text-[#1E2E52] text-4xl lg:text-5xl"
            style={{ fontFamily: 'Syne, sans-serif' }}
          >
            Our Stack
          </h2>
          <p className="mt-4 text-[#1E2E52]/60 text-base max-w-xl mx-auto">
            We work with modern, proven technologies — chosen for performance, scalability, and developer experience.
          </p>
        </motion.div>

        {/* Categories */}
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-8 lg:gap-10">
          {categories.map((cat, i) => (
            <motion.div
              key={cat.category}
              initial={{ opacity: 0, y: 32 }}
              whileInView={{ opacity: 1, y: 0 }}
              viewport={{ once: true }}
              transition={{ duration: 0.5, delay: i * 0.08 }}
              className="flex flex-col gap-4 p-6 rounded-2xl bg-[#F5F3EE] border border-[#1E2E52]/08"
            >
              <h3
                className="font-extrabold text-[#3D5A99] text-lg border-b border-[#B5A84B]/30 pb-3"
                style={{ fontFamily: 'Syne, sans-serif' }}
              >
                {cat.category}
              </h3>
              <ul className="flex flex-col gap-2">
                {cat.items.map((item) => (
                  <li
                    key={item}
                    className="flex items-center gap-2 text-[#1E2E52]/75 text-sm"
                  >
                    <span className="w-1.5 h-1.5 rounded-full bg-[#B5A84B] flex-shrink-0" />
                    {item}
                  </li>
                ))}
              </ul>
            </motion.div>
          ))}
        </div>
      </div>
    </section>
  )
}