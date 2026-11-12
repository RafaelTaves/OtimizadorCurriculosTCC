import type { Metadata } from "next";
import "@fontsource/manrope/latin-600.css";
import "@fontsource/manrope/latin-700.css";
import "@fontsource/source-sans-3/latin-400.css";
import "@fontsource/source-sans-3/latin-500.css";
import "@fontsource/source-sans-3/latin-600.css";
import "@fontsource/source-sans-3/latin-700.css";
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
