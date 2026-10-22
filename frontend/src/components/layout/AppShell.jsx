import { useEffect, useState } from "react";
import { Outlet, useLocation } from "react-router-dom";

import { Sidebar } from "./Sidebar";
import { Topbar } from "./Topbar";
import { CommandPalette } from "./CommandPalette";

export function AppShell() {
  const [mobileOpen, setMobileOpen] = useState(false);
  const [searchOpen, setSearchOpen] = useState(false);
  const location = useLocation();

  useEffect(() => {
    setMobileOpen(false);
    window.scrollTo({ top: 0, behavior: "instant" });
  }, [location.pathname]);

  // Ctrl/Cmd+K opens the search. It is a shortcut, not the only way in: the
  // button in the top bar does the same thing.
  useEffect(() => {
    const onKey = (event) => {
      if ((event.metaKey || event.ctrlKey) && event.key.toLowerCase() === "k") {
        event.preventDefault();
        setSearchOpen((value) => !value);
      }
    };
    document.addEventListener("keydown", onKey);
    return () => document.removeEventListener("keydown", onKey);
  }, []);

  return (
    <div className="min-h-screen bg-mist dark:bg-navy-950">
      <div className="hidden lg:fixed lg:inset-y-0 lg:left-0 lg:z-40 lg:block">
        <Sidebar />
      </div>

      {mobileOpen ? (
        <div className="fixed inset-0 z-50 lg:hidden">
          <button
            type="button"
            className="absolute inset-0 bg-navy-950/45 backdrop-blur-[2px]"
            aria-label="Close navigation"
            onClick={() => setMobileOpen(false)}
          />
          <div className="relative h-full w-[260px] max-w-[82vw] animate-fade-in shadow-pop">
            <Sidebar onNavigate={() => setMobileOpen(false)} />
          </div>
        </div>
      ) : null}

      <div className="lg:pl-[240px]">
        <Topbar onMenu={() => setMobileOpen(true)} onOpenSearch={() => setSearchOpen(true)} />
        <main className="mx-auto w-full max-w-[1440px] px-4 py-6 sm:px-6 lg:px-8 lg:py-8">
          <Outlet />
        </main>
      </div>

      <CommandPalette open={searchOpen} onClose={() => setSearchOpen(false)} />
    </div>
  );
}
