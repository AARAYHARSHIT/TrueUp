"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import {
  LayoutDashboard,
  GitMerge,
  AlertTriangle,
  Search,
  Banknote,
  FileText,
  Bot,
  ChevronLeft,
  ChevronRight,
  ExternalLink,
} from "lucide-react";
import { useState } from "react";

const navItems = [
  { href: "/", label: "Overview", icon: LayoutDashboard },
  { href: "/reconcile", label: "Reconcile", icon: GitMerge },
  { href: "/exceptions", label: "Exceptions", icon: AlertTriangle },
  { href: "/transactions", label: "Transactions", icon: Search },
  { href: "/cash", label: "Cash Position", icon: Banknote },
  { href: "/agent", label: "AI Controller", icon: Bot },
  { href: "/reports", label: "Reports", icon: FileText },
];

const links = [
  {
    href: "https://github.com/trueup/trueup",
    label: "GitHub",
    icon: ExternalLink,
  },
  {
    href: "https://github.com/trueup/trueup/blob/main/README.md",
    label: "Documentation",
    icon: ExternalLink,
  },
];

export function Sidebar() {
  const pathname = usePathname();
  const [collapsed, setCollapsed] = useState(false);

  return (
    <aside
      className={`hidden md:flex flex-col border-r border-border bg-card transition-all duration-200 ${
        collapsed ? "w-16" : "w-60"
      }`}
    >
      <div className="flex items-center justify-between px-4 h-14 border-b border-border">
        {!collapsed && (
          <span className="text-sm font-semibold tracking-wide text-foreground">
            TRUEUP
          </span>
        )}
        <button
          onClick={() => setCollapsed(!collapsed)}
          className="p-1 rounded text-muted hover:text-foreground hover:bg-card-hover transition-colors"
          aria-label="Toggle sidebar"
        >
          {collapsed ? (
            <ChevronRight className="h-4 w-4" />
          ) : (
            <ChevronLeft className="h-4 w-4" />
          )}
        </button>
      </div>

      <nav className="flex-1 py-3 space-y-1 px-2">
        {navItems.map((item) => {
          const active =
            item.href === "/"
              ? pathname === "/"
              : pathname === item.href || pathname.startsWith(item.href + "/");
          return (
            <Link
              key={item.href}
              href={item.href}
              className={`flex items-center gap-3 rounded-md px-3 py-2 text-sm transition-colors ${
                active
                  ? "bg-blue-dim text-blue font-medium"
                  : "text-muted hover:text-foreground hover:bg-card-hover"
              } ${collapsed ? "justify-center" : ""}`}
              title={collapsed ? item.label : undefined}
            >
              <item.icon className="h-4 w-4 shrink-0" />
              {!collapsed && <span>{item.label}</span>}
            </Link>
          );
        })}
      </nav>

      {!collapsed && (
        <div className="px-4 py-3 border-t border-border space-y-2">
          {links.map((link) => (
            <a
              key={link.href}
              href={link.href}
              target="_blank"
              rel="noopener noreferrer"
              className="flex items-center gap-2 text-xs text-muted hover:text-foreground transition-colors"
            >
              <link.icon className="h-3 w-3" />
              <span>{link.label}</span>
            </a>
          ))}
          <p className="text-[10px] text-muted leading-tight pt-2">
            AI Finance Controller
          </p>
        </div>
      )}
    </aside>
  );
}
