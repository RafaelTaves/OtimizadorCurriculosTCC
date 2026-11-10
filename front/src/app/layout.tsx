import type { Metadata } from "next";
import "@fontsource/geist/400.css";
import "@fontsource/geist/500.css";
import "./globals.css";
export const metadata: Metadata = {
  title: {
    default: "Otimizador de currículos",
    template: "%s | Otimizador de currículos",
  },
  description:
    "Seu espaço para preparar, revisar e organizar currículos em português.",
};
export default function RootLayout({
  children,
}: Readonly<{ children: React.ReactNode }>) {
  return (
    <html lang="pt-BR">
      <body>{children}</body>
    </html>
  );
}
