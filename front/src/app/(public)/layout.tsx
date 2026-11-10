import { Brand } from "@/components/layout/brand";
export default function PublicLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <main className="auth-layout">
      <Brand href="/login" />
      <div className="auth-card">{children}</div>
      <p className="auth-footer">
        Currículos em português. Revisão humana em cada etapa.
      </p>
    </main>
  );
}
