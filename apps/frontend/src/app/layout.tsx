import type { Metadata } from "next";
import Link from "next/link";
import type { ReactNode } from "react";

import "./globals.css";

export const metadata: Metadata = {
  title: "eVoting",
  description: "Plataforma de votación electrónica verificable",
};

export default function RootLayout({ children }: Readonly<{ children: ReactNode }>) {
  return (
    <html lang="es">
      <body>
        <header className="site-header">
          <Link className="brand" href="/">
            e<span>Voting</span>
          </Link>
          <nav aria-label="Navegación principal">
            <Link href="/elections">Elecciones</Link>
            <Link href="/vote">Votar</Link>
            <Link href="/admin">Comisión</Link>
          </nav>
        </header>
        <main>{children}</main>
        <footer className="site-footer">Base inicial · identidad y urna se mantienen separadas</footer>
      </body>
    </html>
  );
}
