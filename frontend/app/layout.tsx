import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "Parkly · Quản lý bãi đỗ xe",
  description: "Không gian quản lý bãi đỗ xe thông minh",
};

export default function RootLayout({ children }: LayoutProps<"/">) {
  return (
    <html lang="vi">
      <body>{children}</body>
    </html>
  );
}
