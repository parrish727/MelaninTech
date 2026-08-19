# Task
check if frontend agent is running and give an updated output

# Proposal
I'll check the current state of the melanin-tech-website frontend and give you an updated output of the key files.

Let me start by reading the existing files:

<tool_call>
{"name": "read_file", "arguments": {"path": "/app/Projects/default/frontend/app/page.tsx"}}
</tool_call>
<tool_response>
import Nav from "@/components/Nav";
import Hero from "@/components/Hero";
import Services from "@/components/Services";
import HowWeWork from "@/components/HowWeWork";
import WhoWeAre from "@/components/WhoWeAre";
import Stack from "@/components/Stack";
import Contact from "@/components/Contact";
import Footer from "@/components/Footer";

export default function Home() {
  return (
    <main>
      <Nav />
      <Hero />
      <Services />
      <HowWeWork />
      <WhoWeAre />
      <Stack />
      <Contact />
      <Footer />
    </main>
  );
}
</tool_response>

<tool_call>
{"name": "read_file", "arguments": {"path": "/app/Projects/default/frontend/app/globals.css"}}
</tool_call>
<tool_response>
@import url('https://fonts.googleapis.com/css2?family=Syne:wght@400;700;800&family=Inter:wght@400;500;600&display=swap');

@tailwind base;
@tailwind components;
@tailwind utilities;

:root {
  --blue: #3D5A99;
  --blue-dark: #2C4275;
  --blue-deep: #1E2E52;
  --gold: #B5A84B;
  --gold-light: #D4C96A;
  --sage: #6B9E78;
  --off-white: #F5F3EE;
}

* {
  margin: 0;
  padding: 0;
  box-sizing: border-box;
}

html {
  scroll-behavior: smooth;
}

body {
  font-family: 'Inter', sans-serif;
  background-color: var(--off-white);
  color: #1a1a1a;
}

h1, h2, h3, h4 {
  font-family: 'Syne', sans-serif;
}

.section-padding {
  @apply px-6 md:px-12 lg:px-24;
}
</tool_response>

<tool_call>
{"name": "read_file", "arguments": {"path": "/app/Projects/default/frontend/components/Nav.tsx"}}
</tool_call>
<tool_response>
// components/Nav.tsx
"use client";

import { useState } from "react";
import Image from "next/image";
import Link from "next/link";

export default function Nav() {
  const [open, setOpen] = useState(false);

  return (
    <nav className="fixed top-0 left-0 right-0 z-50 bg-[#1E2E52]/95 backdrop-blur-sm border-b border-white/10">
      <div className="max-w-7xl mx-auto section-padding flex items-center justify-between h-16">
        {/* Logo */}
        <Link href="/" className="flex items-center gap-3">
          <Image src="/logo.png" alt="Melanin Technologies" width={36} height={36} className="rounded" />
          <span className="font-extrabold text-white text-lg" style={{ fontFamily: 'Syne, sans-serif' }}>
            Melanin Technologies
          </span>
        </Link>

        {/* Desktop links */}
        <div className="hidden md:flex items-center gap-8">
          {["Services", "How We Work", "Culture", "Stack", "Contact"].map((item) => (
            <Link
              key={item}
              href={`#${item.toLowerCase().replace(/\s+/g, "-")}`}
              className="text-white/80 hover:text-[#D4C96A] text-sm font-medium transition-colors"
            >
              {item}
            </Link>
          ))}
          <Link
            href="#contact"
            className="bg-[#B5A84B] hover:bg-[#D4C96A] text-white text-sm font-semibold px-5 py-2 rounded transition-colors"
          >
            Get Started →
          </Link>
        </div>

        {/* Mobile hamburger */}
        <button
          className="md:hidden text-white p-2"
          onClick={() => setOpen(!open)}
          aria-label="Toggle menu"
        >
          <div className={`w-6 h-0.5 bg-white transition-all mb-1.5 ${open ? "rotate-45 translate-y-2" : ""}`} />
          <div className={`w-6 h-0.5 bg-white transition-all mb-1.5 ${open ? "opacity-0" : ""}`} />
          <div className={`w-6 h-0.5 bg-white transition-all ${open ? "-rotate-45 -translate-y-2" : ""}`} />
        </button>
      </div>

      {/* Mobile menu */}
      {open && (
        <div className="md:hidden bg-[#1E2E52] border-t border-white/10 section-padding py-4 flex flex-col gap-4">
          {["Services", "How We Work", "Culture", "Stack", "Contact"].map((item) => (
            <Link
              key={item}
              href={`#${item.toLowerCase().replace(/\s+/g, "-")}`}
              className="text-white/80 hover:text-[#D4C96A] text-sm font-medium transition-colors"
              onClick={() => setOpen(false)}
            >
              {item}
            </Link>
          ))}
          <Link
            href="#contact"
            className="bg-[#B5A84B] hover:bg-[#D4C96A] text-white text-sm font-semibold px-5 py-2 rounded transition-colors w-fit"
            onClick={() => setOpen(false)}
          >
            Get Started →
          </Link>
        </div>
      )}
    </nav>
  );
}
</tool_response>

