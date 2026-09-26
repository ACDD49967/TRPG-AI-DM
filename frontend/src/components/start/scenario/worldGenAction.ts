/** 世界生成长动作：流式生成大纲、进度、完成后的基线保存与知识库刷新。 */
import { WORLD_STAGES } from '../../../data/dndData';
import type { GameSystem } from '../../../gameSystems';
import { readEventStream, refreshScenarioList } from '../scenarioStream';

export interface WorldGenContext {
  username: string;
  apiKey: string;
  modelName: string;
  baseUrl: string;
  gameSystem: string;
  charName: string;
  raceName: string;
  className: string;
  thinkingStrength: string;
  worldDesc: string;
  worldTone: string;
  customRules: string;
  customClasses: string[];
  customSkills: string[];
  extraAttributes: Record<string, string>;
  setBusy: (v: boolean) => void;
  setError: (v: string) => void;
  setStage: (v: number) => void;
  setDetail: (v: string) => void;
  setLive: (updater: (prev: string) => string) => void;
  setOutline: (v: string) => void;
  setScore: (v: number | null) => void;
  setWorldStateJson: (v: string) => void;
  setSummary: (v: string) => void;
  setScenarioSystem: (v: GameSystem) => void;
  setSourceChunks: (v: string[]) => void;
  setScenarioId: (v: string) => void;
  setSelectedScenario: (v: string) => void;
  setShowScenarioList: (v: boolean) => void;
  setSavedScenarios: (v: Array<Record<string, unknown>>) => void;
  updateScenario: (overrides: Record<string, unknown>, sid: string) => void;
  loadKb: () => void;
}

export async function generateWorld(ctx: WorldGenContext): Promise<void> {
  ctx.setBusy(true);
  ctx.setError('');
  ctx.setStage(0);
  ctx.setLive(() => '');
  try {
    const r = await fetch('/api/generate/world/stream', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        description: ctx.worldDesc || '一个' + ctx.worldTone + '的冒险',
        username: ctx.username || 'default',
        character_name: ctx.charName || '冒险者',
        race: ctx.raceName,
        char_class: ctx.className,
        tone: ctx.worldTone,
        game_system: ctx.gameSystem,
        custom_rules: ctx.customRules || undefined,
        custom_classes: ctx.customClasses,
        custom_skills: ctx.customSkills,
        extra_attributes: ctx.extraAttributes,
        api_key: ctx.apiKey || undefined,
        model_name: ctx.modelName || undefined,
        base_url: ctx.baseUrl || undefined,
        thinking_strength: ctx.thinkingStrength,
      }),
    });
    if (!r.ok) {
      const e = await r.json().catch(() => ({}));
      throw new Error(e.detail || '生成失败');
    }
    await readEventStream(r, (data) => {
      if (data.type === 'gen_token') {
        ctx.setLive((prev) => prev + String(data.token));
      } else if (data.type === 'progress') {
        const idx = Math.min(WORLD_STAGES.length - 1,
          Math.floor((Number(data.percent) / 100) * WORLD_STAGES.length));
        ctx.setStage(idx);
        ctx.setDetail(String(data.detail || data.label || ''));
      } else if (data.type === 'complete') {
        ctx.setOutline(String(data.content));
        ctx.setScore(typeof data.score === 'number' ? data.score : null);
        if (data.scenario_id) {
          ctx.setScenarioId(String(data.scenario_id));
          ctx.setSelectedScenario(String(data.scenario_id));
          ctx.setShowScenarioList(false);
        }
        if (data.world_state_json) ctx.setWorldStateJson(String(data.world_state_json));
        if (data.summary) ctx.setSummary(String(data.summary));
        if (data.system) ctx.setScenarioSystem(data.system as GameSystem);
        if (data.source_chunks) ctx.setSourceChunks(data.source_chunks as string[]);
        // 生成完成即自动保存一次（确保后续编辑前的基线已落库）
        if (data.scenario_id) {
          ctx.updateScenario({
            world_outline: data.content,
            summary: data.summary || '',
            custom_rules: ctx.customRules,
            custom_classes: ctx.customClasses,
            custom_skills: ctx.customSkills,
            extra_attributes: ctx.extraAttributes,
          }, String(data.scenario_id));
        }
        ctx.setStage(WORLD_STAGES.length - 1);
        ctx.setDetail('');
      } else if (data.type === 'error') {
        throw new Error(String(data.msg || '生成失败'));
      }
    });
    ctx.setSavedScenarios(await refreshScenarioList(ctx.username) as Array<Record<string, unknown>>);
    ctx.loadKb();
  } catch (e: unknown) {
    ctx.setError(e instanceof Error ? e.message : '生成失败');
  } finally {
    ctx.setBusy(false);
  }
}
