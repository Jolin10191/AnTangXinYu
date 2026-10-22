import {
  MAX_VOICE_MILLISECONDS,
  VOICE_SILENCE_DB,
  formatVoiceDuration,
  isTooQuiet,
  isVoiceTooLong,
  mergeTranscriptIntoDraft,
  voiceFileName,
} from './voice-recording';

describe('voice recording helpers', () => {
  test('formats a duration as minutes and padded seconds', () => {
    expect(formatVoiceDuration(0)).toBe('0:00');
    expect(formatVoiceDuration(7_400)).toBe('0:07');
    expect(formatVoiceDuration(61_000)).toBe('1:01');
    expect(formatVoiceDuration(-1)).toBe('0:00');
  });

  test('rejects recordings longer than the limit', () => {
    expect(isVoiceTooLong(MAX_VOICE_MILLISECONDS)).toBe(false);
    expect(isVoiceTooLong(MAX_VOICE_MILLISECONDS + 1)).toBe(true);
  });

  test('names the file from the clock so two takes do not collide', () => {
    expect(voiceFileName(new Date(1_700_000_000_000))).toBe(
      'voice-1700000000000.m4a',
    );
  });

  test('appends a Chinese transcript without inventing a space', () => {
    expect(mergeTranscriptIntoDraft('', '我昨晚又没睡着')).toBe('我昨晚又没睡着');
    expect(mergeTranscriptIntoDraft('嗯，', '我昨晚又没睡着')).toBe(
      '嗯，我昨晚又没睡着',
    );
  });

  test('keeps a space between two English words', () => {
    expect(mergeTranscriptIntoDraft('I am', 'tired')).toBe('I am tired');
  });

  test('leaves the draft alone when the transcript is blank', () => {
    expect(mergeTranscriptIntoDraft('已经写好的字', '   ')).toBe('已经写好的字');
  });

  test('treats a take that never got loud as silence', () => {
    // 上游对静音会编造内容，所以静音在手机上就挡掉，不上传。
    expect(isTooQuiet(null)).toBe(false);
    expect(isTooQuiet(VOICE_SILENCE_DB)).toBe(false);
    expect(isTooQuiet(VOICE_SILENCE_DB - 1)).toBe(true);
    expect(isTooQuiet(-12)).toBe(false);
  });
});
