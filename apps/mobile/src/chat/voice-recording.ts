/**
 * 语音输入的纯逻辑：录音只活在这一次输入里，转成文字写进输入框就结束。
 *
 * 这里刻意不放任何原生模块调用——录音状态机在 useVoiceInput，接口请求在
 * ApiClient.transcribeVoice，这一层只做能单测的判断。
 */

/** 服务端按 voice_max_audio_bytes 收文件，这里先从时长上拦一道，别让人白等上传。 */
export const MAX_VOICE_MILLISECONDS = 120_000;

/** expo-audio 的 LOW_QUALITY 预设就是 m4a；后端支持的音频类型里有 audio/m4a。 */
export const VOICE_RECORDING_MIME_TYPE = 'audio/m4a';

export function formatVoiceDuration(milliseconds: number): string {
  const totalSeconds = Math.max(0, Math.floor(milliseconds / 1000));
  const minutes = Math.floor(totalSeconds / 60);
  const seconds = totalSeconds % 60;
  return `${minutes}:${seconds.toString().padStart(2, '0')}`;
}

export function isVoiceTooLong(milliseconds: number): boolean {
  return milliseconds > MAX_VOICE_MILLISECONDS;
}

/**
 * 录音期间达到过的最小分贝（expo-audio 的 metering 是 dBFS，0 最响）。
 *
 * 低于这个阈值就当成没听到人说话：上游模型对静音会编造内容（实测 8 秒
 * 静音也能转出一整句话），而这比"没听清"糟得多——用户会看到一个自己从没
 * 说过的句子。所以静音在手机上就挡掉，不要上传。
 */
export const VOICE_SILENCE_DB = -50;

export function isTooQuiet(loudestDb: number | null): boolean {
  return loudestDb !== null && loudestDb < VOICE_SILENCE_DB;
}

export function voiceFileName(now: Date = new Date()): string {
  return `voice-${now.getTime()}.m4a`;
}

/**
 * 把转写结果接到草稿后面。中文直接接，英文单词之间留一个空格——
 * 不然用户说了一句中文再补一句英文，两个词会粘在一起。
 */
export function mergeTranscriptIntoDraft(
  draft: string,
  transcript: string,
): string {
  const spoken = transcript.trim();
  if (spoken.length === 0) return draft;
  const kept = draft.trimEnd();
  if (kept.length === 0) return spoken;
  const glue =
    /[A-Za-z0-9]$/.test(kept) && /^[A-Za-z0-9]/.test(spoken) ? ' ' : '';
  return `${kept}${glue}${spoken}`;
}
