import type { Metadata } from 'next'
import { Inter } from 'next/font/google'
import './globals.css'

const inter = Inter({
  subsets: ['latin'],
  display: 'swap',
  variable: '--font-inter',
})

export const metadata: Metadata = {
  title: 'Sistema de Bodega',
  description: 'Warehouse Management System - Control de pedidos e inventario',
  icons: {
    icon: "data:image/svg+xml,<svg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 100 100'><text y='.9em' font-size='90'>🏭</text></svg>",
  },
}

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode
}>) {
  return (
    <html lang="es" className={`${inter.variable} dark`}>
      <body
        className="font-sans antialiased min-h-screen"
        style={{ backgroundColor: '#0f172a', color: '#f1f5f9' }}
      >
        {children}
      </body>
    </html>
  )
}
