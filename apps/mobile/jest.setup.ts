import { ReadableStream } from 'stream/web';
import { TextDecoder, TextEncoder } from 'util';

Object.defineProperty(globalThis, 'ReadableStream', { value: ReadableStream });
Object.defineProperty(globalThis, 'TextDecoder', { value: TextDecoder });
Object.defineProperty(globalThis, 'TextEncoder', { value: TextEncoder });

// 单元测试不读 .env：给一个显式地址，避免 config.ts 在测试里抛错。
process.env.EXPO_PUBLIC_API_URL ??= 'https://api.antang.test';
