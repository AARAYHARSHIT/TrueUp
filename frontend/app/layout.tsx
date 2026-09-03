import type { Metadata } from "next";
import { Geist, Geist_Mono } from "next/font/google";
import "./globals.css";
import { Providers } from "./providers";
import { OnboardingProvider } from "@/components/onboarding/OnboardingProvider";
import { Sidebar } from "@/components/layout/Sidebar";
import { Header } from "@/components/layout/Header";

const geistSans = Geist({
  variable: "--font-geist-sans",
  subsets: ["latin"],
});

const geistMono = Geist_Mono({
  variable: "--font-geist-mono",
  subsets: ["latin"],
});

export const metadata: Metadata = {
  title: "TrueUp — AI Finance Controller",
  description:
    "Reconciliation engine dashboard. Deterministic-first, fuzzy-second, LLM-only-when-genuinely-ambiguous.",
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html
      lang="en"
      className={`${geistSans.variable} ${geistMono.variable} h-full antialiased`}
    >
      <body className="h-full bg-background text-foreground">
        <Providers>
          <OnboardingProvider>
            <div className="flex h-full">
              <Sidebar />
              <div className="flex flex-col flex-1 min-w-0">
                <Header />
                <main className="flex-1 overflow-auto p-6">{children}</main>
              </div>
            </div>
          </OnboardingProvider>
        </Providers>
      </body>
    </html>
  );
}
