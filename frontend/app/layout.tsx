import type { Metadata } from "next";
import { Geist, Geist_Mono } from "next/font/google";
import Providers from "./providers";
import "./globals.css";

const geistSans = Geist({
  variable: "--font-geist-sans",
  subsets: ["latin"],
});

const geistMono = Geist_Mono({
  variable: "--font-geist-mono",
  subsets: ["latin"],
});

export const metadata: Metadata = {
  title: "ResearchSwarm — Turn hours of research into one cited report",
  description:
    "A local-first multi-agent research workspace. Ask a question, and ResearchSwarm plans it, searches the web and your PDFs, ranks the evidence, and writes a cited answer. Powered by LangGraph + Ollama.",
  keywords: ["AI", "research", "multi-agent", "RAG", "LangGraph", "Ollama", "PDF analysis", "citations"],
  openGraph: {
    title: "ResearchSwarm — Multi-agent research workspace",
    description:
      "Turn hours of research into one cited report. Web search, PDF analysis, and evidence-ranked answers — all local.",
    type: "website",
  },
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html
      lang="en"
      className={`${geistSans.variable} ${geistMono.variable}`}
      suppressHydrationWarning
    >
      <head>
        <script
          dangerouslySetInnerHTML={{
            __html: `
              (function() {
                try {
                  var theme = localStorage.getItem('research-swarm-theme');
                  if (!theme || theme === 'dark') {
                    document.documentElement.classList.add('dark');
                  } else {
                    document.documentElement.classList.remove('dark');
                  }
                } catch(e) {}
              })();
            `,
          }}
        />
      </head>
      <body className="antialiased">
        <Providers>{children}</Providers>
      </body>
    </html>
  );
}
