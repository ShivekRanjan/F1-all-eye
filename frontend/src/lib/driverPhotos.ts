// Wikimedia headshots committed under frontend/public/drivers/ (license-checked,
// see ATTRIBUTIONS.md). Codes not listed here fall back to an initials avatar —
// no failed-image-request cascade needed since the manifest is exhaustive.
export const DRIVER_PHOTOS: Record<string, string> = {
  ALB: "ALB.jpg",
  ALO: "ALO.jpg",
  ANT: "ANT.jpg",
  BEA: "BEA.jpg",
  BOR: "BOR.jpg",
  COL: "COL.jpg",
  DOO: "DOO.jpg",
  GAS: "GAS.jpg",
  HAD: "HAD.jpg",
  HAM: "HAM.jpg",
  HUL: "HUL.jpg",
  LEC: "LEC.jpg",
  MAG: "MAG.jpg",
  NOR: "NOR.jpg",
  OCO: "OCO.jpg",
  PER: "PER.jpg",
  PIA: "PIA.jpg",
  RIC: "RIC.jpg",
  RUS: "RUS.jpg",
  SAI: "SAI.jpg",
  SAR: "SAR.jpg",
  STR: "STR.jpg",
  TSU: "TSU.jpg",
  VER: "VER.jpg",
  ZHO: "ZHO.jpg",
};

export function driverPhotoUrl(code: string): string | null {
  const file = DRIVER_PHOTOS[code];
  return file ? `/drivers/${file}` : null;
}
