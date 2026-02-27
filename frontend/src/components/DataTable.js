import { jsx as _jsx, jsxs as _jsxs } from "react/jsx-runtime";
import { useMemo, useState } from "react";
function asComparable(value) {
    if (value === null || value === undefined || value === "") {
        return null;
    }
    if (typeof value === "number") {
        return value;
    }
    if (typeof value === "string") {
        const raw = value.replace(/[,%]/g, "").trim();
        const parsed = Number(raw);
        return Number.isNaN(parsed) ? value.toLowerCase() : parsed;
    }
    return String(value).toLowerCase();
}
function formatCell(value) {
    if (value === null || value === undefined || value === "") {
        return "—";
    }
    return String(value);
}
function classNames(...parts) {
    return parts.filter(Boolean).join(" ");
}
export function DataTable({ columns, rows, initialSort, tableClassName, rowClassName }) {
    const [sortKey, setSortKey] = useState(initialSort?.key ?? columns[0]?.key ?? "");
    const [sortDesc, setSortDesc] = useState(initialSort?.desc ?? false);
    const rowIdKey = columns[0]?.key ?? "id";
    const sorted = useMemo(() => {
        const activeColumn = columns.find((column) => column.key === sortKey);
        const next = [...rows];
        next.sort((a, b) => {
            const aRaw = activeColumn?.sortValue ? activeColumn.sortValue(a[sortKey], a) : a[sortKey];
            const bRaw = activeColumn?.sortValue ? activeColumn.sortValue(b[sortKey], b) : b[sortKey];
            const av = asComparable(aRaw);
            const bv = asComparable(bRaw);
            if (av === null && bv === null)
                return 0;
            if (av === null)
                return 1;
            if (bv === null)
                return -1;
            let compare = 0;
            if (typeof av === "number" && typeof bv === "number") {
                compare = av - bv;
            }
            else {
                compare = av < bv ? -1 : av > bv ? 1 : 0;
            }
            return sortDesc ? -compare : compare;
        });
        return next;
    }, [columns, rows, sortKey, sortDesc]);
    function onSort(key) {
        if (key === sortKey) {
            setSortDesc((value) => !value);
            return;
        }
        setSortKey(key);
        setSortDesc(false);
    }
    return (_jsx("div", { className: "table-wrap", children: _jsxs("table", { className: tableClassName, children: [_jsx("thead", { children: _jsx("tr", { children: columns.map((column) => (_jsx("th", { className: classNames(sortKey === column.key ? "active-sort" : "", column.align ? `align-${column.align}` : "", column.headerClassName), onClick: () => onSort(column.key), children: column.label }, column.key))) }) }), _jsx("tbody", { children: sorted.map((row, index) => (_jsx("tr", { className: rowClassName ? rowClassName(row, index) : undefined, children: columns.map((column) => {
                            const value = row[column.key];
                            const customCellClass = typeof column.cellClassName === "function" ? column.cellClassName(value, row) : column.cellClassName;
                            return (_jsx("td", { className: classNames(column.align ? `align-${column.align}` : "", customCellClass), children: column.render ? column.render(value, row) : formatCell(value) }, column.key));
                        }) }, `${index}-${String(row[rowIdKey] ?? "row")}`))) })] }) }));
}
