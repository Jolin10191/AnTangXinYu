import {
  RecordingPresets,
  requestRecordingPermissionsAsync,
  setAudioModeAsync,
  useAudioRecorder,
  useAudioRecorderState,
} from 'expo-audio';
import { useCallback, useEffect, useRef, useState } from 'react';

import {
  isTooQuiet,
  isVoiceTooLong,
  VOICE_RECORDING_MIME_TYPE,
  voiceFileName,
} from './voice-recording';

export type VoiceInputPhase = 'idle' | 'recording' | 'transcribing';

const TOO_LONG = '这段有点长，分两段说给我听。';
const TOO_QUIET = '没听到声音，再说一遍。';
const NO_PERMISSION = '需要麦克风权限才能说话，可以在系统设置里打开。';
const RECORD_FAILED = '没能开始录音，再试一次。';

type Transcribe = (recording: {
  mimeType: string;
  name: string;
  uri: string;
}) => Promise<string>;

function messageOf(error: unknown): string {
  return error instanceof Error && error.message.length > 0
    ? error.message
    : RECORD_FAILED;
}

/**
 * 一次录音的生命周期：申请权限 → 录 → 停 → 上传转写 → 文字进草稿。
 *
 * 音频不留在手机上：转写完就走，失败也不重试——重试要保住文件，
 * 而这些文件包含最敏感的内容（用户在自己家里说话）。方案 A 的取舍见
 * docs/voice-input.md。
 *
 * 开着 metering 是为了在本地判断"这段里有没有人声"：上游模型对静音会
 * 编造内容，让编出来的句子进输入框比让它报错更糟。
 */
export function useVoiceInput(transcribe: Transcribe, onTranscript: (text: string) => void) {
  const recorder = useAudioRecorder({
    ...RecordingPresets.LOW_QUALITY,
    isMeteringEnabled: true,
  });
  const recorderState = useAudioRecorderState(recorder, 200);
  const loudestDb = useRef<number | null>(null);
  const [phase, setPhase] = useState<VoiceInputPhase>('idle');
  const [error, setError] = useState<string | null>(null);

  const metering = recorderState.metering;
  useEffect(() => {
    if (phase !== 'recording' || typeof metering !== 'number') return;
    const current = loudestDb.current;
    if (current === null || metering > current) loudestDb.current = metering;
  }, [metering, phase]);

  const start = useCallback(async () => {
    if (phase !== 'idle') return;
    setError(null);
    loudestDb.current = null;
    try {
      const permission = await requestRecordingPermissionsAsync();
      if (!permission.granted) {
        setError(NO_PERMISSION);
        return;
      }
      await setAudioModeAsync({ allowsRecording: true, playsInSilentMode: true });
      await recorder.prepareToRecordAsync();
      recorder.record();
      setPhase('recording');
    } catch (failure) {
      await setAudioModeAsync({ allowsRecording: false }).catch(() => undefined);
      setError(messageOf(failure));
    }
  }, [phase, recorder]);

  const stop = useCallback(async () => {
    if (phase !== 'recording') return;
    const durationMillis = recorderState.durationMillis;
    const heardDb = loudestDb.current;
    try {
      await recorder.stop();
    } catch (failure) {
      await setAudioModeAsync({ allowsRecording: false }).catch(() => undefined);
      setError(messageOf(failure));
      setPhase('idle');
      return;
    }
    await setAudioModeAsync({ allowsRecording: false }).catch(() => undefined);

    if (isVoiceTooLong(durationMillis)) {
      setError(TOO_LONG);
      setPhase('idle');
      return;
    }
    if (isTooQuiet(heardDb)) {
      setError(TOO_QUIET);
      setPhase('idle');
      return;
    }
    const uri = recorder.uri;
    if (!uri) {
      setError(RECORD_FAILED);
      setPhase('idle');
      return;
    }

    setPhase('transcribing');
    try {
      const transcript = await transcribe({
        mimeType: VOICE_RECORDING_MIME_TYPE,
        name: voiceFileName(),
        uri,
      });
      if (transcript.trim().length > 0) onTranscript(transcript);
    } catch (failure) {
      setError(messageOf(failure));
    } finally {
      setPhase('idle');
    }
  }, [phase, recorder, recorderState.durationMillis, transcribe, onTranscript]);

  return {
    phase,
    durationMillis: recorderState.durationMillis,
    error,
    dismissError: useCallback(() => setError(null), []),
    start,
    stop,
  };
}
