import * as FileSystem from 'expo-file-system/legacy';
import * as IntentLauncher from 'expo-intent-launcher';
import { Platform } from 'react-native';

import type { ReleaseInfo } from './release';

/**
 * 应用内更新：把 APK 下到缓存目录，核对大小，再交给系统安装器。
 *
 * 两件刻意没做的事：
 * - 不在端上算 sha256。APK 有几十 MB，把它读成 base64 再进 JS 摘要会把
 *   低端机的内存顶满；校验放在发布脚本侧（服务器上的文件是对的），端上只
 *   核对 size_bytes 挡住下载被截断的情况。
 * - 不做静默安装。那需要系统签名或 MDM，「允许安装未知应用」必须由用户
 *   自己在系统设置里开。
 */

const INSTALL_ACTION = 'android.intent.action.VIEW';
const APK_MIME_TYPE = 'application/vnd.android.package-archive';
/** FLAG_GRANT_READ_URI_PERMISSION：让系统安装器能读我们 FileProvider 给的 content:// */
const GRANT_READ = 1;

export type DownloadProgress = {
  loaded: number;
  percent: number;
  total: number;
};

export function downloadPercent(loaded: number, total: number): number {
  if (!Number.isFinite(total) || total <= 0) return 0;
  return Math.max(0, Math.min(100, Math.round((loaded / total) * 100)));
}

/** 服务器给的大小和实际下到的大小必须一致，否则当作下载被截断。 */
export function downloadedSizeMatches(
  actual: number | undefined,
  expected: number,
): boolean {
  return actual !== undefined && actual === expected;
}

export function apkCachePath(
  release: ReleaseInfo,
  cacheDirectory: string | null,
): string {
  if (cacheDirectory === null) {
    throw new Error('没有可用的缓存目录，下载不了安装包');
  }
  return `${cacheDirectory}antang-${release.versionCode}.apk`;
}

async function deleteIfExists(uri: string): Promise<void> {
  await FileSystem.deleteAsync(uri, { idempotent: true });
}

export async function downloadApk(
  release: ReleaseInfo,
  onProgress: (progress: DownloadProgress) => void,
): Promise<string> {
  if (Platform.OS !== 'android') {
    throw new Error('应用内安装目前只支持 Android');
  }
  const target = apkCachePath(release, FileSystem.cacheDirectory);
  // 上次失败留下的半截文件不要复用：长度可能刚好对不上，也可能被当成本次结果。
  await deleteIfExists(target);

  const download = FileSystem.createDownloadResumable(
    release.apkUrl,
    target,
    {},
    (progress) => {
      onProgress({
        loaded: progress.totalBytesWritten,
        percent: downloadPercent(
          progress.totalBytesWritten,
          progress.totalBytesExpectedToWrite,
        ),
        total: progress.totalBytesExpectedToWrite,
      });
    },
  );
  const result = await download.downloadAsync();
  if (result === undefined) {
    throw new Error('下载中断了，再试一次。');
  }
  const info = await FileSystem.getInfoAsync(result.uri);
  const size = info.exists ? info.size : undefined;
  if (!info.exists || !downloadedSizeMatches(size, release.sizeBytes)) {
    await deleteIfExists(result.uri);
    throw new Error('下载的文件不完整，再试一次。');
  }
  return result.uri;
}

export async function installApk(apkUri: string): Promise<void> {
  // file:// 从 Android 7 起不能在 Intent 里直接传（FileUriExposedException），
  // 必须换成 FileProvider 的 content://。
  const contentUri = await FileSystem.getContentUriAsync(apkUri);
  try {
    await IntentLauncher.startActivityAsync(INSTALL_ACTION, {
      data: contentUri,
      flags: GRANT_READ,
      type: APK_MIME_TYPE,
    });
  } catch (error) {
    throw new Error(
      `没能打开系统安装器${
        error instanceof Error ? `：${error.message}` : ''
      }。到「设置 → 应用 → 安糖心语 → 安装未知应用」里允许之后再试一次。`,
    );
  }
}

export async function downloadAndInstall(
  release: ReleaseInfo,
  onProgress: (progress: DownloadProgress) => void,
): Promise<void> {
  const apkUri = await downloadApk(release, onProgress);
  await installApk(apkUri);
}
