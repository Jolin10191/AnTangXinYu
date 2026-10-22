import { buildSparklinePoints, toSvgPoints } from './sparkline';

test('lays the series across the full width, first point at 0 and last at width', () => {
  const points = buildSparklinePoints([60, 70, 80], 100, 40, 0);
  expect(points.map((point) => point.x)).toEqual([0, 50, 100]);
  expect(points[0].y).toBe(40);
  expect(points[2].y).toBe(0);
});

test('keeps a flat series on the middle line instead of dividing by zero', () => {
  const points = buildSparklinePoints([72, 72, 72], 100, 40, 4);
  expect(points.every((point) => point.y === 20)).toBe(true);
});

test('centers a single reading and returns nothing for an empty series', () => {
  expect(buildSparklinePoints([75], 100, 40, 4)).toEqual([{ x: 50, y: 20 }]);
  expect(buildSparklinePoints([], 100, 40)).toEqual([]);
});

test('renders svg points with one decimal place', () => {
  expect(toSvgPoints([{ x: 0, y: 12.345 }, { x: 10, y: 0 }])).toBe('0.0,12.3 10.0,0.0');
});
