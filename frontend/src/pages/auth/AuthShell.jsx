import { useTranslation } from "react-i18next";
import { CheckCircle2, FileSearch, ShieldCheck, Sparkles } from "lucide-react";

import { Logo } from "../../components/Logo";
import { LanguageSwitch } from "../../components/LanguageSwitch";
import { ThemeToggle } from "../../components/ThemeToggle";

const FEATURES = [
  { key: "feature1", icon: FileSearch },
  { key: "feature2", icon: Sparkles },
  { key: "feature3", icon: CheckCircle2 },
];

export function AuthShell({ title, subtitle, children, footer }) {
  const { t } = useTranslation();

  return (
    <div className="relative min-h-screen bg-mist dark:bg-navy-950 lg:grid lg:grid-cols-[1.05fr_1fr]">
      <div className="absolute right-4 top-4 z-20 flex items-center gap-2">
        <LanguageSwitch compact />
        <ThemeToggle />
      </div>

      <aside className="relative hidden overflow-hidden bg-navy-900 px-12 py-10 lg:flex lg:flex-col">
        <div className="absolute -right-24 -top-24 h-72 w-72 rounded-full bg-teal-500/10 blur-3xl" />
        <div className="absolute -bottom-32 -left-20 h-80 w-80 rounded-full bg-teal-400/10 blur-3xl" />
        <div
          className="absolute inset-0 opacity-[0.035]"
          style={{
            backgroundImage:
              "linear-gradient(#fff 1px, transparent 1px), linear-gradient(90deg, #fff 1px, transparent 1px)",
            backgroundSize: "36px 36px",
          }}
          aria-hidden="true"
        />

        <div className="relative">
          <Logo light />
        </div>

        <div className="relative mt-auto mb-auto max-w-lg py-14">
          <p className="mb-4 inline-flex items-center gap-2 rounded-full border border-teal-400/30 bg-teal-400/10 px-3 py-1.5 text-[11px] font-semibold uppercase tracking-[0.14em] text-teal-200">
            <ShieldCheck className="h-3.5 w-3.5" />
            {t("auth.secureNote")}
          </p>
          <h1 className="text-4xl font-semibold leading-[1.15] tracking-tight text-white">
            {t("common.tagline")}
          </h1>
          <p className="mt-4 max-w-md text-sm leading-6 text-navy-200">{t("auth.termsNote")}</p>

          <ul className="mt-9 space-y-4">
            {FEATURES.map(({ key, icon: Icon }) => (
              <li key={key} className="flex items-start gap-3 text-sm text-navy-100">
                <span className="mt-0.5 flex h-7 w-7 shrink-0 items-center justify-center rounded-lg bg-white/10 text-teal-300">
                  <Icon className="h-4 w-4" aria-hidden="true" />
                </span>
                <span className="pt-1">{t(`auth.${key}`)}</span>
              </li>
            ))}
          </ul>

          <div className="mt-12 rounded-2xl border border-white/10 bg-white/[0.04] p-4">
            <p className="text-[10px] font-bold uppercase tracking-[0.16em] text-teal-300">
              Source traceability
            </p>
            <p className="mt-2 text-sm leading-6 text-navy-200">
              Every tender requirement keeps its source document, page, clause and excerpt — or is
              clearly marked unverified.
            </p>
          </div>
        </div>

        <p className="relative text-xs text-navy-400">
          © {new Date().getFullYear()} BidKaro · Built for Indian public procurement
        </p>
      </aside>

      <main className="flex min-h-screen items-center justify-center px-4 py-20 sm:px-8">
        <div className="w-full max-w-[420px] animate-fade-in">
          <div className="mb-9 lg:hidden">
            <Logo />
          </div>
          <h2 className="text-2xl font-semibold tracking-tight text-navy-900 dark:text-white">{title}</h2>
          <p className="mt-2 text-sm muted">{subtitle}</p>
          <div className="mt-8">{children}</div>
          {footer ? <div className="mt-6 text-sm muted">{footer}</div> : null}
          <p className="mt-10 flex items-start gap-2 text-[11px] leading-5 text-navy-400">
            <ShieldCheck className="mt-0.5 h-3.5 w-3.5 shrink-0" />
            {t("auth.termsNote")}
          </p>
        </div>
      </main>
    </div>
  );
}
