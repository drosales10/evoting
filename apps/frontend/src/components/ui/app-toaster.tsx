"use client";

import { useEffect, useState } from "react";
import { Toaster as SonnerToaster } from "sonner";

/**
 * Observa la clase `.dark` en <html> (portal cliente) para alinear Sonner
 * con el modo claro/oscuro de la app, sin depender de next-themes.
 */
function useDocumentTheme(): "light" | "dark" {
  const [theme, setTheme] = useState<"light" | "dark">("light");

  useEffect(() => {
    const root = document.documentElement;
    const sync = () => {
      setTheme(root.classList.contains("dark") ? "dark" : "light");
    };
    sync();
    const observer = new MutationObserver(sync);
    observer.observe(root, { attributes: true, attributeFilter: ["class"] });
    return () => observer.disconnect();
  }, []);

  return theme;
}

export function AppToaster() {
  const theme = useDocumentTheme();

  return (
    <SonnerToaster
      theme={theme}
      position="top-right"
      richColors
      closeButton
      expand={false}
      visibleToasts={4}
      duration={4500}
      toastOptions={{
        classNames: {
          toast:
            "border border-[var(--line)] bg-[var(--surface)] text-[var(--ink)] shadow-lg",
          title: "text-sm font-semibold text-[var(--ink)]",
          description: "text-sm text-[var(--muted)]",
          closeButton:
            "border border-[var(--line)] bg-[var(--surface)] text-[var(--muted)]",
        },
      }}
    />
  );
}