<tool_call>
{"name": "read_file", "arguments": {"path": "/app/Projects/default/frontend/components/Hero.tsx"}}
</tool_call>
<tool_response>
// components/Hero.tsx
"use client";

import Image from "next/image";
import { motion } from "framer-motion";

export default function Hero() {
  return (
    <section className="relative min-h-screen bg-[#1E2E52] flex items-center overflow-hidden pt-16">
      {/* Background image */}
      <div className="absolute inset-0 z-0">
        <Image
          src="/tech-globe.jpg"
          alt=""
          fill
          className="object-cover opacity-20"
          priority
        />
      </div>

      {/* Decorative molecule */}
      <div className="absolute right-0 top-1/2 -translate-y-1/2 w-96 h-96 opacity-10 z-0 hidden lg:block">
        <Image src="/molecule.png" alt="" fill className="object-contain" />
      </div>

      <div className="relative z-10 max-w-7xl mx-auto section-padding w-full py-24">
        <div className="max-w-3xl">
          <motion.div
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.6 }}
          >
            <span className="inline-block text-[#D4C96A] text-sm font-semibold tracking-widest uppercase mb-6">
              Technology · Culture · Excellence
            </span>
          </motion.div>

          <motion.h1
            className="font-extrabold text-white leading-tight mb-6"
            style={{ fontFamily: 'Syne, sans-serif', fontSize: 'clamp(2.5rem, 6vw, 5rem)' }}
            initial={{ opacity: 0, y: 30 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.7, delay: 0.1 }}
          >
            Melanin Technologies
          </motion.h1>

          <motion.p
            className="text-white/70 text-lg md:text-xl leading-relaxed mb-10 max-w-2xl"
            initial={{ opacity: 0, y: 30 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.7, delay: 0.2 }}
          >
            We build cutting-edge digital products and platforms that drive transformation.
            Powered by diverse talent, rooted in excellence.
          </motion.p>

          <motion.div
            className="flex flex-wrap gap-4"
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.6, delay: 0.3 }}
          >
            <a
              href="#contact"
              className="bg-[#B5A84B] hover:bg-[#D4C96A] text-white font-semibold px-8 py-4 rounded transition-colors text-base"
            >
              Start a Project →
            </a>
            <a
              href="#services"
              className="border border-white/30 hover:border-[#D4C96A] text-white hover:text-[#D4C96A] font-semibold px-8 py-4 rounded transition-colors text-base"
            >
              Our Services →
            </a>
          </motion.div>
        </div>
      </div>
    </section>
  );
}
</tool_response>

<tool_call>
{"name": "read_file", "arguments": {"path": "/app/Projects/default/frontend/components/Services.tsx"}}
</tool_call>
<tool_response>
// components/Services.tsx
"use client";

import { motion } from "framer-motion";

const services = [
  {
    icon: "⚡",
    title: "Digital Product Engineering",
    description:
      "End-to-end design and development of web and mobile products — from MVP to enterprise scale.",
  },
  {
    icon: "☁️",
    title: "Cloud & Infrastructure",
    description:
      "AWS, GCP, and Azure architecture, DevOps pipelines, Kubernetes, and cloud-native migrations.",
  },
  {
    icon: "🤖",
    title: "AI & Data Solutions",
    description:
      "Machine learning models, data pipelines, analytics dashboards, and intelligent automation.",
  },
  {
    icon: "🔒",
    title: "Cybersecurity",
    description:
      "Penetration testing, security audits, compliance frameworks (SOC2, ISO 27001), and zero-trust architecture.",
  },
  {
    icon: "🎨",
    title: "UX & Design Systems",
    description:
      "User research, interaction design, and scalable design systems built for real engineering teams.",
  },
  {
    icon: "🔗",
    title: "API & Integration",
    description:
      "REST and GraphQL APIs, third-party integrations, microservices architecture, and event-driven systems.",
  },
];

