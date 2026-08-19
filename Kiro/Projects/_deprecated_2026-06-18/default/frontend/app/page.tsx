// app/page.tsx
import Nav from '@/components/Nav'
import Hero from '@/components/Hero'
import Services from '@/components/Services'
import HowWeWork from '@/components/HowWeWork'
import Culture from '@/components/Culture'
import Stack from '@/components/Stack'
import Contact from '@/components/Contact'
import Footer from '@/components/Footer'

export default function Home() {
  return (
    <main>
      <Nav />
      <Hero />
      <Services />
      <HowWeWork />
      <Culture />
      <Stack />
      <Contact />
      <Footer />
    </main>
  )
}