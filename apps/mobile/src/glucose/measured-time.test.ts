import { measuredTimeLabel } from './measured-time';

describe('measuredTimeLabel', () => {
  it('shows the clock when the patient gave a real time', () => {
    expect(measuredTimeLabel('2026-10-29T07:10:00+08:00', 'exact')).toBe(
      '10-29 07:10',
    );
  });

  it('names the daypart instead of pretending to know the minute', () => {
    // 患者只说「早上」：时间是该时段的代表时刻 07:00，界面必须写「大概」。
    expect(measuredTimeLabel('2026-10-29T07:00:00+08:00', 'daypart')).toBe(
      '10-29 早上（大概）',
    );
    expect(measuredTimeLabel('2026-10-29T20:00:00+08:00', 'daypart')).toBe(
      '10-29 晚上（大概）',
    );
  });

  it('falls back to the clock for an hour it cannot name', () => {
    // 认不出的时段宁可显示时刻，也不要叫错时段。
    expect(measuredTimeLabel('2026-10-29T09:00:00+08:00', 'daypart')).toBe(
      '10-29 09:00',
    );
  });

  it('treats a missing precision as exact', () => {
    expect(measuredTimeLabel('2026-10-29T09:00:00+08:00', undefined)).toBe(
      '10-29 09:00',
    );
  });
});