export default function Services() {
  return (
    <section id="services" className="bg-white py-24">
      <div className="max-w-7xl mx-auto section-padding">
        {/* Header */}
        <motion.div
          className="mb-16 text-center"
          initial={{ opacity: 0, y: 30 }}
          whileInView={{ opacity: 1, y: 0 }}
          viewport={{ once: true }}
          transition={{ duration: 0.6 }}
        >
          <span className="inline-block text-[#B5A84B] text-sm font-semibold tracking-widest uppercase mb-4">
            What We Do
          </span>
          <h2
            className="font-extrabold text-[#1E2E52] text-4xl md:text-5xl mb-4"
            style={{ fontFamily: "Syne, sans-serif" }}
          >
            Our Services
          </h2>
          <p className="text-gray-500 max-w-xl mx-auto text-lg">
            From strategy to deployment — we deliver technology that matters.
          </p>
        </motion.div>

        {/* Cards */}
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-8">
          {services.map((service, i) => (
            <motion.div
              key={service.title}
              className="bg-[#F5F3EE] rounded-2xl p-8 flex flex-col gap-4 hover:shadow-lg transition-shadow"
              initial={{ opacity: 0, y: 30 }}
              whileInView={{ opacity: 1, y: 0 }}
              viewport={{ once: true }}
              transition={{ duration: 0.5, delay: i * 0.1 }}
            >
              <span className="text-4xl">{service.icon}</span>
              <h3
                className="font-extrabold text-[#1E2E52] text-xl"
                style={{ fontFamily: "Syne, sans-serif" }}
              >
                {service.title}
              </h3>
              <p className="text-gray-500 text-sm leading-relaxed">
                {service.description}
              </p>
              <a
                href="#contact"
                className="mt-auto text-[#B5A84B] hover:text-[#D4C96A] text-sm font-semibold transition-colors"
              >
                Learn more →
              </a>
            </motion.div>
          ))}
        </div>
      </div>
    </section>
  );
}
</tool_response>

<tool_call>
{"name": "read_file", "arguments": {"path": "/app/Projects/default/frontend/components/HowWeWork.tsx"}}
</tool_call>
<tool_response>
// components/HowWeWork.tsx
"use client";

import { motion } from "framer-motion";

const steps = [
  {
    number: "01",
    title: "Discover",
    description:
      "We start with deep discovery — understanding your business goals, technical constraints, and user needs.",
  },
  {
    number: "02",
    title: "Architect",
    description:
      "Our engineers and designers collaborate to define the architecture, tech stack, and product roadmap.",
  },
  {
    number: "03",
    title: "Build",
    description:
      "Agile sprints, CI/CD from day one. We ship working software early and iterate fast based on feedback.",
  },
  {
    number: "04",
    title: "Launch & Scale",
    description:
      "We handle deployment, monitoring, and scaling — so your product is production-ready on day one.",
  },
];

export default function HowWeWork() {
  return (
    <section id="how-we-work" className="bg-[#F5F3EE] py-24">
      <div className="max-w-7xl mx-auto section-padding">
        {/* Header */}
        <motion.div
          className="mb-16 text-center"
          initial={{ opacity: 0, y: 30 }}
          whileInView={{ opacity: 1, y: 0 }}
          viewport={{ once: true }}
          transition={{ duration: 0.6 }}
        >
          <span className="inline-block text-[#B5A84B] text-sm font-semibold tracking-widest uppercase mb-4">
            Our Process
          </span>
          <h2
            className="font-extrabold text-[#1E2E52] text-4xl md:text-5xl"
            style={{ fontFamily: "Syne, sans-serif" }}
          >
            How We Work
          </h2>
        </motion.div>

        {/* Steps */}
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-8">
          {steps.map((step, i) => (
            <motion.div
              key={step.number}
              className="relative"
              initial={{ opacity: 0, y: 40 }}
              whileInView={{ opacity: 1, y: 0 }}
              viewport={{ once: true }}
              transition={{ duration: 0.5, delay: i * 0.15 }}
            >
              <div className="bg-white rounded-2xl p-8 h-full flex flex-col gap-4 shadow-sm">
                <span
                  className="text-5xl font-extrabold text-[#B5A84B]/30"
                  style={{ fontFamily: "Syne, sans-serif" }}
                >
                  {step.number}
                </span>
                <h3
                  className="font-extrabold text-[#1E2E52] text-xl"
                  style={{ fontFamily: "Syne, sans-serif" }}
                >
                  {step.title}
                </h3>
                <p className="text-gray-500 text-sm leading-relaxed">
                  {step.description}
                </p>
              </div>
            </motion.div>
          ))}
        </div>
      </div>
    </section>
  );
}
</tool_response>

