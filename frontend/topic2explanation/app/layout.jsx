import "./globals.css";
import { Orbitron, Space_Grotesk } from "next/font/google";

const displayFont = Orbitron({
  subsets: ["latin"],
  variable: "--font-display",
});

const bodyFont = Space_Grotesk({
  subsets: ["latin"],
  variable: "--font-body",
});

export const metadata = {
  title: "API Video Tutorial Generator",
  description:
    "A futuristic landing page and studio for generating polished tutorial videos from a single idea or API brief.",
};

export default function RootLayout({ children }) {
  return (
    <html lang="en">
      <body className={`${displayFont.variable} ${bodyFont.variable}`}>
        {children}
      </body>
    </html>
  );
}
