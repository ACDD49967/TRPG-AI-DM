/** SSE 处理器共用类型：各域工厂只依赖 store 读取与统计刷新。 */
import type { GameState } from '../../store/gameStore';

export type SSEHandler = (data: Record<string, unknown>) => void;

export interface SSEHandlerDeps {
  store: { getState: () => GameState };
  refreshMetrics: () => void;
}