<tool_call>
{"name": "read_file", "arguments": {"path": "/app/Projects/default/frontend/components/WhoWeAre.tsx"}}
</tool_call>
<tool_response>
// components/WhoWeAre.tsx
"use client";

import Image from "next/image";
import { motion } from "framer-motion";

const values = [
  { icon: "🌍", label: "Pan-African Vision" },
  { icon: "💡", label: "Innovation First" },
  { icon: "🤝", label: "Community-Driven" },
  { icon: "🏆", label: "Excellence Always" },
];

export default function WhoWeAre() {
  return (
    <section id="culture" className="bg-[#1E2E52] py-24">
      <div className="max-w-7xl mx-auto section-padding">
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-16 items-center">
          {/* Left: Text */}
          <motion.div
            initial={{ opacity: 0, x: -40 }}
            whileInView={{ opacity: 1, x: 0 }}
            viewport={{ once: true }}
            transition={{ duration: 0.7 }}
          >
            <span className="inline-block text-[#D4C96A] text-sm font-semibold tracking-widest uppercase mb-6">
              Who We Are
            </span>
            <h2
              className="font-extrabold text-white text-4xl md:text-5xl leading-tight mb-6"
              style={{ fontFamily: "Syne, sans-serif" }}
            >
              Built by diverse talent.
              <br />
              <span className="text-[#D4C96A]">Driven by purpose.</span>
            </h2>
            <p className="text-white/70 text-lg leading-relaxed mb-8">
              Melanin Technologies is a technology consultancy rooted in diversity,
              equity, and excellence. We bring together the brightest minds from
              across the African diaspora and beyond to solve complex problems with
              elegant, scalable solutions.
            </p>

            {/* Values grid */}
            <div className="grid grid-cols-2 gap-4">
              {values.map((v, i) => (
                <motion.div
                  key={v.label}
                  className="flex items-center gap-3"
                  initial={{ opacity: 0, y: 20 }}
                  whileInView={{ opacity: 1, y: 0 }}
                  viewport={{ once: true }}
                  transition={{ duration: 0.5, delay: i * 0.1 }}
                >
                  <span className="text-2xl">{v.icon}</span>
                  <span className="text-white/80 font-medium text-sm">{v.label}</span>
                </motion.div>
              ))}
            </div>
          </motion.div>

          {/* Right: Illustration */}
          <motion.div
            className="relative h-80 lg:h-[480px] rounded-2xl overflow-hidden"
            initial={{ opacity: 0, x: 40 }}
            whileInView={{ opacity: 1, x: 0 }}
            viewport={{ once: true }}
            transition={{ duration: 0.7 }}
          >
            <Image
              src="/illustrations/team.jpg"
              alt="Our team"
              fill
              className="object-cover"
            />
            <div className="absolute inset-0 bg-gradient-to-t from-[#1E2E52]/60 to-transparent" />
          </motion.div>
        </div>
      </div>
    </section>
  );
}
</tool_response>

<tool_call>
{"name": "read_file", "arguments": {"path": "/app/Projects/default/frontend/components/Stack.tsx"}}
</tool_call>
<tool_response>
// components/Stack.tsx
"use client";

import { motion } from "framer-motion";

const categories = [
  {
    label: "Frontend",
    techs: ["React", "Next.js", "TypeScript", "Tailwind CSS", "Vue.js"],
  },
  {
    label: "Backend",
    techs: ["Node.js", "Python", "Go", "GraphQL", "REST APIs"],
  },
  {
    label: "Cloud",
    techs: ["AWS", "GCP", "Azure", "Kubernetes", "Terraform"],
  },
  {
    label: "Data & AI",
    techs: ["PyTorch", "TensorFlow", "Spark", "Airflow", "dbt"],
  },
  {
    label: "Mobile",
    techs: ["React Native", "Flutter", "Swift", "Kotlin"],
  },
  {
    label: "DevOps",
    techs: ["Docker", "GitHub Actions", "ArgoCD", "Prometheus", "Grafana"],
  },
];

