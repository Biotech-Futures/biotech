import {
  Bar,
  BarChart,
  CartesianGrid,
  Cell,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";

type Row = { label: string; value: number; hint?: string };

type Props = {
  rows: Row[];
  /** Rendered under the value in the tooltip and in the table view. */
  unit?: string;
  format?: (value: number) => string;
  emptyMessage?: string;
};

/** A single-series horizontal bar chart.
 *
 *  Single series on purpose: every measure on this page is one quantity broken
 *  down by one dimension, so a second colour would encode nothing. That also
 *  keeps the palette out of trouble — this app's design system is achromatic
 *  (every --chart-* token has zero chroma), and inventing hues for it would
 *  both clash and put the burden of colourblind separation on a chart that
 *  does not need colour to be read at all.
 *
 *  Horizontal because the labels are words: category names and statuses do not
 *  fit under a vertical axis without rotating them.
 */
export function MeasureBars({ rows, unit, format, emptyMessage }: Props) {
  if (rows.length === 0) {
    return (
      <p className="text-muted-foreground py-6 text-sm">
        {emptyMessage ?? "Nothing in this window."}
      </p>
    );
  }

  const show = format ?? ((value: number) => String(value));

  return (
    <>
      <ResponsiveContainer width="100%" height={Math.max(120, rows.length * 40)}>
        <BarChart
          data={rows}
          layout="vertical"
          margin={{ top: 4, right: 48, bottom: 4, left: 8 }}
          barCategoryGap={6}
        >
          {/* Recessive: the grid is a reading aid, not a mark. */}
          <CartesianGrid horizontal={false} stroke="var(--border)" />
          <XAxis
            type="number"
            tick={{ fill: "var(--muted-foreground)", fontSize: 12 }}
            stroke="var(--border)"
            allowDecimals={false}
            // The axis needs the formatter too, not just the tooltip and the
            // table. Without it the durations chart ran "0 / 70000 / 140000 /
            // 210000 / 280000" in raw seconds while every other number on the
            // same page read "33h 58m".
            tickFormatter={show}
          />
          <YAxis
            type="category"
            dataKey="label"
            width={130}
            tick={{ fill: "var(--muted-foreground)", fontSize: 12 }}
            stroke="var(--border)"
          />
          <Tooltip
            cursor={{ fill: "var(--accent)" }}
            contentStyle={{
              background: "var(--popover)",
              border: "1px solid var(--border)",
              borderRadius: 6,
              fontSize: 12,
              // Text wears text tokens, never the mark colour.
              color: "var(--popover-foreground)",
            }}
            // Recharts types the tooltip value as possibly undefined, so it
            // is narrowed here rather than asserted away.
            formatter={(value) => [
              `${show(Number(value ?? 0))}${unit ? ` ${unit}` : ""}`,
              "",
            ]}
          />
          <Bar
            dataKey="value"
            fill="var(--chart-2)"
            // Rounded at the data end only, anchored to the baseline.
            radius={[0, 4, 4, 0]}
            isAnimationActive={false}
          >
            {rows.map((row) => (
              <Cell key={row.label} />
            ))}
          </Bar>
        </BarChart>
      </ResponsiveContainer>

      {/* The same numbers without the chart. Identity is never colour-alone
          here anyway, but a table is what a screen reader and a printout can
          actually use. */}
      <details className="mt-2">
        <summary className="text-muted-foreground cursor-pointer text-xs">
          Show as a table
        </summary>
        <table className="mt-2 w-full text-sm">
          <tbody>
            {rows.map((row) => (
              <tr key={row.label} className="border-b last:border-0">
                <th scope="row" className="py-1 text-left font-normal">
                  {row.label}
                </th>
                <td className="py-1 text-right tabular-nums">
                  {show(row.value)}
                  {unit ? ` ${unit}` : ""}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </details>
    </>
  );
}
