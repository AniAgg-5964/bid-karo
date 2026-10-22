import { useEffect, useRef, useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { useTranslation } from "react-i18next";
import { Bell, ChevronDown, LogOut, Menu, Search, Settings, UserRound } from "lucide-react";

import { useAuth } from "../../contexts/AuthContext";
import { LanguageSwitch } from "../LanguageSwitch";
import { ThemeToggle } from "../ThemeToggle";
import { cn, initials } from "../../lib/utils";

export function Topbar({ onMenu, onOpenSearch }) {
  const { t } = useTranslation();
  const navigate = useNavigate();
  const { session, logout } = useAuth();
  const [openMenu, setOpenMenu] = useState(null);
  const containerRef = useRef(null);

  useEffect(() => {
    const onPointerDown = (event) => {
      if (!containerRef.current?.contains(event.target)) setOpenMenu(null);
    };
    const onKeyDown = (event) => {
      if (event.key === "Escape") setOpenMenu(null);
    };
    document.addEventListener("pointerdown", onPointerDown);
    document.addEventListener("keydown", onKeyDown);
    return () => {
      document.removeEventListener("pointerdown", onPointerDown);
      document.removeEventListener("keydown", onKeyDown);
    };
  }, []);

  const handleLogout = () => {
    logout();
    navigate("/login", { replace: true });
  };

  return (
    <header className="sticky top-0 z-40 border-b border-navy-100 bg-white/90 backdrop-blur dark:border-navy-800 dark:bg-navy-900/90">
      <div ref={containerRef} className="flex h-16 items-center gap-3 px-4 sm:px-6">
        <button
          type="button"
          onClick={onMenu}
          className="inline-flex h-9 w-9 items-center justify-center rounded-lg text-navy-600 hover:bg-navy-100 dark:text-navy-300 dark:hover:bg-navy-800 lg:hidden"
          aria-label="Open navigation"
        >
          <Menu className="h-5 w-5" />
        </button>

        <button
          type="button"
          onClick={onOpenSearch}
          className="group hidden h-9 max-w-sm flex-1 items-center gap-2.5 rounded-xl border border-navy-200 bg-navy-50/60 px-3 text-left text-sm text-navy-500 transition hover:border-navy-300 hover:bg-white focus-visible:ring-2 focus-visible:ring-teal-600 dark:border-navy-700 dark:bg-navy-800 dark:text-navy-300 dark:hover:border-navy-600 dark:hover:bg-navy-900 sm:flex"
        >
          <Search className="h-4 w-4 shrink-0" aria-hidden="true" />
          <span className="flex-1 truncate">{t("palette.placeholder")}</span>
          <kbd className="hidden shrink-0 rounded border border-navy-200 bg-white px-1.5 py-0.5 text-[10px] font-semibold text-navy-500 group-hover:border-navy-300 dark:border-navy-600 dark:bg-navy-900 dark:text-navy-300 lg:inline">
            Ctrl K
          </kbd>
        </button>

        <button
          type="button"
          onClick={onOpenSearch}
          className="inline-flex h-9 w-9 items-center justify-center rounded-lg text-navy-600 transition hover:bg-navy-100 dark:text-navy-300 dark:hover:bg-navy-800 sm:hidden"
          aria-label={t("palette.title")}
        >
          <Search className="h-4 w-4" aria-hidden="true" />
        </button>

        <div className="ml-auto flex items-center gap-1.5 sm:gap-2">
          <LanguageSwitch compact className="hidden sm:inline-flex" />
          <ThemeToggle />

          <div className="relative">
            <button
              type="button"
              onClick={() => setOpenMenu((current) => (current === "notifications" ? null : "notifications"))}
              className="relative inline-flex h-9 w-9 items-center justify-center rounded-lg border border-navy-200 bg-white text-navy-600 transition hover:bg-navy-50 dark:border-navy-700 dark:bg-navy-900 dark:text-navy-300 dark:hover:bg-navy-800"
              aria-label={t("common.notifications")}
              aria-expanded={openMenu === "notifications"}
            >
              <Bell className="h-4 w-4" />
              <span className="absolute right-2 top-2 h-1.5 w-1.5 rounded-full bg-teal-500" />
            </button>
            {openMenu === "notifications" ? (
              <div className="absolute right-0 mt-2 w-72 rounded-xl border border-navy-100 bg-white p-3 shadow-pop animate-fade-in dark:border-navy-700 dark:bg-navy-900">
                <p className="px-1 text-xs font-semibold uppercase tracking-wide text-navy-500 dark:text-navy-300">
                  {t("common.notifications")}
                </p>
                <p className="mt-3 rounded-lg bg-navy-50 px-3 py-4 text-center text-sm muted dark:bg-navy-800">
                  {t("inbox.empty")}
                </p>
                <Link
                  to="/app/changes"
                  onClick={() => setOpenMenu(null)}
                  className="mt-2 block rounded-lg px-3 py-2 text-center text-xs font-semibold text-teal-700 hover:bg-teal-50 dark:text-teal-300 dark:hover:bg-teal-950"
                >
                  {t("nav.changes")}
                </Link>
              </div>
            ) : null}
          </div>

          <div className="relative">
            <button
              type="button"
              onClick={() => setOpenMenu((current) => (current === "user" ? null : "user"))}
              className="flex items-center gap-2 rounded-xl border border-transparent p-1 pr-1.5 transition hover:border-navy-200 hover:bg-navy-50 dark:hover:border-navy-700 dark:hover:bg-navy-800"
              aria-label={[
                initials(session?.user?.full_name),
                session?.user?.full_name,
                session?.company?.name,
                t("common.profile"),
              ]
                .filter(Boolean)
                .join(" ")}
              aria-expanded={openMenu === "user"}
            >
              <span
                aria-hidden="true"
                className="flex h-8 w-8 items-center justify-center rounded-lg bg-navy-900 text-xs font-bold text-white dark:bg-teal-600"
              >
                {initials(session?.user?.full_name)}
              </span>{" "}
              <span className="hidden text-left md:block">
                <span className="block max-w-[130px] truncate text-xs font-semibold text-navy-900 dark:text-white">
                  {session?.user?.full_name}
                </span>{" "}
                <span
                  aria-hidden="true"
                  className="block max-w-[130px] truncate text-[10px] text-navy-500 dark:text-navy-300"
                >
                  {session?.company?.name}
                </span>
              </span>
              <ChevronDown className="hidden h-3.5 w-3.5 text-navy-400 md:block" />
            </button>

            {openMenu === "user" ? (
              <div className="absolute right-0 mt-2 w-60 rounded-xl border border-navy-100 bg-white p-2 shadow-pop animate-fade-in dark:border-navy-700 dark:bg-navy-900">
                <div className="border-b border-navy-100 px-3 py-2 dark:border-navy-800">
                  <p className="truncate text-sm font-semibold text-navy-900 dark:text-white">
                    {session?.user?.full_name}
                  </p>
                  <p className="truncate text-xs muted">{session?.user?.email}</p>
                </div>
                <Link
                  to="/app/company"
                  onClick={() => setOpenMenu(null)}
                  className="mt-1 flex items-center gap-2 rounded-lg px-3 py-2 text-sm text-navy-700 hover:bg-navy-50 dark:text-navy-200 dark:hover:bg-navy-800"
                >
                  <UserRound className="h-4 w-4" />
                  {t("common.profile")}
                </Link>
                <Link
                  to="/app/settings"
                  onClick={() => setOpenMenu(null)}
                  className="flex items-center gap-2 rounded-lg px-3 py-2 text-sm text-navy-700 hover:bg-navy-50 dark:text-navy-200 dark:hover:bg-navy-800"
                >
                  <Settings className="h-4 w-4" />
                  {t("nav.settings")}
                </Link>
                <button
                  type="button"
                  onClick={handleLogout}
                  className={cn(
                    "flex w-full items-center gap-2 rounded-lg px-3 py-2 text-left text-sm text-red-600 hover:bg-red-50 dark:text-red-400 dark:hover:bg-red-950",
                  )}
                >
                  <LogOut className="h-4 w-4" />
                  {t("common.signOut")}
                </button>
              </div>
            ) : null}
          </div>
        </div>
      </div>
    </header>
  );
}
