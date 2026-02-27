export function toNumber(value) {
    if (typeof value === "number" && Number.isFinite(value)) {
        return value;
    }
    if (typeof value === "string") {
        const parsed = Number(value.replace(/[,%]/g, "").trim());
        return Number.isFinite(parsed) ? parsed : null;
    }
    return null;
}
export function isNumber(value) {
    return toNumber(value) !== null;
}
export function formatFixed(value, decimals) {
    const num = toNumber(value);
    if (num === null) {
        return "—";
    }
    return num.toFixed(decimals);
}
export function formatCompact(value, maxDecimals = 3) {
    const num = toNumber(value);
    if (num === null) {
        return "—";
    }
    return num.toLocaleString("en-US", {
        minimumFractionDigits: 0,
        maximumFractionDigits: maxDecimals
    });
}
export function formatSigned(value, decimals = 0) {
    const num = toNumber(value);
    if (num === null) {
        return "—";
    }
    const prefix = num > 0 ? "+" : "";
    const body = decimals === 0 ? formatCompact(num, 3) : num.toFixed(decimals);
    return `${prefix}${body}`;
}
