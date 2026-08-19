// components/Culture.tsx
'use client'

import Image from 'next/image'
import { motion } from 'framer-motion'

const values = [
  {
    title: 'Excellence',
    description: 'We hold ourselves to the highest standard — in craft, in communication, and in culture.',
  },
  {
    title: 'Equity',
    description: 'We believe great technology should open doors, not close them. Inclusion is baked into everything we build.',
  },
  {
    title: 'Community',
    description: 'We invest in the next generation of Black and Brown technologists through mentorship, hiring, and advocacy.',
  },
  {
    title: 'Courage',
    description: 'We tackle hard problems and say the hard truths — because that's how you earn trust.',
  },
]

export default function Culture() {
  return (
    <section
      id="culture"
      className="bg-[#F5F3EE] py-24 lg:py-32"
    >
      <div className="max-w-7xl mx-auto px-6 lg:px-12">
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-16 lg:gap-24 items-center">
          {/* Left: image */}
          <motion.div
            initial={{ opacity: 0, x: -32 }}
            whileInView={{ opacity: 1, x: 0 }}
            viewport={{ once: true }}
            transition={{ duration: 0.7 }}
            className="relative h-80 lg:h-[520px] rounded-3xl overflow-hidden"
          >
            <Image
              src="/illustrations/culture.jpg"
              alt="Our Culture"
              fill
              className="object-cover"
            />
            <div className="absolute inset-0 bg-gradient-to-t from-[#1E2E52]/60 to-transparent" />
          </motion.div>

          {/* Right: content */}
          <motion.div
            initial={{ opacity: 0, x: 32 }}
            whileInView={{ opacity: 1, x: 0 }}
            viewport={{ once: true }}
            transition={{ duration: 0.7 }}
            className="flex flex-col gap-8"
          >
            <div>
              <span className="inline-block text-[#B5A84B] text-sm font-semibold tracking-widest uppercase mb-4">
                Who We Are
              </span>
              <h2
                className="font-extrabold text-[#1E2E52] text-4xl lg:text-5xl leading-tight"
                style={{ fontFamily: 'Syne, sans-serif' }}
              >
                Built on Culture.<br />Driven by Purpose.
              </h2>
            </div>

            <p className="text-[#1E2E52]/70 text-base leading-relaxed">
              Melanin Technologies is more than a tech firm. We are a movement — proving that 
              diversity and technical excellence are not competing ideas, but complementary forces 
              that make better products and better businesses.
            </p>

            <div className="grid grid-cols-1 sm:grid-cols-2 gap-6">
              {values.map((v, i) => (
                <motion.div
                  key={v.title}
                  initial={{ opacity: 0, y: 20 }}
                  whileInView={{ opacity: 1, y: 0 }}
                  viewport={{ once: true }}
                  transition={{ duration: 0.5, delay: i * 0.1 }}
                  className="flex flex-col gap-2"
                >
                  <div className="flex items-center gap-2">
                    <div className="w-2 h-2 rounded-full bg-[#B5A84B]" />
                    <h4
                      className="font-extrabold text-[#1E2E52] text-base"
                      style={{ fontFamily: 'Syne, sans-serif' }}
                    >
                      {v.title}
                    </h4>
                  </div>
                  <p className="text-[#1E2E52]/65 text-sm leading-relaxed pl-4">
                    {v.description}
                  </p>
                </motion.div>
              ))}
            </div>
          </motion.div>
        </div>
      </div>
    </section>
  )
}