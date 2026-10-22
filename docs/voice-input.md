# 语音输入（L2：转写 + 声音的粗状态）

低血糖当下的状态是手抖、心慌、脑子发木——打字打不完一句话。语音输入要解决的是这个时刻，
不是"给产品加一个语音功能"。

论文 Fig 1 把 `Text, voice, emotion` 画成同一类输入。这一版把 `emotion` 落到**听感**上，
不做声学情绪识别：留下的是"语速偏快、声音偏轻、呼吸声可闻"这类可以数出来的东西，
加上模型自己的置信度，而不是"焦虑 0.72"。

## 一、边界：音频不留存，只留几个标量

请求进来 → 在内存里读一次 → 返回文字（以及可选的听感），**音频不落库、不落盘、不写日志**。
用户说"我刚才差点晕过去"时，声音里有喘，但那声喘不该变成数据库里的一条资产。

留下的只有 `speech_cues` 表里的一行：`pace` / `energy` / `breathing` / `confidence` /
`model_name` / `heard_at` / `expires_at` / `consumed_at`。
它存活 10 分钟（`SPEECH_CUE_WINDOW_SECONDS = 600`）、只被下一轮**成功发出**的对话读一次，
然后在数据库里留着（可随消息一起删）。**不返回给客户端、不出现在界面上**。

代价是转写失败只能让用户重说一遍（没有原件可重试）。这一条是刻意的。

## 二、接口

```
POST /api/v1/voice/transcribe      (multipart/form-data, 字段名 file, 需登录)
→ 200 {"text": "今天早上有点低血糖"}
```

响应里没有听感字段：它只影响下一轮回答的语气，不是给用户看的数据。

两条通道，由 `HACHIMI_AUDIO_MODEL_NAME` 决定：

| 配置 | 走的路径 | 产物 |
| --- | --- | --- |
| 留空（默认） | `/audio/transcriptions`（`HACHIMI_TRANSCRIBE_MODEL_NAME`，默认 `whisper-1`，`language=zh`） | 只有文字 |
| 配了模型（如 `gemini-3.8-flash`） | `/chat/completions` + `input_audio`（base64，`temperature=0`） | 文字 + 听感（JSON 解析） |

- 只接受音频容器：`audio/m4a`、`audio/mp4`、`audio/aac`、`audio/mpeg`、`audio/wav`、`audio/webm`、`audio/ogg`。
  其他类型 `415`；空文件 `422`；超过 `VOICE_MAX_AUDIO_BYTES`（默认 10MB）`413`。
- 上游失败一律 `502`，文案是给人看的（"语音转写服务连不上，稍后再试。"），
  **不透传上游状态码和报文**——那不是用户能修的东西。
- 转写结果为空或只有空白，当作"没听到声音"，返回 `422`（不是 `502`：这段输入里没有人声，
  让用户再说一遍而不是稍后再试）。多模态模型对静音会**编造内容**，所以挡了三道：
  1. 提示词先要求 `heard_speech`，为 `false` 时转写一律不采信（`NoSpeechError`）。
  2. 服务端对 16 位 PCM WAV 直接读采样，峰值低于 64（约 −54 dBFS）就判静音，根本不发给模型
     （`api/src/antang_api/voice/silence.py`）。m4a 判断不了，明确不猜。
  3. App 端录音开着 `isMeteringEnabled`，整段的最响分贝低于 −50 就不上传，直接提示"没听到声音"。
  实测证据：同一段数字静音，1 秒时模型返回空转写（守住），8 秒时返回
  `{"heard_speech": true, "transcript": "怎么做一顿丰盛的晚餐"}`——所以只靠提示词不够，
  必须在本地先做确定性的判断。
- 听感存不上（数据库出错）只记日志、不影响转写本身：它是附加信息，不是这条消息能不能用的前提。

## 三、为什么这么保守

- **低血糖本身会改变声音**：喘、发虚、语速乱，正是焦虑的"声音特征"。把生理症状读成情绪，
  代价可能是当着一个正在低血糖的人说他"听起来很焦虑"。
- **误判的代价不对称**：说错一句"你听起来很害怕"，比少说一句安慰更伤人，也可能让用户
  开始修饰自己的声音。
