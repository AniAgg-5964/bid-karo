import { NavLink, useNavigate } from "react-router-dom";
import { useTranslation } from "react-i18next";
import {
  AlarmClock,
  BellRing,
  Building2,
  ChevronRight,
  ClipboardCheck,
  FileText,
  LayoutDashboard,
  Search,
  Settings,
  Sparkles,
} from "lucide-react";

import { Logo } from "../Logo";
import { cn } from "../../lib/utils";

const PRIMARY_NAV = [
  { key: "dashboard", to: "/app/dashboard", icon: LayoutDashboard },
  { key: "discover", to: "/app/discover", icon: Search },
  { key: "tenders", to: "/app/tenders", icon: FileText },
  { key: "checklist", to: "/app/checklist", icon: ClipboardCheck },
  { key: "documents", to: "/app/documents", icon: FileText },
  { key: "changes", to: "/app/changes", icon: BellRing },
  { key: "reminders", to: "/app/reminders", icon: AlarmClock },
];

const ACCOUNT_NAV = [
  { key: "company", to: "/app/company", icon: Building2 },
  { key: "settings", to: "/app/settings", icon: Settings },
];

function NavItem({ item, onNavigate }) {
  const { t } = useTranslation();
  const Icon = item.icon;
  return (
    <NavLink
      to={item.to}
      onClick={onNavigate}
      className={({ isActive }) =>
        cn(
          "group flex items-center gap-2.5 rounded-lg px-2.5 py-[7px] text-[13px] font-medium transition",
          isActive
            ? "bg-teal-50 font-semibold text-teal-700 dark:bg-teal-900/40 dark:text-teal-200"
            : "text-navy-600 hover:bg-navy-50 hover:text-navy-900 dark:text-navy-300 dark:hover:bg-navy-800 dark:hover:text-white",
        )
      }
    >
      {({ isActive }) => (
        <>
          <Icon
            className={cn(
              "h-4 w-4 shrink-0",
              isActive ? "text-teal-600 dark:text-teal-300" : "text-navy-400 group-hover:text-navy-600 dark:text-navy-400 dark:group-hover:text-navy-200",
            )}
            aria-hidden="true"
            strokeWidth={1.9}
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
        "flex h-full w-[212px] shrink-0 flex-col border-r border-navy-100 bg-white dark:border-navy-800 dark:bg-navy-900",
        className,
      )}
    >
      <div className="flex h-16 shrink-0 items-center px-4">
        <Logo />
      </div>

      <div className="flex-1 overflow-y-auto px-2.5 pb-4 pt-1">
        <nav className="space-y-0.5" aria-label={t("nav.workspace")}>
          {PRIMARY_NAV.map((item) => (
            <NavItem key={item.key} item={item} onNavigate={onNavigate} />
          ))}
        </nav>

        <p className="px-2.5 pb-1.5 pt-6 text-[9px] font-bold uppercase tracking-[0.16em] text-navy-400">
          {t("nav.account")}
        </p>
        <nav className="space-y-0.5" aria-label={t("nav.account")}>
          {ACCOUNT_NAV.map((item) => (
            <NavItem key={item.key} item={item} onNavigate={onNavigate} />
          ))}
        </nav>
      </div>

      <div className="m-3 rounded-xl border border-teal-100 bg-teal-50/60 p-3 dark:border-teal-900 dark:bg-teal-950/40">
        <div className="mb-2 flex h-6 w-6 items-center justify-center rounded-md bg-white text-teal-700 shadow-sm dark:bg-navy-900 dark:text-teal-300">
          <Sparkles className="h-3.5 w-3.5" aria-hidden="true" />
        </div>
        <p className="text-[11px] font-medium leading-[1.5] text-navy-700 dark:text-navy-100">
          {t("dashboard.bannerTitle")}
        </p>
        <button
          type="button"
          onClick={() => {
            navigate("/app/discover");
            onNavigate?.();
          }}
          className="mt-1.5 inline-flex items-center gap-0.5 text-[11px] font-bold text-teal-700 hover:text-teal-900 dark:text-teal-300"
        >
          {t("dashboard.discoverCta")}
          <ChevronRight className="h-3 w-3" />
        </button>
      </div>
    </aside>
  );
}
