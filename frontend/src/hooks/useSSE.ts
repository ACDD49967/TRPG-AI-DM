/** SSE (Server-Sent Events) 连接Hook —— 管理EventSource生命周期 */

import { useEffect, useRef, useCallback } from 'react';
import { useGameStore } from '../store/gameStore';
import { createSSEHandlers } from './sseHandlers';

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
  const reconnectAttemptsRef = useRef(0);

  const store = useGameStore;

  const connect = useCallback(() => {
    if (!sessionId) return;

    // 关闭旧连接
    if (eventSourceRef.current) {
      eventSourceRef.current.close();
    }

    const username = useGameStore.getState().status.username || 'default';
    const url = `/api/game/${sessionId}/stream?last_event_seq=${lastSeqRef.current}&username=${encodeURIComponent(username)}`;
    const es = new EventSource(url);
    eventSourceRef.current = es;

    // 连接成功
    es.onopen = () => {
      reconnectAttemptsRef.current = 0;
      console.log(`[SSE] 已连接到会话 ${sessionId}`);
    };

    /** 拉取本会话的耗时/token 统计；失败不影响游戏流程。 */
    const refreshMetrics = () => {
      const sid = store.getState().sessionId;
      const name = store.getState().status.username || 'default';
      if (!sid) return;
      fetch(`/api/game/${sid}/metrics?username=${encodeURIComponent(name)}`)
        .then((r) => (r.ok ? r.json() : null))
        .then((metrics) => {
          if (metrics) store.getState().setMetrics(metrics);
        })
        .catch(() => { /* 统计不可用不影响游戏 */ });
    };

    // 定义事件处理器
    const handlers = createSSEHandlers({ store, refreshMetrics });

    // 监听所有标准事件类型
    const eventTypes = [
      'intro', 'narrative', 'narrative_flush', 'dice_roll',
      'state_update', 'choices', 'game_event', 'error', 'end_of_turn',
      'metrics_update',
      'journal_update', 'scene_update', 'maps_updated', 'bestiary_updated', 'spells_updated', 'history',
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
      es.close();
      if (reconnectTimeoutRef.current) {
        clearTimeout(reconnectTimeoutRef.current);
      }
      // P1-17: 指数退避 + 最大尝试次数，避免后端重启后无限重试。
      const attempt = reconnectAttemptsRef.current;
      if (attempt >= 8) {
        console.error('[SSE] 重连尝试超过 8 次，已停止自动重连；请刷新页面或检查后端。');
        return;
      }
      reconnectAttemptsRef.current = attempt + 1;
      const delay = Math.min(30000, 1000 * Math.pow(1.6, attempt));
      console.warn(`[SSE] 连接断开，第 ${attempt + 1} 次重连将在 ${Math.round(delay / 1000)} 秒后开始...`);
      reconnectTimeoutRef.current = setTimeout(() => {
        connect();
      }, delay);
    };
  }, [sessionId]);

  useEffect(() => {
    connect();

    // 读档或漏掉 feat_available 事件时，也要能弹出升级选择
    const name = useGameStore.getState().status.username
      || (typeof localStorage !== 'undefined' ? localStorage.getItem('dnd_auth_user') : '')
      || 'default';
    if (sessionId) {
      fetch(`/api/game/${sessionId}/levelup?username=${encodeURIComponent(name)}`)
        .then((r) => (r.ok ? r.json() : null))
        .then((data) => {
          if (data && typeof data.pending_level === 'number') {
            useGameStore.getState().setPendingLevelUp(data.pending_level);
          }
        })
        .catch(() => { /* 检查失败不影响游戏 */ });
    }

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
