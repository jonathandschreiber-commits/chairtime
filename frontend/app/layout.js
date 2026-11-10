import Image from "next/image";
import Link from "next/link";
import { Geist, Geist_Mono } from "next/font/google";
import "./globals.css";

const geistSans = Geist({
  variable: "--font-geist-sans",
  subsets: ["latin"],
});

const geistMono = Geist_Mono({
  variable: "--font-geist-mono",
  subsets: ["latin"],
});

export const metadata = {
  title: "DayTello | Simple scheduling for busy businesses",
  description: "Manage appointments, customers, reminders, and online booking with DayTello.",
};

export default function RootLayout({ children }) {
  return (
    <html
      lang="en"
      className={`${geistSans.variable} ${geistMono.variable} h-full antialiased`}
    >
      <body className="min-h-full flex flex-col">
        <div className="border-b border-gray-200 bg-white">
          <div className="mx-auto max-w-6xl px-6">
            <Link href="/" aria-label="DayTello home" className="inline-block max-w-full align-middle">
              <Image src="/daytello-logo.png" alt="DayTello" width={350} height={180} className="h-auto w-64 max-w-full sm:w-96 lg:w-[420px]" unoptimized />
            </Link>
          </div>
        </div>
        {children}
      </body>
    </html>
  );
}

