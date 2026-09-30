"use client";

import {
  Bar,
  BarChart,
  CartesianGrid,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import { chartMargin, chartTheme } from "@/lib/charts";
import { formatCompactCOP } from "@/lib/format";

interface Row {
  month: string;
  ingresos: number;
  gastos: number;
}

export function IncomeExpenseBars({ data }: { data: Row[] }) {
  return (
    <div className="h-64 w-full">
      <ResponsiveContainer width="100%" height="100%">
        <BarChart data={data} margin={chartMargin} barCategoryGap={18}>
          <CartesianGrid vertical={false} stroke={chartTheme.grid} />
          <XAxis
            dataKey="month"
            axisLine={false}
            tickLine={false}
            tick={{ fill: chartTheme.axis, fontSize: 11 }}
          />
          <YAxis
            axisLine={false}
            tickLine={false}
            tick={{ fill: chartTheme.axis, fontSize: 11 }}
            tickFormatter={(v) => formatCompactCOP(v).replace("$", "")}
            width={44}
          />
          <Tooltip
            cursor={{ fill: "hsl(var(--surface-sunken))", opacity: 0.6 }}
            contentStyle={{
              background: chartTheme.tooltipBg,
              border: `1px solid ${chartTheme.tooltipBorder}`,
              borderRadius: 10,
              fontSize: 12,
              boxShadow: "0 8px 24px -8px rgb(15 23 42 / 0.15)",
            }}
            formatter={(v) => formatCompactCOP(Number(v))}
          />
          <Bar dataKey="ingresos" fill={chartTheme.income} radius={[4, 4, 0, 0]} maxBarSize={28} />
          <Bar dataKey="gastos" fill={chartTheme.expense} radius={[4, 4, 0, 0]} maxBarSize={28} />
        </BarChart>
      </ResponsiveContainer>
      <div className="mt-2 flex justify-end gap-4 text-2xs text-ink-subtle">
        <LegendDot color={chartTheme.income} label="Ingresos" />
        <LegendDot color={chartTheme.expense} label="Gastos" />
      </div>
    </div>
  );
}

function LegendDot({ color, label }: { color: string; label: string }) {
  return (
    <span className="inline-flex items-center gap-1.5">
      <span className="h-2 w-2 rounded-sm" style={{ background: color }} />
      {label}
    </span>
  );
}