export default function Stack() {
  return (
    <section id="stack" className="bg-white py-24">
      <div className="max-w-7xl mx-auto section-padding">
        {/* Header */}
        <motion.div
          className="mb-16 text-center"
          initial={{ opacity: 0, y: 30 }}
          whileInView={{ opacity: 1, y: 0 }}
          viewport={{ once: true }}
          transition={{ duration: 0.6 }}
        >
          <span className="inline-block text-[#B5A84B] text-sm font-semibold tracking-widest uppercase mb-4">
            Technology
          </span>
          <h2
            className="font-extrabold text-[#1E2E52] text-4xl md:text-5xl"
            style={{ fontFamily: "Syne, sans-serif" }}
          >
            Our Stack
          </h2>
          <p className="text-gray-500 mt-4 max-w-xl mx-auto">
            We work with modern, battle-tested technologies — chosen for each
            project's unique needs.
          </p>
        </motion.div>

        {/* Grid */}
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-6">
          {categories.map((cat, i) => (
            <motion.div
              key={cat.label}
              className="bg-[#F5F3EE] rounded-2xl p-6"
              initial={{ opacity: 0, y: 30 }}
              whileInView={{ opacity: 1, y: 0 }}
              viewport={{ once: true }}
              transition={{ duration: 0.5, delay: i * 0.1 }}
            >
              <h3
                className="font-extrabold text-[#1E2E52] text-lg mb-4"
                style={{ fontFamily: "Syne, sans-serif" }}
              >
                {cat.label}
              </h3>
              <div className="flex flex-wrap gap-2">
                {cat.techs.map((tech) => (
                  <span
                    key={tech}
                    className="bg-white text-[#3D5A99] text-xs font-semibold px-3 py-1.5 rounded-full border border-[#3D5A99]/20"
                  >
                    {tech}
                  </span>
                ))}
              </div>
            </motion.div>
          ))}
        </div>
      </div>
    </section>
  );
}
</tool_response>

<tool_call>
{"name": "read_file", "arguments": {"path": "/app/Projects/default/frontend/components/Contact.tsx"}}
</tool_call>
<tool_response>
// components/Contact.tsx
"use client";

import { motion } from "framer-motion";
import { useState } from "react";

export default function Contact() {
  const [form, setForm] = useState({ name: "", email: "", message: "" });
  const [sent, setSent] = useState(false);

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    setSent(true);
  };

  return (
    <section id="contact" className="bg-[#F5F3EE] py-24">
      <div className="max-w-7xl mx-auto section-padding">
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-16 items-start">
          {/* Left: copy */}
          <motion.div
            initial={{ opacity: 0, x: -30 }}
            whileInView={{ opacity: 1, x: 0 }}
            viewport={{ once: true }}
            transition={{ duration: 0.7 }}
          >
            <span className="inline-block text-[#B5A84B] text-sm font-semibold tracking-widest uppercase mb-6">
              Get In Touch
            </span>
            <h2
              className="font-extrabold text-[#1E2E52] text-4xl md:text-5xl leading-tight mb-6"
              style={{ fontFamily: "Syne, sans-serif" }}
            >
              Let's build something
              <br />
              <span className="text-[#B5A84B]">remarkable together.</span>
            </h2>
            <p className="text-gray-600 text-lg leading-relaxed mb-8">
              Whether you have a project in mind, need a technology partner, or
              just want to explore possibilities — we'd love to hear from you.
            </p>
            <div className="flex flex-col gap-3 text-gray-600">
              <a href="mailto:hello@melanintech.io" className="hover:text-[#B5A84B] transition-colors font-medium">
                hello@melanintech.io →
              </a>
              <a href="tel:+1-800-MELANIN" className="hover:text-[#B5A84B] transition-colors font-medium">
                +1-800-MELANIN →
              </a>
            </div>
          </motion.div>

          {/* Right: form */}
          <motion.div
            initial={{ opacity: 0, x: 30 }}
            whileInView={{ opacity: 1, x: 0 }}
            viewport={{ once: true }}
            transition={{ duration: 0.7 }}
          >
            {sent ? (
              <div className="bg-[#6B9E78]/10 border border-[#6B9E78]/30 rounded-2xl p-10 text-center">
                <span className="text-4xl mb-4 block">✅</span>
                <h3 className="font-extrabold text-[#1E2E52] text-2xl mb-2" style={{ fontFamily: "Syne, sans-serif" }}>
                  Message Sent!
                </h3>
                <p className="text-gray-600">We'll be in touch within 1 business day.</p>
              </div>
            ) : (
              <form onSubmit={handleSubmit} className="flex flex-col gap-5">
                <div>
                  <label className="block text-sm font-semibold text-[#1E2E52] mb-2">Name</label>
                  <input
                    type="text"
                    required
                    value={form.name}
                    onChange={(e) => setForm({ ...form, name: e.target.value })}
                    className="w-full bg-white border border-gray-200 rounded-xl px-4 py-3 text-sm focus:outline-none focus:border-[#3D5A99] transition-colors"
                    placeholder="Your full name"
                  />
                </div>
                <div>
                  <label className="block text-sm font-semibold text-[#1E2E52] mb-2">Email</label>
                  <input
                    type="email"
                    required
                    value={form.email}
                    onChange={(e) => setForm({ ...form, email: e.target.value })}
                    className="w-full bg-white border border-gray-200 rounded-xl px-4 py-3 text-sm focus:outline-none focus:border-[#3D5A99] transition-colors"
                    placeholder="your@email.com"
                  />
                </div>
                <div>
                  <label className="block text-sm font-semibold text-[#1E2E52] mb-2">Message</label>
                  <textarea
                    required
                    rows={5}
                    value={form.message}
                    onChange={(e) => setForm({ ...form, message: e.target.value })}
                    className="w-full bg-white border border-gray-200 rounded-xl px-4 py-3 text-sm focus:outline-none focus:border-[#3D5A99] transition-colors resize-none"
                    placeholder="Tell us about your project..."
                  />
                </div>
                <button
                  type="submit"
                  className="bg-[#1E2E52] hover:bg-[#2C4275] text-white font-semibold px-8 py-4 rounded-xl transition-colors text-sm"
                >
                  Send Message →
                </button>
              </form>
            )}
          </motion.div>
        </div>
      </div>
    </section>
  );
}
</tool_response>

