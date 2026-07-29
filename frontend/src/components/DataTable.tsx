import type { ReactNode } from "react";

export interface Column<R> {
  key: string;
  header: ReactNode;
  render: (row: R) => ReactNode;
  align?: "left" | "right" | "center";
  className?: string;
}

/** Minimal, dark-themed table. Highlights the first row (rank 1 / our pick),
 *  and optionally a specific row (e.g. the user's favourite driver) via
 *  `isHighlighted` — a distinct accent-left-border treatment so it doesn't
 *  get confused with the "our pick" tint. */
export function DataTable<R>({
  columns,
  rows,
  highlightFirst = false,
  isHighlighted,
  getKey,
}: {
  columns: Column<R>[];
  rows: R[];
  highlightFirst?: boolean;
  isHighlighted?: (row: R) => boolean;
  getKey: (row: R, i: number) => string | number;
}) {
  const alignCls = { left: "text-left", right: "text-right", center: "text-center" };
  // Right/center-aligned columns are numeric-ish and content-width — collapsing
  // them to their content (instead of the browser's default auto-layout, which
  // stretches every column) keeps the numbers tight together on the right
  // instead of scattering across the full table width.
  const narrowCls = (c: Column<R>) =>
    c.align === "right" || c.align === "center" ? "w-px whitespace-nowrap" : "";
  return (
    <div className="overflow-x-auto">
      <table className="w-full border-collapse text-sm">
        <thead>
          <tr className="border-b border-line">
            {columns.map((c) => (
              <th
                key={c.key}
                className={`px-3 py-2 text-mini font-600 uppercase tracking-wide text-ink-muted ${alignCls[c.align ?? "left"]} ${narrowCls(c)}`}
              >
                {c.header}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {rows.map((row, i) => (
            <tr
              key={getKey(row, i)}
              className={`animate-rise border-b border-line/60 ${
                highlightFirst && i === 0 ? "bg-f1/[0.06]" : ""
              } ${isHighlighted?.(row) ? "border-l-2 border-l-accent bg-accent/[0.05]" : ""}`}
              style={{ animationDelay: `${Math.min(i, 10) * 30}ms` }}
            >
              {columns.map((c) => (
                <td
                  key={c.key}
                  className={`nums px-3 py-2 text-ink ${alignCls[c.align ?? "left"]} ${narrowCls(c)} ${c.className ?? ""}`}
                >
                  {c.render(row)}
                </td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
