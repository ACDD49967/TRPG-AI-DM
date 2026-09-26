/** 战斗事件 SSE 处理器：先攻、战场态势、状态浮层、战斗记录与多敌状态。 */
import { useToastStore } from '../../store/toastStore';
import type { BattlefieldPlacement, InitiativeEntry } from '../../store/gameStore';
import type { SSEHandler, SSEHandlerDeps } from './handlerTypes';

export function createCombatHandlers(deps: SSEHandlerDeps): Record<string, SSEHandler> {
  const { store } = deps;
  return {
    game_event: (data) => {
      store.getState().appendGameEvent({
        type: data.type as string,
        description: data.description as string,
        extra: data.extra as Record<string, unknown> | undefined,
      });

      // 关键状态用浮层提示，避免玩家只从叙事文字里察觉（或干脆漏看）
      const eventType = data.type as string;
      // 先攻顺序由后端维护（谁先动、谁还没动），前端只负责展示
      if (eventType === 'initiative') {
        const extra = data.extra as
          { round?: number; current?: string; order?: InitiativeEntry[] } | undefined;
        if (extra && Array.isArray(extra.order)) {
          store.getState().setInitiative({
            round: Number(extra.round ?? 1),
            current: String(extra.current ?? ''),
            order: extra.order,
          });
        }
      }
      // 战场态势：距离档位与掩体（set_tactical_state 推送）
      if (eventType === 'battlefield') {
        const extra = data.extra as { placements?: BattlefieldPlacement[] } | undefined;
        if (extra && Array.isArray(extra.placements)) {
          store.getState().mergePlacements(extra.placements);
        }
      }
      if (eventType === 'dying') {
        useToastStore.getState().showToast(
          '⚰️ 你倒下了——昏迷无法行动，每回合需要掷死亡豁免。', 'error');
      } else if (eventType === 'player_death') {
        useToastStore.getState().showToast(
          '☠️ 角色已死亡。可以创建新角色继续这个世界的冒险。', 'error');
      } else if (eventType === 'feat_available') {
        const level = (data.extra as Record<string, unknown> | undefined)?.level;
        if (typeof level === 'number') store.getState().setPendingLevelUp(level);
        useToastStore.getState().showToast(
          `🎯 升至 ${level ?? ''} 级！可以分配属性提升或专长（选择界面已打开）。`, 'success');
      }

      // 战斗记录统一进入面板
      const evDesc = data.description as string || '';
      store.getState().appendCombatLog({
        kind: data.type === 'combat' ? (evDesc.includes('攻击') ? 'enemy' : 'combat') : 'combat',
        text: evDesc,
        extra: data.extra as Record<string, unknown> | undefined,
      });

      // 处理多敌人战斗状态
      const extra = data.extra as Record<string, unknown> | undefined;
      if (data.type === 'combat' && extra) {
        const prev = store.getState().combat;
        const enemyName = extra.enemy_name as string || '敌人';
        const prevHp = prev?.enemies?.find(e => e.name === enemyName)?.hp ?? 0;
        const enemyHp = typeof extra.enemy_hp_remaining === 'number' ? extra.enemy_hp_remaining : prevHp;
        let enemies = prev?.enemies ? [...prev.enemies] : [];
        // 后端提供完整敌人快照时优先使用，保证多敌战斗全部显示
        if (Array.isArray(extra.enemies)) {
          const snapshot = extra.enemies as Array<{ name: string; hp: number; pending_regen?: boolean }>;
          const map = new Map(enemies.map(e => [e.name, e]));
          for (const e of snapshot) map.set(e.name, { name: e.name, hp: e.hp, pending_regen: e.pending_regen });
          enemies = [...map.values()];
        } else {
          const idx = enemies.findIndex(e => e.name === enemyName);
          if (idx >= 0) enemies[idx] = { name: enemyName, hp: enemyHp };
          else enemies.push({ name: enemyName, hp: enemyHp });
        }
        const anyAlive = enemies.length === 0
          ? !extra.enemy_dead
          : enemies.some(e => e.hp > 0 || e.pending_regen);
        store.getState().setCombat({
          active: anyAlive,
          enemyName,
          enemyHp,
          enemies,
        });
        // HP 以 state_update 事件为准，避免与后端已推送的权威状态重复扣血
      }
    },
  };
}
