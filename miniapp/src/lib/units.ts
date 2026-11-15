/* Imperial <-> metric. The API always stores kg and cm. */
const LB = 0.45359237;
const INCH = 2.54;

export type WeightUnit = "kg" | "lb";
export type HeightUnit = "cm" | "in";

export const kgToLb = (kg: number) => Math.round(kg / LB);
export const lbToKg = (lb: number) => Math.round(lb * LB * 10) / 10;
export const cmToIn = (cm: number) => Math.round(cm / INCH);
export const inToCm = (inches: number) => Math.round(inches * INCH * 10) / 10;

/** 70 -> 5′10″ */
export function formatFeet(inches: number): string {
  return `${Math.floor(inches / 12)}′${inches % 12}″`;
}

export function clamp(value: number, low: number, high: number): number {
  return Math.min(high, Math.max(low, value));
}

/** Round to the nearest multiple of step (avoids 72.49999 float noise). */
export function snap(value: number, step: number): number {
  return Math.round(Math.round(value / step) * step * 10) / 10;
}
