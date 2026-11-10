"use client";
import Link from "next/link";
import { usePathname } from "next/navigation";
import { useState } from "react";
import {
  LayoutDashboard,
  Files,
  FilePlus2,
  UserRound,
  Menu,
} from "lucide-react";
import { Brand } from "./brand";
import {
  Sheet,
  SheetContent,
  SheetTitle,
  SheetDescription,
  SheetTrigger,
} from "@/components/ui/sheet";
import { Button } from "@/components/ui/button";
import { LogoutButton } from "@/features/auth/logout-button";
import type { User } from "@/lib/contracts";

const links = [
  { href: "/painel", label: "Painel", icon: LayoutDashboard },
  { href: "/curriculos", label: "Currículos", icon: Files },
  { href: "/curriculos/novo", label: "Novo currículo", icon: FilePlus2 },
  { href: "/conta", label: "Conta", icon: UserRound },
];
function Navigation({ path, close }: { path: string; close: () => void }) {
  return (
    <nav aria-label="Navegação principal" className="navigation">
      {links.map(({ href, label, icon: Icon }) => {
        const active =
          href === "/curriculos"
            ? path.startsWith(href) && path !== "/curriculos/novo"
            : path === href;
        return (
          <Link
            key={href}
            href={href}
            aria-current={active ? "page" : undefined}
            onClick={close}
          >
            <Icon aria-hidden="true" size={18} strokeWidth={1.5} />
            {label}
          </Link>
        );
      })}
    </nav>
  );
}
function Account({ user }: { user: User }) {
  return (
    <div className="sidebar-account">
      <span className="text-xs text-muted-foreground">Sua conta</span>
      <span className="account-name">{user.username}</span>
      <LogoutButton />
    </div>
  );
}
export function AppShell({
  user,
  children,
}: {
  user: User;
  children: React.ReactNode;
}) {
  const path = usePathname();
  const [open, setOpen] = useState(false);
  return (
    <div className="app-shell">
      <a href="#conteudo" className="skip-link">
        Pular para o conteúdo
      </a>
      <aside className="desktop-sidebar">
        <Brand />
        <p className="workspace-label">Espaço pessoal</p>
        <Navigation path={path} close={() => setOpen(false)} />
        <div className="sidebar-note">
          Seu currículo, com revisão
          <br />
          em cada etapa.
        </div>
        <Account user={user} />
      </aside>
      <header className="mobile-header">
        <Brand />
        <Sheet open={open} onOpenChange={setOpen}>
          <SheetTrigger asChild>
            <Button variant="ghost" aria-label="Abrir menu">
              <Menu aria-hidden="true" />
              Menu
            </Button>
          </SheetTrigger>
          <SheetContent>
            <SheetTitle className="text-base font-medium pr-12">
              Navegação
            </SheetTitle>
            <SheetDescription className="mt-1 text-sm text-muted-foreground">
              Seu espaço de currículos.
            </SheetDescription>
            <div className="mt-8">
              <Navigation path={path} close={() => setOpen(false)} />
            </div>
            <Account user={user} />
          </SheetContent>
        </Sheet>
      </header>
      <main id="conteudo" tabIndex={-1} className="main-content">
        <div className="canvas">{children}</div>
      </main>
    </div>
  );
}
