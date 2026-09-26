/** 角色状态、日志快照、场景与媒体版本相关 SSE 处理器。 */
import type { SSEHandler, SSEHandlerDeps } from './handlerTypes';

/** 将后端 snake_case 状态字段映射为前端 camelCase，避免 maxHp/maxMp/maxSan 不更新 */
function normalizeStatusUpdate(data: Record<string, unknown>): Record<string, unknown> {
  const out: Record<string, unknown> = { ...data };
  if (out.max_hp !== undefined) {
    out.maxHp = out.max_hp;
    delete out.max_hp;
  }
  if (out.max_mp !== undefined) {
    out.maxMp = out.max_mp;
    delete out.max_mp;
  }
  if (out.max_san !== undefined) {
    out.maxSan = out.max_san;
    delete out.max_san;
  }
  return out;
}

export function createStateHandlers(deps: SSEHandlerDeps): Record<string, SSEHandler> {
  const { store } = deps;
  return {
    state_update: (data) => {
      const update: Record<string, unknown> = { ...data };
      // 展平 inventory —— 后端发送 {items:[...]} 格式
      if (typeof data.inventory === 'object' && data.inventory !== null && !Array.isArray(data.inventory)) {
        const inv = data.inventory as Record<string, unknown>;
        if (Array.isArray(inv.items)) {
          update.inventory = inv.items;
        }
      }
      // eslint-disable-next-line @typescript-eslint/no-explicit-any
      store.getState().updateStatus(normalizeStatusUpdate(update) as any);
    },

    journal_update: (data) => {
      // P2-12修复：SSE推送Journal数据，无需轮询API
      store.getState().setJournalStatus('synced');
      store.getState().setJournalData(data as Record<string, unknown>);
      // 同时同步场景信息到顶栏
      const scene = (data as Record<string, unknown>).scene as Record<string, unknown> | undefined;
      if (scene) {
        store.getState().setSceneInfo({
          location: scene.location as string || '',
          time: scene.time as string || '',
          weather: scene.weather as string || '',
          npcs_here: scene.npcs_here as string[] || [],
          light: scene.light as string || '',
          light_source: scene.light_source as string || '',
        });
      }
    },

    maps_updated: () => {
      store.getState().bumpMediaVersion();
    },

    bestiary_updated: () => {
      store.getState().bumpMediaVersion();
    },

    spells_updated: () => {
      store.getState().bumpMediaVersion();
    },

    scene_update: (data) => {
      store.getState().setSceneInfo({
        location: data.location as string || '',
        time: data.time as string || '',
        weather: data.weather as string || '',
        npcs_here: data.npcs_here as string[] || [],
        light: data.light as string || '',
        light_source: data.light_source as string || '',
      });
    },
  };
}
