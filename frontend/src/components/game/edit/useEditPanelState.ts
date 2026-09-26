/** 编辑面板数据层：世界/角色/会话设置的读取、写回、删除与本地草稿。 */
import { useCallback, useEffect, useState } from 'react';
import { useGameStore } from '../../../store/gameStore';
import type {
  CharacterState, SceneRow, SessionSettings, Tab, WorldState,
} from './types';

export function useEditPanelState({
  sessionId, username, onClose, onChanged,
}: {
  sessionId: string;
  username: string;
  onClose: () => void;
  onChanged?: () => void;
}) {
  const [tab, setTab] = useState<Tab>('scene');
  const [world, setWorld] = useState<WorldState | null>(null);
  const [character, setCharacter] = useState<CharacterState | null>(null);
  const [settings, setSettings] = useState<SessionSettings>({});
  const [apiKeyDraft, setApiKeyDraft] = useState('');
  const [busy, setBusy] = useState(false);
  const [message, setMessage] = useState('');
  const [error, setError] = useState('');

  const api = useCallback(async (path: string, init?: RequestInit) => {
    const joiner = path.includes('?') ? '&' : '?';
    const url = `${path}${joiner}username=${encodeURIComponent(username || 'default')}`;
    return fetch(url, init);
  }, [username]);

  const load = useCallback(async (allowRetry = true) => {
    try {
      const [w, c, s] = await Promise.all([
        api(`/api/game/${sessionId}/world`),
        api(`/api/game/${sessionId}/state`),
        api(`/api/game/${sessionId}/settings`),
      ]);
      if (w.ok) setWorld(await w.json());
      if (c.ok) setCharacter(await c.json());
      if (s.ok) setSettings(await s.json());
      setError('');
      // 刚读档时服务端会话可能还没注册完，三个请求会一起失败；
      // 这里短暂等待后重试一次，否则面板会停在空设置上，点保存只会提示"没有需要修改的字段"。
      if (allowRetry && !(w.ok && c.ok && s.ok)) {
        window.setTimeout(() => { void load(false); }, 800);
      }
    } catch (e) {
      setError(e instanceof Error ? e.message : '读取失败');
      if (allowRetry) window.setTimeout(() => { void load(false); }, 800);
    }
  }, [api, sessionId]);

  useEffect(() => { load(); }, [load]);

  const sendWorld = useCallback(async (
    action: string, target: string, changes: Record<string, any>,
  ) => {
    setBusy(true); setMessage('');
    try {
      const response = await api(`/api/game/${sessionId}/world`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ action, target, changes, reason: '玩家在编辑面板修改' }),
      });
      const body = await response.json();
      if (!response.ok) throw new Error(body?.detail || '修改失败');
      setMessage(String(body.result || '已保存'));
      if (body.world) setWorld(body.world);
      onChanged?.();
    } catch (e) {
      setError(e instanceof Error ? e.message : '修改失败');
    } finally {
      setBusy(false);
    }
  }, [api, onChanged, sessionId]);

  const sendState = useCallback(async (changes: Record<string, any>) => {
    setBusy(true); setMessage('');
    try {
      const response = await api(`/api/game/${sessionId}/state`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ changes, reason: '玩家在编辑面板修改' }),
      });
      const body = await response.json();
      if (!response.ok) throw new Error(body?.detail || '修改失败');
      setMessage(String(body.result || '已保存'));
      if (body.state) setCharacter(body.state);
      onChanged?.();
    } catch (e) {
      setError(e instanceof Error ? e.message : '修改失败');
    } finally {
      setBusy(false);
    }
  }, [api, onChanged, sessionId]);

  const saveSettings = useCallback(async () => {
    setBusy(true); setMessage('');
    try {
      const payload: Record<string, string> = {};
      if (settings.model_name) payload.model_name = settings.model_name;
      if (settings.base_url) payload.base_url = settings.base_url;
      if (settings.play_mode) payload.play_mode = settings.play_mode;
      if (settings.thinking_strength) payload.thinking_strength = settings.thinking_strength;
      if (apiKeyDraft.trim()) payload.api_key = apiKeyDraft.trim();
      if (Object.keys(payload).length === 0) {
        setMessage('没有需要修改的字段');
        return;
      }
      const response = await api(`/api/game/${sessionId}/settings`, {
        method: 'PATCH',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload),
      });
      const body = await response.json();
      if (!response.ok) throw new Error(body?.detail || '保存失败');
      setSettings(body.settings || settings);
      setApiKeyDraft('');
      setMessage('会话设置已更新');
    } catch (e) {
      setError(e instanceof Error ? e.message : '保存失败');
    } finally {
      setBusy(false);
    }
  }, [api, apiKeyDraft, sessionId, settings]);

  const editScene = useCallback((key: keyof SceneRow, value: string) => {
    setWorld((prev) => (prev ? { ...prev, scene: { ...prev.scene, [key]: value } } : prev));
  }, []);

  const mergeSettings = useCallback((patch: Partial<SessionSettings>) => {
    setSettings((prev) => ({ ...prev, ...patch }));
  }, []);

  const deleteSession = useCallback(async () => {
    if (!window.confirm('确定删除本局会话？已保存的存档与角色卡不受影响。')) return;
    setBusy(true); setMessage(''); setError('');
    try {
      const response = await api(`/api/game/${sessionId}`, { method: 'DELETE' });
      const body = await response.json().catch(() => ({}));
      if (!response.ok) throw new Error(body?.detail || '删除失败');
      // 会话已消失：回到大厅，避免停留在指向死会话的游戏界面
      useGameStore.getState().goToStart();
      onClose();
      onChanged?.();
    } catch (e) {
      setError(e instanceof Error ? e.message : '删除失败');
    } finally {
      setBusy(false);
    }
  }, [api, onChanged, onClose, sessionId]);

  return {
    tab, setTab, world, character, settings, apiKeyDraft, setApiKeyDraft,
    busy, message, error, load, sendWorld, sendState, saveSettings,
    editScene, mergeSettings, deleteSession,
  };
}
