/**
 * SSE 事件处理器表（从 useSSE 拆出）。
 *
 * 按叙事、状态、战斗三个域分别实现，这里只做组合；不含连接/重连生命周期。
 * 需要的东西（store、refreshMetrics）由 useSSE 通过 deps 注入。
 */
import { createCombatHandlers } from './sse/combatHandlers';
import { createNarrativeHandlers } from './sse/narrativeHandlers';
import { createStateHandlers } from './sse/stateHandlers';
import type { SSEHandler, SSEHandlerDeps } from './sse/handlerTypes';

export type { SSEHandler, SSEHandlerDeps } from './sse/handlerTypes';

export function createSSEHandlers(deps: SSEHandlerDeps): Record<string, SSEHandler> {
  return {
    ...createNarrativeHandlers(deps),
    ...createStateHandlers(deps),
    ...createCombatHandlers(deps),
  };
}
