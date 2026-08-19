// components/Hero.tsx
'use client'

import Image from 'next/image'
import Link from 'next/link'
import { motion } from 'framer-motion'

export default function Hero() {
  return (
    <section className="relative min-h-screen bg-[#1E2E52] flex items-center overflow-hidden pt-16">
      {/* Background globe image */}
      <div className="absolute inset-0 z-0">
        <Image
          src="/tech-globe.jpg"
          alt="Tech Globe"
          fill
          className="object-cover opacity-20"
          priority
        />
        <div className="absolute inset-0 bg-gradient-to-r from-[#1E2E52] via-[#1E2E52]/80 to-transparent" />
      </div>

      {/* Molecule decoration */}
      <div className="absolute right-0 bottom-0 w-1/2 h-full z-0 hidden lg:block">
        <Image
          src="/molecule.png"
          alt=""
          fill
          className="object-contain object-right-bottom opacity-30"
        />
      </div>

      <div className="relative z-10 max-w-7xl mx-auto px-6 lg:px-12 py-24 lg:py-32">
        <div className="max-w-3xl">
          <motion.div
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.6 }}
          >
            <span className="inline-block text-[#B5A84B] text-sm font-semibold tracking-widest uppercase mb-6">
              Engineering Equity Through Technology
            </span>
          </motion.div>

          <motion.h1
            initial={{ opacity: 0, y: 30 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.7, delay: 0.1 }}
            className="font-extrabold text-white text-5xl lg:text-7xl leading-tight mb-6"
            style={{ fontFamily: 'Syne, sans-serif' }}
          >
            Melanin{' '}
            <span className="text-[#B5A84B]">Technologies</span>
          </motion.h1>

          <motion.p
            initial={{ opacity: 0, y: 30 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.7, delay: 0.2 }}
            className="text-white/70 text-lg lg:text-xl leading-relaxed mb-10 max-w-xl"
          >
            We build transformative digital products, platforms, and teams — 
            rooted in cultural excellence and powered by world-class engineering.
          </motion.p>

          <motion.div
            initial={{ opacity: 0, y: 30 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.7, delay: 0.3 }}
            className="flex flex-wrap gap-4"
          >
            <Link
              href="#services"
              className="inline-flex items-center px-8 py-4 rounded-full bg-[#B5A84B] hover:bg-[#D4C96A] text-[#1E2E52] font-semibold text-base transition-colors duration-200"
            >
              Explore Our Work
            </Link>
            <Link
              href="#contact"
              className="inline-flex items-center px-8 py-4 rounded-full border border-white/30 hover:border-white/60 text-white font-semibold text-base transition-colors duration-200"
            >
              Get In Touch
            </Link>
          </motion.div>
        </div>
      </div>

      {/* Bottom fade */}
      <div className="absolute bottom-0 left-0 right-0 h-24 bg-gradient-to-t from-[#F5F3EE] to-transparent z-10" />
    </section>
  )
}