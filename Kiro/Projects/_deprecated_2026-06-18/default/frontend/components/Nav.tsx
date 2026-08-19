// components/Nav.tsx
'use client'

import Image from 'next/image'
import Link from 'next/link'
import { useState } from 'react'

export default function Nav() {
  const [open, setOpen] = useState(false)

  const links = [
    { href: '#services', label: 'Services' },
    { href: '#how-we-work', label: 'How We Work' },
    { href: '#culture', label: 'Culture' },
    { href: '#stack', label: 'Stack' },
    { href: '#contact', label: 'Contact' },
  ]

  return (
    <nav className="fixed top-0 left-0 right-0 z-50 bg-[#1E2E52]/95 backdrop-blur-sm border-b border-white/10">
      <div className="max-w-7xl mx-auto px-6 lg:px-12 flex items-center justify-between h-16">
        {/* Logo */}
        <Link href="/" className="flex items-center gap-3">
          <Image
            src="/logo.png"
            alt="Melanin Technologies Logo"
            width={36}
            height={36}
            className="object-contain"
          />
          <span
            className="text-white font-extrabold text-lg tracking-tight"
            style={{ fontFamily: 'Syne, sans-serif' }}
          >
            Melanin Technologies
          </span>
        </Link>

        {/* Desktop links */}
        <ul className="hidden md:flex items-center gap-8">
          {links.map((l) => (
            <li key={l.href}>
              <Link
                href={l.href}
                className="text-white/80 hover:text-[#D4C96A] text-sm font-medium transition-colors duration-200"
              >
                {l.label}
              </Link>
            </li>
          ))}
        </ul>

        {/* CTA */}
        <Link
          href="#contact"
          className="hidden md:inline-flex items-center px-5 py-2 rounded-full bg-[#B5A84B] hover:bg-[#D4C96A] text-[#1E2E52] text-sm font-semibold transition-colors duration-200"
        >
          Let's Talk
        </Link>

        {/* Mobile hamburger */}
        <button
          className="md:hidden text-white p-2"
          onClick={() => setOpen(!open)}
          aria-label="Toggle menu"
        >
          <span className="block w-6 h-0.5 bg-white mb-1.5" />
          <span className="block w-6 h-0.5 bg-white mb-1.5" />
          <span className="block w-6 h-0.5 bg-white" />
        </button>
      </div>

      {/* Mobile menu */}
      {open && (
        <div className="md:hidden bg-[#1E2E52] border-t border-white/10 px-6 py-4">
          <ul className="flex flex-col gap-4">
            {links.map((l) => (
              <li key={l.href}>
                <Link
                  href={l.href}
                  onClick={() => setOpen(false)}
                  className="text-white/80 hover:text-[#D4C96A] text-sm font-medium transition-colors"
                >
                  {l.label}
                </Link>
              </li>
            ))}
          </ul>
          <Link
            href="#contact"
            onClick={() => setOpen(false)}
            className="mt-4 inline-flex items-center px-5 py-2 rounded-full bg-[#B5A84B] hover:bg-[#D4C96A] text-[#1E2E52] text-sm font-semibold transition-colors"
          >
            Let's Talk
          </Link>
        </div>
      )}
    </nav>
  )
}