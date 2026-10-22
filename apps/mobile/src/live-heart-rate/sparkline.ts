export type SparklinePoint = {
  x: number;
  y: number;
};

/**
 * 把一串心率换算成 SVG 折线坐标：纵向按本段数据的最小/最大值铺满，
 * 所以看的是「这段有没有起伏」，不是绝对刻度（绝对刻度由旁边的大号读数负责）。
 */
export function buildSparklinePoints(
  values: readonly number[],
  width: number,
  height: number,
  padding = 4,
): SparklinePoint[] {
  if (values.length === 0) return [];
  const inner = Math.max(1, height - padding * 2);
  const minimum = Math.min(...values);
  const maximum = Math.max(...values);
  const span = maximum - minimum;
  const step = values.length > 1 ? width / (values.length - 1) : 0;
  return values.map((value, index) => ({
    x: values.length > 1 ? index * step : width / 2,
    y: span === 0
      ? padding + inner / 2
      : padding + inner - ((value - minimum) / span) * inner,
  }));
}

export function toSvgPoints(points: readonly SparklinePoint[]): string {
  return points.map((point) => `${point.x.toFixed(1)},${point.y.toFixed(1)}`).join(' ');
}