<tool_call>
{"name": "read_file", "arguments": {"path": "/app/Projects/default/frontend/components/Footer.tsx"}}
</tool_call>
<tool_response>
// components/Footer.tsx
import Image from "next/image";
import Link from "next/link";

export default function Footer() {
  return (
    <footer className="bg-[#1E2E52] py-12 border-t border-white/10">
      <div className="max-


## Melanin Technologies Design System

### Colors
- Deep Navy #1E2E52 — primary dark backgrounds
- Blue #3D5A99 — section backgrounds, accents
- Blue Dark #2C4275 — nav scroll state, hover
- Gold #B5A84B — primary accent, CTAs
- Gold Light #D4C96A — stat numbers, hover
- Sage #6B9E78 — secondary accent, section tags
- Off White #F5F3EE — cream section backgrounds

### Typography
- Headings: Syne ExtraBold (800)
- Body: Inter Light/Regular (300–400)
- H1: clamp(3.5rem, 6.5rem), tracking -2.5px, line-height 1.02
- H2: clamp(2.2rem, 3rem), tracking -1px, max-width 520px
- Eyebrow tags: 0.68rem semibold, tracking 0.25em, uppercase

### Section Order & Backgrounds
1. Nav — transparent → #1E2E52/95 on scroll
2. Hero — #1E2E52, full viewport
3. Services — white
4. How We Work — #F5F3EE
5. Who We Are — #1E2E52
6. Stack — #3D5A99
7. Contact — white
8. Footer — #1E2E52

### Spacing
- Section padding: py-24 lg:py-32
- Container: max-w-[1200px] mx-auto px-8 lg:px-16

### Buttons
- Primary: bg-[#B5A84B] text-white hover:bg-[#6B9E78] px-8 py-4
- Dark: bg-[#1E2E52] text-white hover:bg-[#B5A84B] px-8 py-4
- All buttons: Inter semibold 0.8rem, include → or ↗ icon, transition 300ms

### Motion
- Section reveals: fade + slide up, 600ms, stagger 100-150ms
- Trigger: -100px from viewport (whileInView, once:true)
- Hover: scale 1.02 on buttons, x-translate 4px on ghost CTAs

### Hard Rules
- No heavy card borders — whitespace separates
- Alternating dark/light sections
- CTAs always include arrows (→ or ↗)
- One primary accent color: #B5A84B
- Fonts: Syne (headings) + Inter (body) only

### Tech Stack
- Next.js + TypeScript, Tailwind CSS, Framer Motion, Lucide React

