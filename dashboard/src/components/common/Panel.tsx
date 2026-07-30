import { useState, type ReactNode } from "react";
import { ChevronDown, Info } from "lucide-react";
import { cn } from "@/lib/utils";
import { Tooltip, TooltipContent, TooltipTrigger } from "@/components/ui/tooltip";

/**
 * Jerarquía visual de tres niveles:
 * - `primary`: visualización principal de la vista (más superficie y contraste).
 * - `secondary`: apoyo analítico, densidad media.
 * - `technical`: detalle técnico/tabular, tipografía y fondo más discretos.
 */
export type PanelLevel = "primary" | "secondary" | "technical";

interface PanelProps {
  title: string;
  description?: string;
  tooltip?: string;
  actions?: ReactNode;
  children: ReactNode;
  className?: string;
  bodyClassName?: string;
  level?: PanelLevel;
  /** Muestra el panel plegable (útil en secciones técnicas densas). */
  collapsible?: boolean;
  defaultOpen?: boolean;
  footer?: ReactNode;
}

const LEVEL_SHELL: Record<PanelLevel, string> = {
  primary: "panel shadow-[var(--shadow-panel)]",
  secondary: "panel",
  technical: "panel bg-muted/25",
};

const LEVEL_TITLE: Record<PanelLevel, string> = {
  primary: "text-[15px] font-semibold tracking-tight",
  secondary: "text-sm font-semibold tracking-tight",
  technical: "text-xs font-semibold uppercase tracking-wide text-muted-foreground",
};

/** Contenedor estándar de panel analítico con encabezado, ayuda y acciones. */
export function Panel({
  title,
  description,
  tooltip,
  actions,
  children,
  className,
  bodyClassName,
  level = "secondary",
  collapsible = false,
  defaultOpen = true,
  footer,
}: PanelProps) {
  const [open, setOpen] = useState(defaultOpen);
  return (
    <section className={cn(LEVEL_SHELL[level], "flex flex-col", className)} aria-label={title}>
      <header
        className={cn(
          "flex flex-wrap items-start justify-between gap-3 border-b border-panel-border px-4",
          level === "technical" ? "py-2.5" : "py-3",
        )}
      >
        <div className="min-w-0">
          <h2
            className={cn(
              "flex items-center gap-1.5 text-foreground",
              LEVEL_TITLE[level],
            )}
          >
            {collapsible && (
              <button
                type="button"
                onClick={() => setOpen((o) => !o)}
                aria-expanded={open}
                aria-label={open ? `Contraer ${title}` : `Expandir ${title}`}
                className="rounded text-muted-foreground transition-transform hover:text-foreground"
              >
                <ChevronDown
                  className={cn("h-4 w-4 transition-transform", !open && "-rotate-90")}
                  aria-hidden
                />
              </button>
            )}
            {title}
            {tooltip && (
              <Tooltip>
                <TooltipTrigger asChild>
                  <button
                    type="button"
                    aria-label={`Información sobre ${title}`}
                    className="rounded-full text-muted-foreground transition-colors hover:text-foreground"
                  >
                    <Info className="h-3.5 w-3.5" aria-hidden />
                  </button>
                </TooltipTrigger>
                <TooltipContent className="max-w-xs">{tooltip}</TooltipContent>
              </Tooltip>
            )}
          </h2>
          {description && (
            <p className="mt-0.5 text-xs text-muted-foreground">{description}</p>
          )}
        </div>
        {actions && <div className="flex shrink-0 flex-wrap items-center gap-2">{actions}</div>}
      </header>
      {(!collapsible || open) && (
        <div className={cn("flex-1", level === "technical" ? "p-3" : "p-4", bodyClassName)}>
          {children}
        </div>
      )}
      {footer && (!collapsible || open) && (
        <div className="border-t border-panel-border px-4 py-2.5 text-xs text-muted-foreground">
          {footer}
        </div>
      )}
    </section>
  );
}

/** Título de sección para separar los niveles de una página. */
export function SectionHeading({
  title,
  description,
  actions,
  className,
}: {
  title: string;
  description?: string;
  actions?: ReactNode;
  className?: string;
}) {
  return (
    <div
      className={cn(
        "grid grid-cols-[minmax(0,1fr)_auto] items-end gap-3 pt-1 sm:flex sm:justify-between",
        className,
      )}
    >
      <div className="min-w-0">
        <h2 className="truncate text-xs font-semibold uppercase tracking-[0.14em] text-muted-foreground">
          {title}
        </h2>
        {description && <p className="mt-1 text-sm text-foreground/80">{description}</p>}
      </div>
      {actions}
    </div>
  );
}