- **项目不做诊断**：所以只写听感 + 置信度，写进提示词时明确"不要提到你听到了什么声音"、
  "不要说「你听起来很焦虑」"、"与用户说出口的话冲突时以说的话为准"。
- 三项听感全是 `unknown`、或者模型没给置信度时，这一条直接丢弃——没有信息量的 cue
  只会让下一轮多一段噪声。

## 四、为什么不做别的方案

- **不做端上识别**（whisper.cpp / on-device）：T1D 用户群手机不一定够新，模型体积与首包延迟都不可控；
  而且端上模型识别不好用药名。
- **不做声学情绪识别模型**：训练数据、标注口径、临床验证都没有，做出来的分数无法解释，
  也过不了"这句话为什么这么说"的追问。
- **不做长录音/语音消息**：这是对话输入，转完就进输入框，用户自己决定发不发。存语音消息会立刻带来
  "这段录音谁能看"的问题。
- **不做自动发送**：转写只是把文字填进输入框。识别错一个剂量单位直接发出去的后果太大。

## 五、部署与验证

```bash
bash api/scripts/test          # tests/test_voice_transcribe.py（13 个）+ tests/test_speech_cue.py（15 个）
```

上线时在 `~/antang-prod/api/.env` 补：

```
HACHIMI_TRANSCRIBE_MODEL_NAME=whisper-1
HACHIMI_AUDIO_MODEL_NAME=gemini-3.8-flash   # 想同时拿听感时才配
```

注意：本项目的生产中转站（`HACHIMI_BASE_URL`）目前**没有 whisper 模型**，
`/audio/transcriptions` 对 `whisper-1` / `whisper-large-v3` / `gpt-4o-transcribe` 都返回
`503 model_not_found`。所以线上要真正转写，只能配 `HACHIMI_AUDIO_MODEL_NAME` 走多模态通道；
留空时这条接口会稳定返回 502（代码正确、通道不通）。

移动端（2026-10-21 已完成代码）：输入框左侧的麦克风按钮（`apps/mobile/src/chat/ChatScreen.tsx`
的 `voiceButton`）调 `apps/mobile/src/chat/useVoiceInput.ts` 的状态机（`idle → recording → transcribing`），
录音用 `expo-audio` 的 `RecordingPresets.LOW_QUALITY`（`.m4a`），转写成功后由
`mergeTranscriptIntoDraft` 填进输入框——**不自动发送**。权限在 `apps/mobile/app.json` 加了
`android.permission.RECORD_AUDIO`。单段上限 2 分钟（`MAX_VOICE_MILLISECONDS`），超了让人分两段说。

**这颗按钮默认不显示**：`apps/mobile/src/config.ts` 的 `VOICE_INPUT_ENABLED` 只在
`EXPO_PUBLIC_VOICE_INPUT=1` 时为真。理由（2026-10-21 的决定）：语音目前不改变回应质量——它把话
变成文字，系统键盘自带的语音输入也能做到；而 m4a 的静音判定还差 ffmpeg 方案（见 §二 第三道闸）。
所以正式包不带麦克风，先不引入「录了却被编造」的风险；要上机试就打个
`EXPO_PUBLIC_VOICE_INPUT=1` 的测试包，按下面的清单验。

打 APK 时的验证清单：

1. 点麦克风说话 → 再点一下结束 → 输入框出现文字，且能手动改、能删；
2. 拒绝麦克风权限 → 提示「需要麦克风权限才能说话，可以在系统设置里打开。」，不静默失败；
3. 弱网/超时 → 提示「没听清，再说一遍试试。」，输入框里不留半截文字；
4. 抓包确认请求体里只有音频、响应里只有 `text`，服务端日志里没有音频内容；
5. 录一句语速明显慢的话，下一轮回答里**不该**出现"你听起来……"这类对声音的描述
   （听感只能改语气，不能外显）；
6. 录音中锁屏/切后台回来，按钮状态能回到可再次录音（`mediaServicesDidReset` 由
   `useAudioRecorderState` 暴露，本轮没有自动恢复，属于已知限制）。
