import type { ReactNode } from "react";
import { useMemo, useState } from "react";

type DataRow = Record<string, unknown>;

interface Column {
  key: string;
  label: string;
  align?: "left" | "right" | "center";
  headerClassName?: string;
  cellClassName?: string | ((value: unknown, row: DataRow) => string | undefined);
  render?: (value: unknown, row: DataRow) => ReactNode;
  sortValue?: (value: unknown, row: DataRow) => unknown;
}

interface DataTableProps {
  columns: Column[];
  rows: DataRow[];
  initialSort?: { key: string; desc?: boolean };
  tieBreaker?: { key: string; desc?: boolean };
  tableClassName?: string;
  rowClassName?: (row: DataRow, index: number) => string | undefined;
}

function asComparable(value: unknown): number | string | null {
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

function formatCell(value: unknown): string {
  if (value === null || value === undefined || value === "") {
    return "—";
  }
  return String(value);
}

function classNames(...parts: Array<string | undefined | false>) {
  return parts.filter(Boolean).join(" ");
}

export function DataTable({ columns, rows, initialSort, tieBreaker, tableClassName, rowClassName }: DataTableProps) {
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
      if (av === null && bv === null) return 0;
      if (av === null) return 1;
      if (bv === null) return -1;

      let compare = 0;
      if (typeof av === "number" && typeof bv === "number") {
        compare = av - bv;
      } else {
        compare = av < bv ? -1 : av > bv ? 1 : 0;
      }

      if (compare !== 0) return sortDesc ? -compare : compare;

      // Tie-breaker
      if (tieBreaker) {
        const tbKey = tieBreaker.key;
        const tbDesc = tieBreaker.desc ?? false;
        const ta = asComparable(a[tbKey]);
        const tb = asComparable(b[tbKey]);
        if (ta === null && tb === null) return 0;
        if (ta === null) return 1;
        if (tb === null) return -1;
        let tbCompare = 0;
        if (typeof ta === "number" && typeof tb === "number") {
          tbCompare = ta - tb;
        } else {
          tbCompare = ta < tb ? -1 : ta > tb ? 1 : 0;
        }
        return tbDesc ? -tbCompare : tbCompare;
      }

      return 0;
    });
    return next;
  }, [columns, rows, sortKey, sortDesc, tieBreaker]);

  function onSort(key: string) {
    if (key === sortKey) {
      setSortDesc((value) => !value);
      return;
    }
    setSortKey(key);
    setSortDesc(false);
  }

  return (
    <div className="table-wrap">
      <table className={tableClassName}>
        <thead>
          <tr>
            {columns.map((column, colIdx) => (
              <th
                key={`${colIdx}-${column.key}`}
                className={classNames(
                  sortKey === column.key ? "active-sort" : "",
                  column.align ? `align-${column.align}` : "",
                  column.headerClassName
                )}
                onClick={() => onSort(column.key)}
              >
                {column.label}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {sorted.map((row, index) => (
            <tr
              key={`${index}-${String(row[rowIdKey] ?? "row")}`}
              className={rowClassName ? rowClassName(row, index) : undefined}
            >
              {columns.map((column, colIdx) => {
                const value = row[column.key];
                const customCellClass =
                  typeof column.cellClassName === "function" ? column.cellClassName(value, row) : column.cellClassName;
                return (
                  <td key={`${colIdx}-${column.key}`} className={classNames(column.align ? `align-${column.align}` : "", customCellClass)}>
                    {column.render ? column.render(value, row) : formatCell(value)}
                  </td>
                );
              })}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
