import { jsx as _jsx } from "react/jsx-runtime";
export function StatusPanel({ loading, error, hasData, emptyMessage }) {
    if (loading) {
        return _jsx("div", { className: "panel", children: "Loading..." });
    }
    if (error) {
        return _jsx("div", { className: "panel error", children: error });
    }
    if (!hasData) {
        return _jsx("div", { className: "panel", children: emptyMessage });
    }
    return null;
}
