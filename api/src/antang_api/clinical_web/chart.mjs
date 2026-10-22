const NS = 'http://www.w3.org/2000/svg';

export function glucoseValue(mgDl, unit = 'mmol') {
  return unit === 'mg' ? mgDl : mgDl / 18;
}

export function chartLayout(records, start, end, gapHours = 6) {
  const begin = new Date(start).getTime();
  const finish = new Date(end).getTime();
  if (!Number.isFinite(begin) || !Number.isFinite(finish) || finish <= begin) throw new Error('曲线时间范围不正确');
  const points = records.map(record => {
    const time = new Date(record.time).getTime();
    if (!Number.isFinite(time) || !Number.isFinite(record.value)) throw new Error('曲线记录格式不正确');
    return { ...record, time };
  }).sort((a, b) => a.time - b.time);
  const segments = [];
  for (const point of points) {
    const previous = segments.at(-1)?.at(-1);
    if (!previous || point.time - previous.time > gapHours * 3600000 || point.source !== previous.source) segments.push([point]);
    else segments.at(-1).push(point);
  }
  return { points, segments, begin, finish };
}

function svgNode(tag, attributes = {}, text) {
  const node = document.createElementNS(NS, tag);
  for (const [key, value] of Object.entries(attributes)) node.setAttribute(key, String(value));
  if (text !== undefined) node.textContent = String(text);
  return node;
}

function empty(container, text) {
  const node = document.createElement('div');
  node.className = 'chart-empty';
  node.textContent = text;
  container.replaceChildren(node);
}

export function lineChart(container, records, { start, end, unit = '', reference = null, compact = false, gapHours = 6, simulated = false }) {
  const { points, segments, begin, finish } = chartLayout(records, start, end, gapHours);
  if (!points.length) { empty(container, '此时间范围内暂无记录'); return; }
  const width = 1000, height = compact ? 190 : 300;
  const left = 46, right = 18, top = 18, bottom = height - 36;
  const values = [...points.map(point => point.value), ...(reference ?? [])];
  const low = Math.max(0, Math.floor(Math.min(...values) * .8));
  const high = Math.max(low + 1, Math.ceil(Math.max(...values) * 1.16));
  const x = time => left + (time - begin) / (finish - begin) * (width - left - right);
  const y = value => bottom - (value - low) / (high - low) * (bottom - top);
  const svg = svgNode('svg', { viewBox: `0 0 ${width} ${height}`, role: 'img', 'aria-label': `${unit} ${simulated ? "模拟演示" : "已保存"}记录变化曲线` });
  svg.append(svgNode('title', {}, `共 ${points.length} 个${simulated ? "模拟演示" : "记录"}采样点；间隔超过 ${gapHours} 小时断开连线。`));
  if (reference) svg.append(svgNode('rect', { class: 'reference', x: left, y: y(reference[1]), width: width - left - right, height: y(reference[0]) - y(reference[1]) }));
  for (let i = 0; i <= 4; i++) {
    const value = low + (high - low) * i / 4;
    svg.append(svgNode('line', { class: 'grid', x1: left, x2: width - right, y1: y(value), y2: y(value) }));
    svg.append(svgNode('text', { x: left - 12, y: y(value) + 4, 'text-anchor': 'end' }, value >= 30 ? Math.round(value) : value.toFixed(1)));
  }
  for (let i = 0; i <= 5; i++) {
    const time = begin + (finish - begin) * i / 5;
    const date = new Date(time);
    svg.append(svgNode('text', { x: x(time), y: height - 10, 'text-anchor': i === 0 ? 'start' : i === 5 ? 'end' : 'middle' }, `${date.getMonth() + 1}/${date.getDate()} ${date.getHours()}:00`));
  }
  for (const segment of segments) {
    if (segment.length > 1) svg.append(svgNode('path', { class: 'line', d: segment.map((point, i) => `${i ? 'L' : 'M'} ${x(point.time).toFixed(2)} ${y(point.value).toFixed(2)}`).join(' ') }));
  }
  for (const point of points) {
    const circle = svgNode('circle', { class: 'point', cx: x(point.time), cy: y(point.value), r: compact ? 2 : 3, tabindex: '0' });
    circle.append(svgNode('title', {}, `${new Date(point.time).toLocaleString()}\n${point.value.toFixed(1)} ${unit}${point.label ? '\n' + point.label : ''}`));
    svg.append(circle);
  }
  container.replaceChildren(svg);
}

export function stepsChart(container, days, start, end) {
  if (!days.length) { empty(container, '此时间范围内暂无步数记录'); return; }
  const begin = new Date(start).getTime(), finish = new Date(end).getTime();
  const max = Math.max(1, ...days.map(day => day.steps));
  const svg = svgNode('svg', { viewBox: '0 0 1000 180', role: 'img', 'aria-label': '每日已同步步数' });
  const barWidth = Math.max(2, Math.min(45, 820 / Math.max(1, (finish - begin) / 86400000)));
  for (const [i, day] of days.entries()) {
    const time = new Date(day.day + 'T12:00:00').getTime();
    const x = 40 + (time - begin) / (finish - begin) * 920;
    const height = day.steps / max * 125;
    const bar = svgNode('rect', { x: x - barWidth / 2, y: 140 - height, width: barWidth, height: Math.max(1, height), fill: '#96c7ab', rx: 3 });
    bar.append(svgNode('title', {}, `${day.day} · ${day.steps.toLocaleString()} 步`));
    svg.append(bar);
    if (days.length <= 12 || i % Math.ceil(days.length / 8) === 0) svg.append(svgNode('text', { x, y: 165, 'text-anchor': 'middle' }, day.day.slice(5)));
  }
  container.replaceChildren(svg);
}
