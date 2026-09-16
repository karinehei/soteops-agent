import type { Metadata } from "next";
import type { ReactNode } from "react";

import { AppShell } from "@/components/AppShell";
import { Providers } from "@/components/Providers";
import { SyntheticDataBanner } from "@/components/SyntheticDataBanner";

import "./globals.css";

export const metadata: Metadata = {
  title: "SoteOps Agent",
  description:
    "Suomenkielinen prototyyppi synteettisten käyttöoikeuspyyntöjen valmisteluun ihmisen tarkistettavaksi.",
};

export default function RootLayout({ children }: Readonly<{ children: ReactNode }>) {
  return (
    <html lang="fi">
      <body>
        <Providers>
          <SyntheticDataBanner />
          <AppShell>{children}</AppShell>
        </Providers>
      </body>
    </html>
  );
}
