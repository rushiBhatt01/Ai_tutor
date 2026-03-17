import Link from "next/link";
import { navLinks } from "./landingContent";

export default function Navigation() {
  return (
    <header className="fixed inset-x-0 top-0 z-50 px-4 pt-4 sm:px-6">
      <div className="mx-auto max-w-7xl">
        <div className="glass-panel flex items-center justify-between rounded-full px-4 py-3 sm:px-6">
          <Link
            href="/"
            className="display-font text-sm font-semibold uppercase tracking-[0.35em] text-white sm:text-base"
          >
            API Video Lab
          </Link>

          <nav className="hidden items-center gap-6 text-sm text-slate-300 lg:flex">
            {navLinks.map((link) => (
              <a
                key={link.href}
                href={link.href}
                className="transition-colors duration-200 hover:text-cyan-200"
              >
                {link.label}
              </a>
            ))}
          </nav>

          <Link
            href="/studio"
            className="neon-button rounded-full px-4 py-2 text-sm font-semibold text-slate-950"
          >
            Open Studio
          </Link>
        </div>
      </div>
    </header>
  );
}
