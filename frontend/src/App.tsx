import { Suspense, forwardRef, lazy, useEffect, useLayoutEffect, useRef, useState } from "react";
import { CursorGlow } from "./components/CursorGlow";
import { Spinner } from "./components/ui";
import { useSettings } from "./lib/useSettings";

// Views are lazy-loaded: each section (and the chart library the heavy ones
// pull in) ships as its own chunk instead of one entry bundle.
const HomeView = lazy(() => import("./views/HomeView"));
const StrategyView = lazy(() => import("./views/StrategyView"));
const RaceHubView = lazy(() => import("./views/RaceHubView"));
const UndercutView = lazy(() => import("./views/UndercutView"));
const OutcomeView = lazy(() => import("./views/OutcomeView"));
const StandingsView = lazy(() => import("./views/StandingsView"));
const ProfilesView = lazy(() => import("./views/ProfilesView"));
const NewsView = lazy(() => import("./views/NewsView"));
const CalendarView = lazy(() => import("./views/CalendarView"));
const LiveView = lazy(() => import("./views/LiveView"));
const AboutView = lazy(() => import("./views/AboutView"));
const SettingsView = lazy(() => import("./views/SettingsView"));

const REPO = "https://github.com/ShivekRanjan/f1-strategy-engine";

const TABS = [
  { id: "home", label: "Home", group: "Overview", el: <HomeView /> },
  { id: "strategy", label: "Strategy", group: "Strategy", el: <StrategyView /> },
  { id: "undercut", label: "Undercut", group: "Strategy", el: <UndercutView /> },
  { id: "calendar", label: "Calendar", group: "Race weekend", el: <CalendarView /> },
  { id: "racehub", label: "Race Hub", group: "Race weekend", el: <RaceHubView /> },
  { id: "live", label: "Live Race", group: "Race weekend", el: <LiveView /> },
  { id: "standings", label: "Standings", group: "Championship", el: <StandingsView /> },
  { id: "profiles", label: "Drivers & Teams", group: "Championship", el: <ProfilesView /> },
  { id: "outcome", label: "Outcome", group: "Championship", el: <OutcomeView /> },
  { id: "news", label: "News", group: "Paddock", el: <NewsView /> },
  { id: "about", label: "About", group: "Paddock", el: <AboutView /> },
  // Pinned to the sidebar's bottom, outside the scrollable groups (handoff).
  { id: "settings", label: "Settings", group: "_pinned", el: <SettingsView /> },
] as const;

type TabId = (typeof TABS)[number]["id"];
const GROUP_ORDER = ["Overview", "Strategy", "Race weekend", "Championship", "Paddock"] as const;

