/** SSE (Server-Sent Events) 连接Hook —— 管理EventSource生命周期 */

import { useEffect, useRef, useCallback } from 'react';
import { useGameStore } from '../store/gameStore';
import type { SSECallback } from '../types/events';

/** 解析SSE数据行，处理多行data */
function parseSSEData(lines: string[]): Record<string, unknown> | null {
  const dataLines = lines
    .filter((l) => l.startsWith('data: '))
    .map((l) => l.slice(6));

  if (dataLines.length === 0) return null;

  try {
    return JSON.parse(dataLines.join('\n'));
  } catch {
    return null;
  }
}

export function useSSE(sessionId: string | null) {
  const eventSourceRef = useRef<EventSource | null>(null);
  const lastSeqRef = useRef(0);
  const reconnectTimeoutRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  const store = useGameStore;

  const connect = useCallback(() => {
    if (!sessionId) return;

    // 关闭旧连接
    if (eventSourceRef.current) {
      eventSourceRef.current.close();
    }

    const url = `/api/game/${sessionId}/stream?last_event_seq=${lastSeqRef.current}`;
    const es = new EventSource(url);
    eventSourceRef.current = es;

    // 连接成功
    es.onopen = () => {
      console.log(`[SSE] 已连接到会话 ${sessionId}`);
    };

    // 定义事件处理器
    const handlers: Record<string, (data: Record<string, unknown>) => void> = {
      intro: (data) => {
        const scene = data.scene as string;
        if (scene) {
          store.getState().appendNarrativeText(scene);
        }
        store.getState().setProcessing(false);
      },

      narrative: (data) => {
        const token = data.token as string;
        if (token) {
          store.getState().appendToken(token);
        }
      },

      narrative_flush: (data) => {
        const fullText = data.full_text as string;
        if (fullText) {
          store.getState().appendNarrativeText(fullText);
        }
      },

      dice_roll: (data) => {
        store.getState().appendDiceRoll({
          skill: data.skill as string,
          dc: data.dc as number,
          roll: data.roll as number,
          modifier: (data.modifier as number) || 0,
          result: data.result as string,
        });
      },

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
        store.getState().updateStatus(update as any);
      },

      choices: (data) => {
        const options = data.options as string[];
        if (Array.isArray(options)) {
          store.getState().setChoices(options);
        }
      },

      game_event: (data) => {
        store.getState().appendGameEvent({
          type: data.type as string,
          description: data.description as string,
          extra: data.extra as Record<string, unknown> | undefined,
        });

        // 处理战斗事件
        const extra = data.extra as Record<string, unknown> | undefined;
        if (data.type === 'combat' && extra) {
          store.getState().setCombat({
            active: !extra.enemy_dead,
            enemyName: extra.enemy_name as string,
            enemyHp: extra.enemy_hp_remaining as number,
          });
          // 自动更新HP
          if (typeof extra.player_damage_taken === 'number' && extra.player_damage_taken > 0) {
            const s = store.getState();
            store.getState().updateStatus({
              hp: Math.max(0, s.status.hp - (extra.player_damage_taken as number)),
            });
          }
        }
      },

      error: (data) => {
        console.error('[SSE] 错误:', data.msg);
        store.getState().appendNarrativeText(`⚠️ ${data.msg}`);
      },

      journal_update: (data) => {
        // P2-12修复：SSE推送Journal数据，无需轮询API
        store.getState().setJournalData(data as Record<string, unknown>);
        // 同时同步场景信息到顶栏
        const scene = (data as Record<string, unknown>).scene as Record<string, unknown> | undefined;
        if (scene) {
          store.getState().setSceneInfo({
            location: scene.location as string || '',
            time: scene.time as string || '',
            weather: scene.weather as string || '',
            npcs_here: scene.npcs_here as string[] || [],
          });
        }
      },

      scene_update: (data) => {
        store.getState().setSceneInfo({
          location: data.location as string || '',
          time: data.time as string || '',
          weather: data.weather as string || '',
          npcs_here: data.npcs_here as string[] || [],
        });
      },

      end_of_turn: () => {
        // 先获取缓冲区文本用于提取决策
        const buf = store.getState().currentTokenBuffer;
        // 刷新打字机缓冲区
        store.getState().flushBuffer();
        // 从本轮AI回复中提取决策建议
        if (buf) {
          store.getState().extractDecisions(buf);
        }
        store.getState().setProcessing(false);
        // 清除骰子高亮
        setTimeout(() => store.getState().setLatestDiceRoll(null), 5000);
      },
    };

    // 监听所有标准事件类型
    const eventTypes = [
      'intro', 'narrative', 'narrative_flush', 'dice_roll',
      'state_update', 'choices', 'game_event', 'error', 'end_of_turn',
      'journal_update', 'scene_update',
    ];

    for (const eventType of eventTypes) {
      es.addEventListener(eventType, (event: MessageEvent) => {
        try {
          const data = JSON.parse(event.data);
          const seq = data.seq as number | undefined;
          if (seq !== undefined) {
            lastSeqRef.current = seq;
          }
          handlers[eventType]?.(data);
        } catch (e) {
          console.error(`[SSE] 解析${eventType}事件失败:`, e);
        }
      });
    }

    // 连接错误 → 自动重连
    es.onerror = () => {
      console.warn('[SSE] 连接断开，3秒后重连...');
      es.close();
      // EventSource会自动重连，但我们可以做更可控的重连
      if (reconnectTimeoutRef.current) {
        clearTimeout(reconnectTimeoutRef.current);
      }
      reconnectTimeoutRef.current = setTimeout(() => {
        connect();
      }, 3000);
    };
  }, [sessionId]);

  useEffect(() => {
    connect();

    return () => {
      // 组件卸载时清理
      if (eventSourceRef.current) {
        eventSourceRef.current.close();
        eventSourceRef.current = null;
      }
      if (reconnectTimeoutRef.current) {
        clearTimeout(reconnectTimeoutRef.current);
      }
    };
  }, [connect]);

  return {
    reconnect: connect,
  };
}
