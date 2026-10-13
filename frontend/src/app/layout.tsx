import type { Metadata } from "next";
import { Inter, JetBrains_Mono } from "next/font/google";
import "./globals.css";
import { Providers } from "@/components/providers";
import { Header } from "@/components/header";

const inter = Inter({
  variable: "--font-inter",
  subsets: ["latin"],
  display: "swap",
});

const jetbrainsMono = JetBrains_Mono({
  variable: "--font-mono",
  subsets: ["latin"],
  display: "swap",
});

export const metadata: Metadata = {
  title: "ClauseGuard — Contract Integrity & Risk Analysis",
  description: "Review contracts for tampering, contradictions, and key terms with an evidence-based human review workbench.",
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="en" className={`${inter.variable} ${jetbrainsMono.variable} h-full antialiased`}>
      <body className="min-h-full flex flex-col bg-[var(--bg-app)] text-[var(--text-primary)]">
        <Providers>
          <Header />
          <main className="flex-1 flex flex-col">{children}</main>
          <footer className="border-t border-[var(--border-subtle)] bg-[var(--bg-card)] py-4 text-center text-xs text-[var(--text-muted)]">
            <div className="mx-auto max-w-7xl px-4">
              ClauseGuard flags items for human review. It is not legal advice.
            </div>
          </footer>
        </Providers>
      </body>
    </html>
  );
}
