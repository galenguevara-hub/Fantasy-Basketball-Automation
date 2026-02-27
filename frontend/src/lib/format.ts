export function toNumber(value: unknown): number | null {
  if (typeof value === "number" && Number.isFinite(value)) {
    return value;
  }
  if (typeof value === "string") {
    const parsed = Number(value.replace(/[,%]/g, "").trim());
    return Number.isFinite(parsed) ? parsed : null;
  }
  return null;
}

export function isNumber(value: unknown): boolean {
  return toNumber(value) !== null;
}

export function formatFixed(value: unknown, decimals: number): string {
  const num = toNumber(value);
  if (num === null) {
    return "—";
  }
  return num.toFixed(decimals);
}

export function formatCompact(value: unknown, maxDecimals = 3): string {
  const num = toNumber(value);
  if (num === null) {
    return "—";
  }
  return num.toLocaleString("en-US", {
    minimumFractionDigits: 0,
    maximumFractionDigits: maxDecimals
  });
}

export function formatSigned(value: unknown, decimals = 0): string {
  const num = toNumber(value);
  if (num === null) {
    return "—";
  }
  const prefix = num > 0 ? "+" : "";
  const body = decimals === 0 ? formatCompact(num, 3) : num.toFixed(decimals);
  return `${prefix}${body}`;
}
