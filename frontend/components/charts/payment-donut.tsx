"use client";

import { Cell, Pie, PieChart, ResponsiveContainer, Tooltip } from "recharts";
import { chartTheme } from "@/lib/charts";

interface Slice {
  key: string;
  label: string;
  value: number;
  tone: "success" | "warning" | "danger" | "neutral";
}

const TONE_COLOR: Record<string, string> = {
  success: chartTheme.donut[0],
  warning: chartTheme.donut[1],
  danger: chartTheme.donut[2],
  neutral: chartTheme.donut[3],
};

export function PaymentDonut({ data }: { data: Slice[] }) {
  const total = data.reduce((s, d) => s + d.value, 0);
  const primary = data[0];
  return (
    <div className="relative h-40 w-full">
      <ResponsiveContainer width="100%" height="100%">
        <PieChart>
          <Pie
            data={data}
            dataKey="value"
            nameKey="label"
            innerRadius={50}
            outerRadius={72}
            paddingAngle={2}
            stroke="none"
          >
            {data.map((s) => (
              <Cell key={s.key} fill={TONE_COLOR[s.tone]} />
            ))}
          </Pie>
          <Tooltip
            contentStyle={{
              background: chartTheme.tooltipBg,
              border: `1px solid ${chartTheme.tooltipBorder}`,
              borderRadius: 10,
              fontSize: 12,
            }}
            formatter={(v, _n, item) => [`${v}`, (item?.payload as { label?: string } | undefined)?.label ?? ""]}
          />
        </PieChart>
      </ResponsiveContainer>
      <div className="pointer-events-none absolute inset-0 flex flex-col items-center justify-center">
        <div className="font-mono text-lg font-semibold tabular-nums text-ink">{total}</div>
        <div className="text-2xs text-ink-subtle">{primary ? primary.label.toLowerCase() : "facturas"}</div>
      </div>
    </div>
  );
}
