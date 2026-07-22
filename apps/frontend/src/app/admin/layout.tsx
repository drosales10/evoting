import Link from "next/link";

export default function AdminLayout({ children }: { children: React.ReactNode }) {
  // Login stays outside the dense shell chrome.
  return (
    <div className="min-h-screen bg-[var(--background)]">
      <header className="border-b border-[var(--line)] bg-[var(--surface)]">
        <div className="mx-auto flex max-w-7xl items-center justify-between px-4 py-3 md:px-6">
          <Link href="/" className="brand text-lg font-bold">
            e<span className="text-[var(--primary)]">Voting</span>
          </Link>
          <nav className="flex gap-4 text-sm font-semibold text-[var(--muted)]">
            <Link href="/admin" className="hover:text-[var(--primary)]">
              Comisión
            </Link>
            <Link href="/cliente" className="hover:text-[var(--primary)]">
              Área cliente
            </Link>
          </nav>
        </div>
      </header>
      {children}
    </div>
  );
}
