import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "Oak | Task control",
  description: "Configure tasks, agents, and explicit tool access.",
  robots: { index: false, follow: false },
};

export default function RootLayout({ children }: LayoutProps<"/">) {
  return (
    <html lang="en" className="dark h-full antialiased">
      <body className="min-h-full flex flex-col">{children}</body>
    </html>
  );
}
