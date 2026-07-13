// Transparent-background driver cutouts (frontend/public/drivers/cutouts/),
// built by src/f1se/standalone/driver_cutouts.py — real background removal on
// the original Wikimedia photos, not the small circular avatar crops. Not
// every driver has one (some photos didn't have a free-licensed original, or
// the cutout is still pending); callers fall back to DriverTag when absent.
export const DRIVER_CUTOUTS: Set<string> = new Set([
  "ALB", "ALO", "ANT", "BEA", "BOR", "DOO", "GAS", "HAD", "HAM", "HUL", "LEC", "MAG", "NOR",
  "OCO", "PER", "PIA", "RIC", "RUS", "SAI", "SAR", "STR", "TSU", "VER", "ZHO",
]);

export function driverCutoutUrl(code: string): string | null {
  return DRIVER_CUTOUTS.has(code) ? `/drivers/cutouts/${code}.webp` : null;
}
