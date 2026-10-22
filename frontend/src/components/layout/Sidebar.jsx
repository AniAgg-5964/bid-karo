import { NavLink, useNavigate } from "react-router-dom";
import { useTranslation } from "react-i18next";
import {
  AlarmClock,
  BellRing,
  Building2,
  ChevronRight,
  ClipboardCheck,
  Compass,
  FileText,
  LayoutDashboard,
  Search,
  Settings,
  Sparkles,
} from "lucide-react";

import { Logo } from "../Logo";
import { cn } from "../../lib/utils";

/*
  The global navigation is organised by what a person is trying to do, not by
  the order the screens were written in. Every destination here is a route
  that already exists and works.
*/
const WORKSPACE_NAV = [
  { key: "dashboard", to: "/app/dashboard", icon: LayoutDashboard },
  { key: "discover", to: "/app/discover", icon: Compass },
  { key: "tenders", to: "/app/tenders", icon: FileText },
  { key: "checklist", to: "/app/checklist", icon: ClipboardCheck },
  { key: "documents", to: "/app/documents", icon: FileText },
  { key: "changes", to: "/app/changes", icon: BellRing },
];

const ACCOUNT_NAV = [
  { key: "company", to: "/app/company", icon: Building2 },
  { key: "settings", to: "/app/settings", icon: Settings },
];

function NavItem({ item, onNavigate, nested = false }) {
  const { t } = useTranslation();
  const Icon = item.icon;
  return (
    <NavLink
      to={item.to}
      onClick={onNavigate}
      className={({ isActive }) =>
        cn(
          "group relative flex items-center gap-3 rounded-lg py-2 text-[13px] font-medium transition-colors",
          nested ? "pl-9 pr-3" : "px-3",
          isActive
            ? "bg-white/10 text-white"
            : "text-navy-200 hover:bg-white/[0.06] hover:text-white",
        )
      }
    >
      {({ isActive }) => (
        <>
          {isActive ? (
            <span
              className="absolute left-0 top-1/2 h-5 w-[3px] -translate-y-1/2 rounded-r-full bg-teal-400"
              aria-hidden="true"
            />
          ) : null}
          <Icon
            className={cn(
              "h-[17px] w-[17px] shrink-0",
              isActive ? "text-teal-300" : "text-navy-400 group-hover:text-navy-200",
            )}
            aria-hidden="true"
          />
          <span className="flex-1 truncate">{t(`nav.${item.key}`)}</span>
        </>
      )}
    </NavLink>
  );
}

export function Sidebar({ onNavigate, className }) {
  const { t } = useTranslation();
  const navigate = useNavigate();

  return (
    <aside
      className={cn(
        "flex h-full w-[240px] shrink-0 flex-col bg-navy-900 text-navy-100",
        className,
      )}
    >
      <div className="px-5 pb-5 pt-6">
        <Logo light />
      </div>

      <div className="flex-1 overflow-y-auto px-3 pb-4">
        <p className="px-3 pb-2 text-[10px] font-bold uppercase tracking-[0.18em] text-navy-500 dark:text-navy-300">
          {t("nav.workspace")}
        </p>
        <nav className="space-y-0.5" aria-label={t("nav.workspace")}>
          {WORKSPACE_NAV.map((item) => (
            <NavItem key={item.key} item={item} onNavigate={onNavigate} />
          ))}
          {/* Reminders live under the changes and alerts destination, which
              already exists and works. */}
          <NavItem
            item={{ key: "reminders", to: "/app/reminders", icon: AlarmClock }}
            onNavigate={onNavigate}
            nested
          />
        </nav>

        <p className="px-3 pb-2 pt-7 text-[10px] font-bold uppercase tracking-[0.18em] text-navy-500 dark:text-navy-300">
          {t("nav.account")}
        </p>
        <nav className="space-y-0.5" aria-label={t("nav.account")}>
          {ACCOUNT_NAV.map((item) => (
            <NavItem key={item.key} item={item} onNavigate={onNavigate} />
          ))}
        </nav>
      </div>

      <div className="m-3 rounded-xl border border-white/10 bg-white/[0.04] p-3.5">
        <div className="mb-2 flex h-7 w-7 items-center justify-center rounded-lg bg-teal-600/20 text-teal-300">
          <Sparkles className="h-3.5 w-3.5" aria-hidden="true" />
        </div>
        <p className="text-xs font-semibold leading-5 text-white">
          {t("dashboard.bannerTitle")}
        </p>
        <button
          type="button"
          onClick={() => {
            navigate("/app/discover");
            onNavigate?.();
          }}
          className="mt-2 inline-flex items-center gap-1 text-[11px] font-bold text-teal-300 transition hover:text-teal-200"
        >
          {t("dashboard.bannerCta")}
          <ChevronRight className="h-3 w-3" aria-hidden="true" />
        </button>
      </div>
    </aside>
  );
}
