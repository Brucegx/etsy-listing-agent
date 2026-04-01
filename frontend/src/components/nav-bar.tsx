"use client";

import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import { useAuth } from "@/lib/auth";
import { api, API_BASE } from "@/lib/api";
import { Button } from "@/components/ui/button";
import { cn } from "@/lib/utils";

interface NavItem {
  label: string;
  href: string;
}

const NAV_ITEMS: NavItem[] = [
  { label: "Home", href: "/" },
  { label: "Jobs", href: "/jobs" },
];

export function NavBar() {
  const { user, isAuthenticated } = useAuth();
  const pathname = usePathname();
  const router = useRouter();

  const handleLogout = async () => {
    await api.auth.logout().catch(() => null);
    router.push("/");
    router.refresh();
  };

  return (
    <header className="sticky top-0 z-40 w-full border-b border-border/60 bg-background/80 backdrop-blur-md">
      <div className="mx-auto flex max-w-7xl items-center justify-between gap-4 px-4 py-3 sm:px-6">
        {/* Logo */}
        <Link
          href={isAuthenticated ? "/dashboard" : "/"}
          className="flex items-center gap-2 font-semibold text-foreground"
        >
          {/* Tiny amber spark icon */}
          <span
            className="flex h-7 w-7 items-center justify-center rounded-lg text-sm"
            style={{
              background: "oklch(0.62 0.17 48)",
              color: "white",
            }}
            aria-hidden="true"
          >
            ✦
          </span>
          <span className="hidden sm:inline">Etsy Listing Agent</span>
          <span className="sm:hidden">ELA</span>
        </Link>

        {/* Nav links (authenticated only) */}
        {isAuthenticated && (
          <nav className="hidden items-center gap-1 md:flex" aria-label="Main navigation">
            {NAV_ITEMS.map((item) => (
              <Link
                key={item.href}
                href={item.href}
                className={cn(
                  "rounded-md px-3 py-1.5 text-sm font-medium transition-colors",
                  pathname === item.href || (item.href !== "/" && pathname.startsWith(item.href + "/"))
                    ? "bg-accent text-accent-foreground"
                    : "text-muted-foreground hover:bg-muted hover:text-foreground"
                )}
              >
                {item.label}
              </Link>
            ))}
          </nav>
        )}

        {/* Right side */}
        <div className="flex items-center gap-2">
          {isAuthenticated ? (
            <>
              {/* Credit balance display */}
              {user?.is_admin ? (
                <span className="hidden text-xs text-muted-foreground sm:flex items-center gap-1">
                  <span className="opacity-60">{user.credits_used ?? 0} used</span>
                  <span className="opacity-40">(unlimited)</span>
                </span>
              ) : typeof user?.credit_balance === "number" ? (
                <span
                  className={`hidden text-xs font-medium sm:flex items-center gap-1 px-2 py-0.5 rounded-full ${
                    user.credit_balance <= 0
                      ? "bg-red-100 text-red-600 dark:bg-red-950/50 dark:text-red-400"
                      : user.credit_balance <= 20
                      ? "bg-orange-100 text-orange-600 dark:bg-orange-950/50 dark:text-orange-400"
                      : "bg-gray-100 text-gray-600 dark:bg-gray-800 dark:text-gray-400"
                  }`}
                >
                  <span aria-label="credits">💰</span>
                  <span>{user.credit_balance} credits</span>
                </span>
              ) : null}
              <span className="hidden text-xs text-muted-foreground sm:block">
                {user?.email}
              </span>
              <Button variant="ghost" size="sm" onClick={handleLogout}>
                Sign out
              </Button>
            </>
          ) : (
            <a href={`${API_BASE}/api/auth/login`}>
              <Button size="sm">Sign in with Google</Button>
            </a>
          )}
        </div>
      </div>
    </header>
  );
}
