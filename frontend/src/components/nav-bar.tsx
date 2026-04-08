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
    <header className="sticky top-0 z-40 w-full border-b border-[#E8E8E3] bg-white/80 backdrop-blur-xl">
      <div className="mx-auto flex max-w-7xl items-center justify-between gap-4 px-4 py-3 sm:px-6">
        {/* Logo */}
        <Link
          href={isAuthenticated ? "/dashboard" : "/"}
          className="flex items-center gap-2 font-semibold"
        >
          {/* Luma wordmark with gold glow */}
          <span
            className="text-lg font-bold tracking-tight"
            style={{
              color: "#D4A853",
              textShadow: "0 0 20px rgba(212,168,83,0.3)",
            }}
          >
            Luma
          </span>
          <span className="hidden text-sm font-medium text-[#1A1A1A] sm:inline">Studio</span>
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
                    ? "text-[#D4A853]"
                    : "text-[#737373] hover:text-[#1A1A1A]"
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
                <span className="hidden text-xs text-[#A3A3A3] sm:flex items-center gap-1">
                  <span>{user.credits_used ?? 0} used</span>
                  <span className="opacity-60">(unlimited)</span>
                </span>
              ) : typeof user?.credit_balance === "number" ? (
                <span
                  className={`hidden text-xs font-medium sm:flex items-center gap-1 px-2 py-0.5 rounded-full ${
                    user.credit_balance <= 0
                      ? "bg-red-50 text-red-600"
                      : user.credit_balance <= 20
                      ? "bg-amber-50 text-amber-600"
                      : "bg-[#F5F5F0] text-[#737373]"
                  }`}
                >
                  <span aria-label="credits" style={{ color: "#D4A853" }}>◈</span>
                  <span>{user.credit_balance} credits</span>
                </span>
              ) : null}
              <span className="hidden text-xs text-[#A3A3A3] sm:block">
                {user?.email}
              </span>
              <Button variant="ghost" size="sm" onClick={handleLogout} className="text-[#737373] hover:text-[#1A1A1A]">
                Sign out
              </Button>
            </>
          ) : (
            <a href={`${API_BASE}/api/auth/login`}>
              <Button size="sm" style={{ background: "#D4A853", color: "#FFFFFF" }} className="font-semibold hover:opacity-90">
                Sign in with Google
              </Button>
            </a>
          )}
        </div>
      </div>
    </header>
  );
}
