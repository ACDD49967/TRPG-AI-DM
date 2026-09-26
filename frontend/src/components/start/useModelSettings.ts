/**
 * 开始界面「API 连接 / 模型列表 / 向量模式 / 模型下载」的门面。
 *
 * 实现拆成两块：连接与端点预设 → `connectionSettings`，
 * 向量模式与模型下载 → `vectorSettings`。这里只做组合，
 * `StartScreen` 按名字解构的写法与类型导出都保持不变。
 */
import { useConnectionSettings } from './connectionSettings';
import { useVectorSettings } from './vectorSettings';

export type { EndpointPreset, Provider } from './connectionSettings';
export type { VectorMode } from './vectorSettings';

export function useModelSettings() {
  return {
    ...useConnectionSettings(),
    ...useVectorSettings(),
  };
}
