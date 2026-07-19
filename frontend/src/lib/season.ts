/** Resolves the season a view should default to: the user's saved preference
 *  if it's actually in the available list, otherwise the latest season —
 *  today's behaviour. Shared so Calendar/Standings/Strategy/Live don't each
 *  reimplement the same fallback. */
export function pickSeason(seasons: number[], preferred: number | null): number | null {
  if (!seasons.length) return null;
  if (preferred != null && seasons.includes(preferred)) return preferred;
  return seasons[seasons.length - 1];
}
