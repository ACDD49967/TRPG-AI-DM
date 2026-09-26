/** 内容库机翻：SRD 法术整表翻译与地图/图鉴批量翻译（从 useMediaLibraryActions 拆出）。 */
import { useGameStore } from '../../../store/gameStore';
import type { UseMediaActionsDeps } from '../useMediaLibraryActions';


export function createTranslateActions(deps: UseMediaActionsDeps) {
  const {
    bestiary,
    mediaTranslate,
    spells,
    srdTranslating,
    scopedMaps,
    scopedBestiary,
    sessionId,
    username,
    setMediaTranslate,
    setSrdProgress,
    setSrdTranslating,
  } = deps;

    const translateSrd = async () => {
      if (!sessionId || srdTranslating) return;
      const untranslated = spells.filter(s => (s.tags || []).includes('SRD') && !s.description_zh);
      if (untranslated.length === 0) {
        alert('没有需要翻译的 SRD 法术');
        return;
      }
      const ids = untranslated.map(s => s.id);
      const total = ids.length;
      setSrdTranslating(true);
      setSrdProgress({ done: 0, total });
      try {
        const batchSize = 15;
        for (let i = 0; i < ids.length; i += batchSize) {
          const batch = ids.slice(i, i + batchSize);
          const r = await fetch(`/api/game/${sessionId}/translate-srd?username=${encodeURIComponent(username || 'default')}`, {
            method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ spell_ids: batch }),
          });
          if (!r.ok) {
            const e = await r.json().catch(() => ({}));
            alert(e.detail || '翻译失败');
            break;
          }
          setSrdProgress({ done: Math.min(i + batchSize, total), total });
        }
        useGameStore.getState().bumpMediaVersion();
      } catch {
        alert('翻译请求失败');
      } finally {
        setSrdTranslating(false);
        setSrdProgress(null);
      }
    };

    const translateMedia = async (kind: 'locations' | 'bestiary') => {
      if (!sessionId || mediaTranslate) return;
      const source = kind === 'locations' ? scopedMaps : scopedBestiary;
      const untranslated = source.filter(s => !s.description_zh);
      if (untranslated.length === 0) {
        alert('没有需要翻译的条目');
        return;
      }
      const ids = untranslated.map(s => s.id);
      const total = ids.length;
      setMediaTranslate({ kind, done: 0, total });
      try {
        const batchSize = 15;
        for (let i = 0; i < ids.length; i += batchSize) {
          const r = await fetch(`/api/game/${sessionId}/translate-media?username=${encodeURIComponent(username || 'default')}`, {
            method: 'POST', headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ kind, item_ids: ids.slice(i, i + batchSize) }),
          });
          if (!r.ok) {
            const e = await r.json().catch(() => ({}));
            alert(e.detail || '翻译失败');
            break;
          }
          setMediaTranslate({ kind, done: Math.min(i + batchSize, total), total });
        }
        useGameStore.getState().bumpMediaVersion();
      } catch {
        alert('翻译请求失败');
      } finally {
        setMediaTranslate(null);
      }
    };

  return { translateSrd, translateMedia };
}
