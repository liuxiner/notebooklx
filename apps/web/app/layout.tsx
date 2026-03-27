import type { Metadata } from "next";
import { Inter } from "next/font/google";
import "./globals.css";
import { ToastProvider } from "@/lib/toast";

const inter = Inter({ subsets: ["latin"] });

export const metadata: Metadata = {
  title: "NotebookLX",
  description: "Source-grounded notebook knowledge workspace",
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="en">
      <body className={inter.className}>
        <ToastProvider>{children}</ToastProvider>
      </body>
    </html>
  );
}
