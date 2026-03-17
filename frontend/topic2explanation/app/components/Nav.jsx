import Link from "next/link";
import Image from "next/image";
import alystria from "../images/Alystria.png";

export default function Nav() {
  return (
    <div className="mx-4 mt-4">
      <nav className="glass-panel flex flex-col gap-4 rounded-[1.75rem] px-6 py-5 text-white lg:flex-row lg:items-center lg:justify-between">
        <div className="flex items-center gap-4">
          <Image src={alystria} alt="logo" className="h-14 w-14 rounded-full" />
          <div>
            <p className="display-font text-sm uppercase tracking-[0.28em] text-cyan-200/80">
              Generator Studio
            </p>
            <h1 className="text-2xl font-semibold text-white">API Video Lab</h1>
          </div>
        </div>

        <div className="flex flex-wrap items-center gap-3 text-sm font-medium text-slate-200">
          <Link
            href="/"
            className="secondary-button rounded-full px-4 py-2 transition-colors duration-200 hover:text-white"
          >
            Back to landing page
          </Link>
          <span className="glass rounded-full px-4 py-2 text-white/90">
            Customize characters and language
          </span>
          <span className="glass rounded-full px-4 py-2 text-white/90">
            Control tutorial style
          </span>
        </div>
      </nav>
    </div>
  );
}
