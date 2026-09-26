/** 内容库写入：新增生物（含图片与结构化数值）。 */
import { useGameStore } from '../../../store/gameStore';
import type { UseMediaActionsDeps } from '../useMediaLibraryActions';

export function createBeastWriteAction(deps: UseMediaActionsDeps) {
  const { dmBeast, dmBeastImage, gameSystem, scenarioId, username, setDmBeast, setDmBeastImage } = deps;

  return async () => {
    if (!dmBeast.name.trim()) return;
    try {
      const sys = gameSystem || 'custom';
      const sid = scenarioId || '';
      const stats: Record<string, string> = {};
      const num = (v: string) => v.trim();
      if (dmBeast.ac) stats['AC'] = num(dmBeast.ac);
      if (dmBeast.hp) stats['HP'] = num(dmBeast.hp);
      if (dmBeast.speed) stats['速度'] = num(dmBeast.speed);
      if (dmBeast.str) stats['力量'] = num(dmBeast.str);
      if (dmBeast.dex) stats['敏捷'] = num(dmBeast.dex);
      if (dmBeast.con) stats['体质'] = num(dmBeast.con);
      if (dmBeast.int) stats['智力'] = num(dmBeast.int);
      if (dmBeast.wis) stats['感知'] = num(dmBeast.wis);
      if (dmBeast.cha) stats['魅力'] = num(dmBeast.cha);
      if (dmBeast.skills) stats['技能'] = dmBeast.skills.trim();
      if (dmBeast.traits) stats['特性'] = dmBeast.traits.trim();
      if (dmBeast.actions) stats['动作'] = dmBeast.actions.trim();
      const details = {
        habits: dmBeast.habits.trim() || undefined,
        habitat: dmBeast.habitat.trim() || undefined,
        lore: dmBeast.lore.trim() || undefined,
        weakness: dmBeast.weakness.trim() || undefined,
      };
      const tags = dmBeast.tags.split(/[,，]/).map(s => s.trim()).filter(Boolean);
      const payload = {
        username, name: dmBeast.name.trim(), description: dmBeast.description,
        system: sys, stats, tags, details, scenario_id: sid,
      };
      if (dmBeastImage) {
        const fd = new FormData();
        fd.append('file', dmBeastImage);
        fd.append('username', username);
        fd.append('name', dmBeast.name.trim());
        fd.append('description', dmBeast.description);
        fd.append('system', sys);
        fd.append('stats', JSON.stringify(stats));
        fd.append('tags', tags.join(','));
        fd.append('scenario_id', sid);
        await fetch('/api/bestiary/upload', { method: 'POST', body: fd });
        await fetch('/api/bestiary', {
          method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(payload),
        });
      } else {
        await fetch('/api/bestiary', {
          method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(payload),
        });
      }
      setDmBeast({
        name: '', description: '', ac: '', hp: '', speed: '', str: '', dex: '', con: '',
        int: '', wis: '', cha: '', skills: '', traits: '', actions: '', habits: '',
        habitat: '', lore: '', weakness: '', tags: '',
      });
      setDmBeastImage(null);
      useGameStore.getState().bumpMediaVersion();
    } catch { /* 新增失败保持表单 */ }
  };
}
