// chart colors, separate from the UI accent color in globals.css
// validated for colorblind-safety, don't reorder

export const categorical = {
  light: ["#2a78d6", "#eb6834", "#1baf7a", "#eda100", "#e87ba4", "#008300", "#4a3aa7", "#e34948"],
  dark: ["#3987e5", "#d95926", "#199e70", "#c98500", "#d55181", "#008300", "#9085e9", "#e66767"],
};

// first 3 slots, safe for all-pairs comparison (scatter plots)
export const scatterTriad = {
  light: [categorical.light[0], categorical.light[1], categorical.light[2]],
  dark: [categorical.dark[0], categorical.dark[1], categorical.dark[2]],
};

export const sequentialBlue = {
  light: ["#cde2fb", "#9ec5f4", "#5598e7", "#2a78d6", "#184f95"],
  dark: ["#184f95", "#2a78d6", "#3987e5", "#86b6ef", "#cde2fb"],
};

export const diverging = {
  positive: { light: "#2a78d6", dark: "#3987e5" }, // correlation > 0
  negative: { light: "#e34948", dark: "#e66767" }, // correlation < 0
  neutral: { light: "#f0efec", dark: "#383835" }, // correlation ~ 0
};

export const status = {
  warning: { light: "#fab219", dark: "#fab219" },
  critical: { light: "#d03b3b", dark: "#e66767" },
};

export const chartInk = {
  primary: { light: "#0b0b0b", dark: "#ffffff" },
  secondary: { light: "#52514e", dark: "#c3c2b7" },
  muted: { light: "#898781", dark: "#898781" },
  gridline: { light: "#e1e0d9", dark: "#2c2c2a" },
};

function hexToRgb(hex: string): [number, number, number] {
  const n = parseInt(hex.slice(1), 16);
  return [(n >> 16) & 255, (n >> 8) & 255, n & 255];
}

function lerpHex(a: string, b: string, t: number): string {
  const [ar, ag, ab] = hexToRgb(a);
  const [br, bg, bb] = hexToRgb(b);
  const mix = (x: number, y: number) => Math.round(x + (y - x) * t);
  return `rgb(${mix(ar, br)}, ${mix(ag, bg)}, ${mix(ab, bb)})`;
}

export function correlationColor(value: number, mode: "light" | "dark"): string {
  const clamped = Math.max(-1, Math.min(1, value));
  if (clamped >= 0) return lerpHex(diverging.neutral[mode], diverging.positive[mode], clamped);
  return lerpHex(diverging.neutral[mode], diverging.negative[mode], -clamped);
}
