"use client";

import { motion } from "framer-motion";
import { ArrowRight, Play } from "lucide-react";

export default function Hero() {
  return (
    <section className="relative pt-32 pb-20 md:pt-40 md:pb-28 bg-gradient-to-br from-teal-700 via-teal-800 to-gray-900 overflow-hidden">
      {/* Background pattern */}
      <div className="absolute inset-0 opacity-10">
        <div className="absolute top-20 left-10 w-72 h-72 bg-teal-300 rounded-full blur-3xl" />
        <div className="absolute bottom-10 right-10 w-96 h-96 bg-blue-500 rounded-full blur-3xl" />
      </div>

      <div className="relative max-w-7xl mx-auto px-6">
        <div className="max-w-3xl">
          <motion.div
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.6 }}
          >
            <p className="text-teal-300 text-sm font-semibold tracking-wide uppercase mb-4">
              The Complete Orthodontic Platform
            </p>
            <h1 className="text-4xl md:text-5xl lg:text-6xl font-extrabold text-white leading-tight tracking-tight">
              One platform for your
              <br />
              <span className="text-teal-300">entire practice.</span>
            </h1>
            <p className="mt-6 text-lg md:text-xl text-gray-300 leading-relaxed max-w-2xl">
              Scheduling, clinical charting, imaging, patient portal, AI-powered billing, and practice
              intelligence — built from scratch for orthodontic teams. One platform replaces five apps
              and gives your team hours back every day.
            </p>
          </motion.div>

          <motion.div
            className="mt-10 flex flex-col sm:flex-row gap-4"
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.6, delay: 0.2 }}
          >
            <a
              href="#demo"
              className="inline-flex items-center justify-center gap-2 px-7 py-3.5 bg-teal-500 text-white font-semibold rounded-lg hover:bg-teal-400 transition-colors"
            >
              Schedule a Demo
              <ArrowRight size={18} />
            </a>
            <a
              href="#features"
              className="inline-flex items-center justify-center gap-2 px-7 py-3.5 border border-white/20 text-white font-medium rounded-lg hover:border-teal-300 hover:text-teal-300 transition-colors"
            >
              <Play size={16} />
              See All Features
            </a>
          </motion.div>

          {/* Quick stats */}
          <motion.div
            className="mt-14 grid grid-cols-3 gap-8 max-w-lg"
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            transition={{ duration: 0.6, delay: 0.4 }}
          >
            <div>
              <p className="text-3xl font-bold text-white">1</p>
              <p className="text-sm text-gray-400 mt-1">Platform for everything</p>
            </div>
            <div>
              <p className="text-3xl font-bold text-white">10hr</p>
              <p className="text-sm text-gray-400 mt-1">Saved per week on billing</p>
            </div>
            <div>
              <p className="text-3xl font-bold text-white">99%</p>
              <p className="text-sm text-gray-400 mt-1">AI classification accuracy</p>
            </div>
          </motion.div>
        </div>
      </div>
    </section>
  );
}
