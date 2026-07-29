import type { ButtonHTMLAttributes, ReactNode } from "react";

/** The one control that was never extracted.
 *
 *  Twenty-five raw `<button>` elements were styling themselves inline and had
 *  already drifted — `px-4 py-1.5`, `px-3 py-2.5` and `px-3 py-1.5` all appeared
 *  for what is conceptually the same control. Button is the canonical design
 *  system component; leaving it un-extracted meant every new button was a fresh
 *  decision.
 *
 *  Accent discipline is baked in rather than left to the caller: `primary` is
 *  the only variant that spends gold, because gold means "the engine is making a
 *  claim" or "this is the one action that matters". A page with two primaries
 *  has no primary. */

export type ButtonVariant = "primary" | "secondary" | "ghost" | "danger";
export type ButtonSize = "sm" | "md";

const BASE =
  "inline-flex items-center justify-center gap-1.5 rounded-md font-600 " +
  "transition disabled:cursor-not-allowed disabled:opacity-45";

const VARIANT: Record<ButtonVariant, string> = {
  // Filled accent. At most one per view.
  primary: "bg-accent text-accent-ink hover:bg-accent/90",
  // The workhorse: readable, bordered, no accent spend.
  secondary:
    "border border-line-ctl bg-surface-inset text-ink-soft hover:border-line-hover hover:text-ink",
  // Chromeless — toolbars, inline toggles, anywhere a border would be noise.
  ghost: "text-ink-dim hover:bg-surface-inset/70 hover:text-ink",
  // Destructive. Uses the fixed `soft` red, never the runtime accent: a
  // destructive action must not turn gold because someone re-themed the app.
  danger: "border border-soft/40 bg-soft/10 text-soft hover:bg-soft/20",
};

const SIZE: Record<ButtonSize, string> = {
  sm: "px-3 py-1.5 text-data",
  md: "px-4 py-2 text-sm",
};

export interface ButtonProps extends ButtonHTMLAttributes<HTMLButtonElement> {
  variant?: ButtonVariant;
  size?: ButtonSize;
  /** Shows a spinner and blocks interaction without collapsing the layout. */
  loading?: boolean;
  /** Leading glyph or icon. Marked aria-hidden — the label carries the meaning. */
  icon?: ReactNode;
  /** Selected state for toggles; sets aria-pressed so it is announced. */
  pressed?: boolean;
  children?: ReactNode;
}

export function Button({
  variant = "secondary",
  size = "md",
  loading = false,
  icon,
  pressed,
  disabled,
  className = "",
  children,
  onClick,
  ...rest
}: ButtonProps) {
  return (
    <button
      {...rest}
      // A loading button stays focusable but must not fire twice. Real
      // `disabled` would drop focus mid-interaction and stop announcing, so
      // loading uses aria-disabled + a swallowed handler, and `disabled` is
      // reserved for genuinely inert controls.
      disabled={disabled}
      aria-disabled={loading || undefined}
      aria-busy={loading || undefined}
      aria-pressed={pressed}
      onClick={loading ? undefined : onClick}
      className={`${BASE} ${VARIANT[variant]} ${SIZE[size]} ${
        pressed ? "ring-1 ring-inset ring-accent/50" : ""
      } ${className}`}
    >
      {loading ? (
        <span
          aria-hidden
          className="h-3 w-3 shrink-0 animate-spin rounded-full border-2 border-current border-t-transparent"
        />
      ) : (
        icon != null && (
          <span aria-hidden className="shrink-0">
            {icon}
          </span>
        )
      )}
      {children}
    </button>
  );
}
