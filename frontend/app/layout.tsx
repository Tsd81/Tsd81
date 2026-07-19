import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "AI Orchestrator",
  description: "Live dashboard for a personal AI agent orchestrator",
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="en">
      <body>{children}</body>
    </html>
  );
}
