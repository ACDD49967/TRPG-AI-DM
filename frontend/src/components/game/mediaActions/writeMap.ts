/** 内容库写入：新增地点/地图（含图片上传）。 */
import { useGameStore } from '../../../store/gameStore';
import type { UseMediaActionsDeps } from '../useMediaLibraryActions';

export function createMapWriteAction(deps: UseMediaActionsDeps) {
  const { dmMap, dmMapImage, gameSystem, scenarioId, username, setDmMap, setDmMapImage } = deps;

  return async () => {
    if (!dmMap.name.trim()) return;
    try {
      const sys = gameSystem || 'custom';
      const sid = scenarioId || '';
      const locations = dmMap.locationsText.split(/[,，\n]/).map(s => s.trim()).filter(Boolean)
        .map(name => ({ name, x: 0, y: 0 }));
      const details = {
        type: dmMap.type.trim() || undefined,
        status: dmMap.status.trim() || undefined,
        culture: dmMap.culture.trim() || undefined,
        districts: dmMap.districts.split(/[,，]/).map(s => s.trim()).filter(Boolean),
        notable_figures: dmMap.notable_figures.trim() || undefined,
        dangers: dmMap.dangers.trim() || undefined,
        secret: dmMap.secret.trim() || undefined,
      };
      const payload = {
        username, name: dmMap.name.trim(), description: dmMap.description,
        system: sys, scenario_id: sid, locations, details,
      };
      if (dmMapImage) {
        const fd = new FormData();
        fd.append('file', dmMapImage);
        fd.append('username', username);
        fd.append('name', dmMap.name.trim());
        fd.append('description', dmMap.description);
        fd.append('system', sys);
        fd.append('scenario_id', sid);
        await fetch('/api/maps/upload', { method: 'POST', body: fd });
        await fetch('/api/maps', {
          method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(payload),
        });
      } else {
        await fetch('/api/maps', {
          method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(payload),
        });
      }
      setDmMap({
        name: '', description: '', type: '', status: '', culture: '', districts: '',
        notable_figures: '', dangers: '', secret: '', locationsText: '',
      });
      setDmMapImage(null);
      useGameStore.getState().bumpMediaVersion();
    } catch { /* 新增失败保持表单 */ }
  };
}
