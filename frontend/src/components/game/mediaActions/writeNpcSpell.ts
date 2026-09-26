/** 内容库写入：新增 NPC 与法术。 */
import { useGameStore } from '../../../store/gameStore';
import type { UseMediaActionsDeps } from '../useMediaLibraryActions';

export function createNpcSpellWriteActions(deps: UseMediaActionsDeps) {
  const {
    dmNpc, dmNpcImage, dmSpell, gameSystem, scenarioId, sessionId, username,
    setDmNpc, setDmNpcImage, setDmSpell,
  } = deps;

  const addDmNpc = async () => {
    if (!sessionId || !dmNpc.name.trim()) return;
    try {
      const r = await fetch(`/api/game/${sessionId}/npc?username=${encodeURIComponent(username || 'default')}`, {
        method: 'POST', headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(dmNpc),
      });
      if (!r.ok) return;
      if (dmNpcImage) {
        const fd = new FormData();
        fd.append('npc_name', dmNpc.name.trim());
        fd.append('file', dmNpcImage);
        fd.append('username', username || 'default');
        await fetch(`/api/game/${sessionId}/npc/image`, { method: 'POST', body: fd });
      }
      setDmNpc({ name: '', role: '', location: '', hp: 10, ac: 10, level: 1 });
      setDmNpcImage(null);
    } catch { /* 新增失败保持表单 */ }
  };

  const addDmSpell = async () => {
    if (!dmSpell.name.trim()) return;
    try {
      await fetch('/api/spells', {
        method: 'POST', headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          username, name: dmSpell.name, description: dmSpell.description,
          level: dmSpell.level, school: dmSpell.school, ritual: dmSpell.ritual,
          casting_time: dmSpell.casting_time, range: dmSpell.range,
          components: dmSpell.components, duration: dmSpell.duration,
          classes: dmSpell.classes.split(/[,，]/).map(s => s.trim()).filter(Boolean),
          system: gameSystem || 'custom', scenario_id: scenarioId || '',
        }),
      });
      setDmSpell({
        name: '', description: '', level: '0', school: '', ritual: false,
        casting_time: '', range: '', components: '', duration: '', classes: '',
      });
      useGameStore.getState().bumpMediaVersion();
    } catch { /* 新增失败保持表单 */ }
  };

  return { addDmNpc, addDmSpell };
}
