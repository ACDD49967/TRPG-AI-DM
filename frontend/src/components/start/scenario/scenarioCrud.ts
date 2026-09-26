/** 剧本 CRUD 动作：读取回填、删除与更新保存。 */
import type { GameSystem } from '../../../gameSystems';
import { refreshScenarioList } from '../scenarioStream';

export interface ScenarioCrudContext {
  [key: string]: any;
  setGameSystem: (v: GameSystem) => void;
}

export function createScenarioCrud(ctx: ScenarioCrudContext) {
  const loadScenario = async (sid: string) => {
    try {
      const r = await fetch(`/api/scenarios/${sid}?username=${encodeURIComponent(ctx.username || 'default')}`);
      if (!r.ok) return;
      const d = await r.json();
      ctx.setWorldOutline(d.world_outline);
      ctx.setWorldStateJson(d.world_state_json || '');
      ctx.setScenarioSummary(d.summary || d.meta?.summary || '');
      ctx.setSourceChunks(d.source_chunks || []);
      ctx.setCustomRules(d.custom_rules || d.meta?.custom_rules || '');
      ctx.setCustomClassesText((d.custom_classes || []).join(', '));
      ctx.setCustomSkillsText((d.custom_skills || []).join(', '));
      ctx.setExtraAttributesText(
        Object.entries(d.extra_attributes || {}).map(([k, v]) => `${k}:${v}`).join('\n'));
      if (d.meta?.system || d.system) {
        const sys = (d.meta?.system || d.system) as GameSystem;
        ctx.setScenarioSystem(sys);
        ctx.setGameSystem(sys);
      }
      ctx.setScenarioId(sid);
      ctx.setSelectedScenario(sid);
      ctx.setShowScenarioList(false);
      ctx.setWorldScore(d.meta?.score || null);
    } catch { /* 读取失败保持当前剧本 */ }
  };

  const deleteScenario = async (sid: string) => {
    if (!window.confirm('确定删除该剧本？此操作不可恢复。')) return;
    try {
      await fetch(`/api/scenarios/${sid}?username=${encodeURIComponent(ctx.username || 'default')}`,
        { method: 'DELETE' });
      ctx.setSavedScenarios(ctx.savedScenarios.filter((s: any) => s.id !== sid));
      if (ctx.selectedScenario === sid) {
        ctx.setSelectedScenario('');
        ctx.setScenarioId('');
      }
    } catch { /* 删除失败保持列表 */ }
  };

  const updateScenario = async (overrides?: Record<string, any>, sidArg?: string) => {
    const sid = sidArg || ctx.scenarioId;
    if (!sid) return;
    try {
      const r = await fetch(`/api/scenarios/${sid}?username=${encodeURIComponent(ctx.username || 'default')}`, {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          summary: overrides?.summary ?? ctx.scenarioSummary,
          world_outline: overrides?.world_outline ?? ctx.worldOutline,
          custom_rules: overrides?.custom_rules ?? ctx.customRules,
          custom_classes: overrides?.custom_classes ?? ctx.customClasses,
          custom_skills: overrides?.custom_skills ?? ctx.customSkills,
          extra_attributes: overrides?.extra_attributes ?? ctx.extraAttributes,
        }),
      });
      if (!r.ok) {
        const e = await r.json().catch(() => ({}));
        throw new Error(e.detail || '保存失败');
      }
      ctx.setSavedScenarios(await refreshScenarioList(ctx.username));
      ctx.setWorldGenErr('');
    } catch (e: unknown) {
      ctx.setWorldGenErr(e instanceof Error ? e.message : '保存失败');
    }
  };

  return { loadScenario, deleteScenario, updateScenario };
}
