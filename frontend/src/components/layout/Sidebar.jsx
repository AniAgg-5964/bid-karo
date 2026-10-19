import { NavLink, useNavigate } from "react-router-dom";
import { useTranslation } from "react-i18next";
import {
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
          "group flex items-center gap-3 rounded-xl px-3 py-2.5 text-sm font-medium transition",
          isActive
            ? "bg-teal-50 text-teal-800 shadow-[inset_2px_0_0_0] shadow-teal-600 dark:bg-teal-950/60 dark:text-teal-200"
            : "text-navy-600 hover:bg-navy-50 hover:text-navy-900 dark:text-navy-300 dark:hover:bg-navy-800 dark:hover:text-white",
        )
      }
    >
      <Icon className="h-[18px] w-[18px] shrink-0" aria-hidden="true" />
      <span className="flex-1 truncate">{t(`nav.${item.key}`)}</span>
    </NavLink>
  );
}

export function Sidebar({ onNavigate, className }) {
  const { t } = useTranslation();
  const navigate = useNavigate();

  return (
    <aside
      className={cn(
        "flex h-full w-[260px] shrink-0 flex-col border-r border-navy-100 bg-white dark:border-navy-800 dark:bg-navy-900",
        className,
      )}
    >
      <div className="px-5 pb-4 pt-5">
        <Logo />
      </div>

      <div className="flex-1 overflow-y-auto px-3 pb-4">
        <p className="px-3 pb-2 pt-2 text-[10px] font-bold uppercase tracking-[0.16em] text-navy-400">
          {t("nav.workspace")}
        </p>
        <nav className="space-y-0.5" aria-label={t("nav.workspace")}>
          {PRIMARY_NAV.map((item) => (
            <NavItem key={item.key} item={item} onNavigate={onNavigate} />
          ))}
        </nav>

        <p className="px-3 pb-2 pt-6 text-[10px] font-bold uppercase tracking-[0.16em] text-navy-400">
          {t("nav.account")}
        </p>
        <nav className="space-y-0.5" aria-label={t("nav.account")}>
          {ACCOUNT_NAV.map((item) => (
            <NavItem key={item.key} item={item} onNavigate={onNavigate} />
          ))}
        </nav>
      </div>

      <div className="m-3 rounded-2xl border border-teal-100 bg-gradient-to-br from-teal-50 to-white p-3.5 dark:border-teal-900 dark:from-teal-950 dark:to-navy-900">
        <div className="mb-2 flex h-7 w-7 items-center justify-center rounded-lg bg-teal-700 text-white">
          <Sparkles className="h-3.5 w-3.5" aria-hidden="true" />
        </div>
        <p className="text-xs font-semibold leading-5 text-navy-900 dark:text-white">
          {t("dashboard.bannerTitle")}
        </p>
        <button
          type="button"
          onClick={() => {
            navigate("/app/discover");
            onNavigate?.();
          }}
          className="mt-2 inline-flex items-center gap-1 text-[11px] font-bold text-teal-700 hover:text-teal-900 dark:text-teal-300"
        >
          {t("dashboard.bannerCta")}
          <ChevronRight className="h-3 w-3" />
        </button>
      </div>
    </aside>
  );
}
