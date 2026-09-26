/** 升级弹窗数据层：待分配等级、专长/属性目录与两种写回接口。 */
import { useEffect, useState } from 'react';
import { useGameStore } from '../../store/gameStore';
import { useToastStore } from '../../store/toastStore';

export type Ability = { key: string; name: string };
export type FeatInfo = { id: string; name: string; desc: string };
export type LevelUpMode = 'asi2' | 'asi1' | 'feat';

export function useLevelUp() {
  const pendingLevel = useGameStore((s) => s.pendingLevelUp);
  const setPendingLevelUp = useGameStore((s) => s.setPendingLevelUp);
  const sessionId = useGameStore((s) => s.sessionId);
  const storeUsername = useGameStore((s) => s.status.username);
  const username = storeUsername
    || (typeof localStorage !== 'undefined' ? localStorage.getItem('dnd_auth_user') : '')
    || 'default';
  const [mode, setMode] = useState<LevelUpMode>('asi2');
  const [picked, setPicked] = useState<string[]>([]);
  const [feats, setFeats] = useState<FeatInfo[]>([]);
  const [abilities, setAbilities] = useState<Ability[]>([]);
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    if (!pendingLevel || !sessionId) return;
    setPicked([]);
    fetch(`/api/game/${sessionId}/levelup?username=${encodeURIComponent(username)}`)
      .then((r) => (r.ok ? r.json() : null))
      .then((data) => {
        if (!data) return;
        setFeats(data.feats || []);
        setAbilities((data.abilities || []).map((a: Ability) => ({ key: a.key, name: a.name })));
      })
      .catch(() => { /* 拉取失败保持弹窗，玩家可重试 */ });
  }, [pendingLevel, sessionId, username]);

  const pickAbility = (key: string) => {
    if (mode === 'asi2') {
      setPicked([key]);
      return;
    }
    setPicked((prev) => (
      prev.includes(key) ? prev.filter((k) => k !== key) : [...prev, key].slice(-2)
    ));
  };

  const canConfirm = mode === 'asi2' ? picked.length === 1 : picked.length === 2;

  const confirmAsi = async () => {
    if (!sessionId || !canConfirm) return;
    setBusy(true);
    try {
      const body = mode === 'asi2'
        ? { kind: 'asi', ability: picked[0] }
        : { kind: 'asi', ability: picked[0], ability2: picked[1] };
      const res = await fetch(
        `/api/game/${sessionId}/levelup?username=${encodeURIComponent(username)}`,
        { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(body) },
      );
      if (!res.ok) {
        const err = await res.json().catch(() => ({}));
        throw new Error(err.detail || '分配失败');
      }
      const data = await res.json();
      useGameStore.getState().updateStatus({ attributes: data.current.attributes });
      useToastStore.getState().showToast('属性提升已记入角色卡。', 'success');
      setPendingLevelUp(null);
    } catch (e) {
      useToastStore.getState().showToast(String((e as Error).message || e), 'error');
    } finally {
      setBusy(false);
    }
  };

  const confirmFeat = async (featId: string) => {
    if (!sessionId) return;
    setBusy(true);
    try {
      const res = await fetch(
        `/api/game/${sessionId}/levelup?username=${encodeURIComponent(username)}`,
        { method: 'POST', headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ kind: 'feat', feat_id: featId }) },
      );
      if (!res.ok) {
        const err = await res.json().catch(() => ({}));
        throw new Error(err.detail || '选择失败');
      }
      const data = await res.json();
      useGameStore.getState().updateStatus({
        feats: (data.current.feats || []).map((n: string) => ({ name: n })),
      });
      useToastStore.getState().showToast(
        `专长「${feats.find((f) => f.id === featId)?.name || ''}」已记入角色卡。`, 'success');
      setPendingLevelUp(null);
    } catch (e) {
      useToastStore.getState().showToast(String((e as Error).message || e), 'error');
    } finally {
      setBusy(false);
    }
  };

  return {
    pendingLevel, sessionId, mode, setMode, picked, setPicked, pickAbility, canConfirm,
    feats, abilities, busy, confirmAsi, confirmFeat,
    close: () => setPendingLevelUp(null),
  };
}
