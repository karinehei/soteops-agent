"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import type { ReactNode } from "react";

import { useAuth } from "@/lib/auth-context";

export function AppShell({ children }: { children: ReactNode }) {
  const pathname = usePathname();
  const { user, loading, logout } = useAuth();
  const hideNav = pathname === "/login";

  return (
    <>
      <a className="skip-link" href="#main-content">
        Siirry pääsisältöön
      </a>
      {!hideNav && (
        <header className="site-header" role="banner">
          <div className="site-header__inner">
            <Link className="brand" href="/">
              SoteOps Agent
            </Link>
            <nav className="site-nav" aria-label="Päävalikko">
              <Link href="/" aria-current={pathname === "/" ? "page" : undefined}>
                Aloitus
              </Link>
              {(user?.role === "requester" || user?.role === "operator") && (
                <Link href="/requests" aria-current={pathname.startsWith("/requests") ? "page" : undefined}>
                  {user.role === "requester" ? "Omat pyynnöt" : "Pyynnöt"}
                </Link>
              )}
              {user?.role === "reviewer" && (
                <Link href="/review" aria-current={pathname.startsWith("/review") ? "page" : undefined}>
                  Tarkastusjono
                </Link>
              )}
            </nav>
            <div className="site-header__user">
              {loading ? (
                <span className="muted" aria-live="polite">
                  Ladataan…
                </span>
              ) : user ? (
                <>
                  <span className="user-chip" data-testid="current-user">
                    {user.display_name} ({user.role})
                  </span>
                  <button type="button" className="btn btn--ghost" onClick={() => void logout()}>
                    Kirjaudu ulos
                  </button>
                </>
              ) : (
                <Link className="btn btn--ghost" href="/login">
                  Kirjaudu
                </Link>
              )}
            </div>
          </div>
        </header>
      )}
      <div id="main-content">{children}</div>
    </>
  );
}
