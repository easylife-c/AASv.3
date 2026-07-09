import "./globals.css";
import type { Metadata } from "next";

export const metadata: Metadata = {
  title: "Plant Care Dashboard",
  description: "Smart agriculture monitoring & control",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en">
      <body>{children}</body>
    </html>
  );
}