// --- tiny hash router: the tab lives in the URL (#/standings), so refresh
// keeps your place, back/forward work, and sections are deep-linkable.
function tabFromHash(): TabId {
  const h = window.location.hash.replace(/^#\/?/, "");
  return (TABS.some((t) => t.id === h) ? h : "home") as TabId;
}

function useHashTab(): [TabId, (id: TabId) => void] {
  const [tab, setTabState] = useState<TabId>(tabFromHash);
  useEffect(() => {
    const onHash = () => setTabState(tabFromHash());
    window.addEventListener("hashchange", onHash);
    return () => window.removeEventListener("hashchange", onHash);
  }, []);
  const setTab = (id: TabId) => {
    window.location.hash = `/${id}`; // hashchange listener syncs the state
  };
  return [tab, setTab];
}

export default function App() {
  const [tab, setTab] = useHashTab();
  const [collapsed, setCollapsed] = useState(false);
  useSettings(); // ensures <html data-accent/motion> stays applied + reactive
  const active = TABS.find((t) => t.id === tab)!;

  // Sliding indicator that tracks the active nav item — measured off the
  // real DOM node rather than computed from layout constants, so it stays
  // correct however the group headers/spacing change.
  const navRef = useRef<HTMLElement>(null);
  const itemRefs = useRef<Partial<Record<TabId, HTMLButtonElement | null>>>({});
  const [indicator, setIndicator] = useState({ top: 0, height: 0, ready: false });
  useLayoutEffect(() => {
    const btn = itemRefs.current[tab];
    if (btn) setIndicator({ top: btn.offsetTop, height: btn.offsetHeight, ready: true });
  }, [tab, collapsed]);

  return (
    <div className="lg:flex">
      {/* ---- Ambient grid drift — page-wide, behind every screen (not just
          Home's hero card). Shows through the page's negative space; opaque
          card backgrounds naturally occlude it, so it reads as texture, not
          noise. Obeys the Settings motion toggle via .animate-gridmove. */}
      <div
        className="pointer-events-none fixed inset-0 z-0 animate-gridmove opacity-[0.035]"
        style={{
          backgroundImage:
            "linear-gradient(rgb(var(--accent)) 1px, transparent 1px), linear-gradient(90deg, rgb(var(--accent)) 1px, transparent 1px)",
          backgroundSize: "28px 28px",
        }}
      />
      <CursorGlow />
      {/* ---- Sidebar (desktop) — collapsible 252px/76px rail --------------- */}
      <aside
        className="sticky top-0 z-20 hidden h-screen shrink-0 flex-col border-r border-line bg-surface-rail transition-[width] duration-200 ease-out lg:flex"
        style={{ width: collapsed ? 76 : 252 }}
      >
        <div className={`flex items-center gap-3 border-b border-line px-4 py-4 ${collapsed ? "justify-center px-2" : ""}`}>
          <button
            onClick={() => setCollapsed(!collapsed)}
            aria-label={collapsed ? "Expand sidebar" : "Collapse sidebar"}
            className="flex h-10 w-10 shrink-0 flex-col items-center justify-center gap-[3px] rounded-md border border-line-ctl transition hover:border-line-hover"
          >
            <span className="h-[2px] w-4 rounded bg-ink-dim" />
            <span className="h-[2px] w-4 rounded bg-ink-dim" />
            <span className="h-[2px] w-4 rounded bg-ink-dim" />
          </button>
          {!collapsed && <Brand />}
        </div>

        <nav ref={navRef} className="relative flex-1 overflow-y-auto overflow-x-hidden px-3 py-4">
          <div
            className="pointer-events-none absolute left-0 w-[3px] rounded-r bg-accent shadow-glow transition-[transform,height,opacity] duration-300 ease-out"
            style={{
              transform: `translateY(${indicator.top}px)`,
              height: indicator.height,
              opacity: indicator.ready ? 1 : 0,
            }}
          />
          {GROUP_ORDER.map((g) => (
            <div key={g} className="mb-5">
              {!collapsed && (
                <div className="mb-1.5 px-2 font-mono text-[11px] uppercase tracking-[0.16em] text-ink-faint">
                  {g}
                </div>
              )}
              {TABS.filter((t) => t.group === g).map((t) => (
                <NavItem
                  key={t.id}
                  ref={(el) => {
                    itemRefs.current[t.id] = el;
                  }}
                  label={t.label}
                  collapsed={collapsed}
                  active={tab === t.id}
                  onClick={() => setTab(t.id)}
                />
              ))}
            </div>
          ))}
        </nav>

        {/* Settings pinned at the bottom, above the footer divider */}
        <div className="border-t border-line px-3 py-2">
          <NavItem
            label="Settings"
            icon="⚙"
            collapsed={collapsed}
            active={tab === "settings"}
            onClick={() => setTab("settings")}
          />
        </div>
        {!collapsed && <Footer />}
      </aside>

      {/* ---- Mobile top bar ---------------------------------------------- */}
      <header className="sticky top-0 z-20 border-b border-line bg-surface-rail/95 backdrop-blur lg:hidden">
        <div className="flex h-[56px] items-center justify-between px-4">
          <Brand />
          <a href={REPO} target="_blank" rel="noreferrer" className="font-mono text-[11px] text-ink-dim">
            repo ↗
          </a>
        </div>
        <div className="flex items-center gap-1 overflow-x-auto border-t border-line px-3">
          {GROUP_ORDER.map((g, gi) => (
            <span key={g} className="flex items-center gap-1">
              {gi > 0 && <span className="mx-1 h-4 w-px shrink-0 bg-line-hover/60" />}
              {TABS.filter((t) => t.group === g).map((t) => (
                <MobileTab key={t.id} label={t.label} active={tab === t.id} onClick={() => setTab(t.id)} />
              ))}
            </span>
          ))}
          <span className="mx-1 h-4 w-px shrink-0 bg-line-hover/60" />
          <MobileTab label="Settings" active={tab === "settings"} onClick={() => setTab("settings")} />
        </div>
      </header>

      {/* ---- Main content ------------------------------------------------- */}
      <div className="min-w-0 flex-1">
        <div className="hidden items-center justify-between border-b border-line px-6 py-3 lg:flex">
          <div className="font-mono text-[11px] uppercase tracking-[0.14em] text-ink-muted">
            <span className="text-ink-faint">{active.group === "_pinned" ? "System" : active.group}</span>
            <span className="px-2 text-ink-faint">/</span>
            <span className="text-ink">{active.label}</span>
          </div>
          <div className="flex items-center gap-4 font-mono text-[11px]">
            <span className="flex items-center gap-2 text-accent">
              <span className="h-[7px] w-[7px] animate-f1pulse rounded-full bg-accent" />
              LIVE MODEL
            </span>
            <span className="text-ink-faint">2023–26 · CRN</span>
          </div>
        </div>
        <main className="mx-auto max-w-[1600px] px-5 py-6">
          {/* Screen-reader page title — the visible breadcrumb above conveys
              this visually on desktop, but nothing does on mobile, and
              without an h1 the document has no top-level heading at all. */}
          <h1 className="sr-only">{active.label}</h1>
          {/* Keyed by tab: a brief rise preserves continuity between sections. */}
          <div key={tab} className="animate-fadein">
            <Suspense fallback={<Spinner label="Loading…" />}>{active.el}</Suspense>
          </div>
        </main>
      </div>
    </div>
  );
}

function Brand() {
  return (
    <div className="flex min-w-0 items-center gap-3">
      <Logo />
      <div className="min-w-0 leading-tight">
        <div className="truncate text-[15px] font-700 text-ink">
          F1<span className="text-accent">SE</span>
          <span className="px-1 font-500 text-ink-faint">/</span>
          <span className="text-ink-soft">F1 OS</span>
        </div>
        <div className="truncate font-mono text-[11px] uppercase tracking-[0.14em] text-ink-faint">
          v2 · strategy · live
        </div>
      </div>
    </div>
  );
}

/** V2 logo: 32px dark badge with a folded-flag chevron in a gold→accent
 *  gradient, breathing a soft glow (pure CSS — no image asset). */
function Logo() {
  return (
    <div
      className="flex h-8 w-8 shrink-0 items-center justify-center rounded-lg border text-accent animate-breathe"
      style={{ background: "#151109", borderColor: "#3a3020" }}
    >
      <span
        className="block h-4 w-4"
        style={{
          clipPath: "polygon(0 0, 100% 25%, 100% 100%, 0 75%)",
          background: "linear-gradient(135deg, #f0d780, rgb(var(--accent)))",
        }}
      />
    </div>
  );
}

const NavItem = forwardRef<
  HTMLButtonElement,
  { label: string; active: boolean; collapsed: boolean; icon?: string; onClick: () => void }
>(function NavItem({ label, active, collapsed, icon, onClick }, ref) {
  return (
    <button
      ref={ref}
      onClick={onClick}
      aria-current={active ? "page" : undefined}
      title={collapsed ? label : undefined}
      className={`relative flex min-h-[40px] w-full items-center gap-2.5 rounded-md px-3 py-2.5 text-left text-[13px] transition ${
        active ? "bg-accent/15 text-accent" : "text-ink-dim hover:bg-surface-inset/70 hover:text-ink-soft"
      } ${collapsed ? "justify-center px-0" : ""}`}
    >
      <span
        className={`h-2 w-2 shrink-0 rounded-[3px] ${active ? "bg-accent" : "bg-line-hover"}`}
        aria-hidden
      />
      {!collapsed && (
        <span className="truncate">
          {icon ? `${icon} ` : ""}
          {label}
        </span>
      )}
    </button>
  );
});

function MobileTab({ label, active, onClick }: { label: string; active: boolean; onClick: () => void }) {
  return (
    <button
      onClick={onClick}
      className={`flex min-h-[44px] items-center whitespace-nowrap rounded-md px-3 font-mono text-[12px] transition ${
        active ? "bg-accent/15 text-accent" : "text-ink-dim hover:text-ink-muted"
      }`}
    >
      {label}
    </button>
  );
}

function Footer() {
  return (
    <div className="space-y-1.5 border-t border-line px-4 py-3">
      <a
        href={REPO}
        target="_blank"
        rel="noreferrer"
        className="flex items-center justify-between font-mono text-[11px] text-ink-dim transition hover:text-ink-soft"
      >
        <span>github ↗</span>
        <span className="flex items-center gap-1.5 text-accent">
          <span className="h-[6px] w-[6px] animate-f1pulse rounded-full bg-accent" />
          live
        </span>
      </a>
      <div className="font-mono text-[11px] text-ink-faint">
        v{__APP_VERSION__} · {__BUILD_SHA__}
      </div>
    </div>
  );
}
