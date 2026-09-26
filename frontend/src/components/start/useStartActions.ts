/** 向导的两个页面级动作：AI 生成角色/背景、开始冒险（组装 payload 并建局）。
 *
 * 从 StartScreen 拆出：这两段是"组装请求 + 建会话"的纯流程代码，
 * 外移后 StartScreen 只留状态与渲染，动作本身也能单独被浏览器脚本盯住。
 */
import { useGameStore } from '../../store/gameStore';
import type { GameSystem } from '../../gameSystems';

export interface UseStartActionsDeps {
  apiKey: string;
  attrs: any;
  aiGen: any;
  backstoryText: string;
  baseUrl: string;
  cc: any;
  charName: string;
  characterImage: string;
  cocAttrs: any;
  cocLuck: any;
  cocSkillPicks: any;
  cocSkillValues: any;
  customClasses: any;
  customRules: string;
  customSkills: any;
  extraAttributes: any;
  finalAttrs: any;
  gameSystem: GameSystem;
  gender: string;
  modelName: string;
  occupation: string;
  playMode: 'lite' | 'deep';
  rc: any;
  scenarioId: string;
  scenarioSummary: string;
  scenarioText: string;
  referenceScript: string;
  skillPicks: any;
  spellPicks: any;
  thinkingStrength: string;
  username: string;
  worldOutline: string;
  worldStateJson: string;
  activeExtIds: string[];
  updateScenario: () => Promise<any>;
  setAiBusy: (v: boolean) => void;
  setAiErr: (v: string) => void;
  setAiGen: (v: any) => void;
  setError: (v: string) => void;
  setLoading: (v: boolean) => void;
}

export function useStartActions(deps: UseStartActionsDeps) {
  const {
    apiKey, attrs, aiGen, backstoryText, baseUrl, cc, charName, characterImage,
    cocAttrs, cocLuck, cocSkillPicks, cocSkillValues, customClasses, customRules,
    customSkills, extraAttributes, finalAttrs, gameSystem, gender, modelName,
    occupation, playMode, rc, scenarioId, scenarioSummary, scenarioText,
    referenceScript, skillPicks, spellPicks, thinkingStrength, username,
    worldOutline, worldStateJson, activeExtIds, updateScenario,
    setAiBusy, setAiErr, setAiGen, setError, setLoading,
  } = deps;
  const setSession = useGameStore((s) => s.setSession);
  const updateStatus = useGameStore((s) => s.updateStatus);

  const callAI = async (backstoryOnly: boolean) => {
    setAiBusy(true); setAiErr('');
    try {
      const isCoc = gameSystem === 'coc';
      const body: Record<string, unknown> = {
        character_name: charName || '冒险者',
        gender,
        race: isCoc ? '调查员' : rc.name,
        char_class: isCoc ? occupation : cc.name,
        game_system: gameSystem,
        scenario_summary: scenarioSummary || undefined,
        custom_rules: gameSystem === 'custom' ? customRules : undefined,
        api_key: apiKey || undefined,
        model_name: modelName || undefined,
        base_url: baseUrl || undefined,
        thinking_strength: thinkingStrength,
      };
      if (backstoryOnly) body.attributes = isCoc ? cocAttrs : attrs;
      else if (backstoryText.trim()) body.backstory = backstoryText.trim();
      const r = await fetch('/api/generate/character', {
        method: 'POST', headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(body),
      });
      if (!r.ok) { const e = await r.json().catch(() => ({})); throw new Error(e.detail || '生成失败'); }
      const d = await r.json();
      if (backstoryOnly) {
        d.attributes = isCoc ? cocAttrs : attrs;
      }
      setAiGen(d);
      if (d.fallback) {
        setAiErr('LLM 调用失败，已使用降级默认值（请检查 API Key / 模型 / 网络）');
      } else {
        setAiErr('');
      }
    } catch (e: unknown) { setAiErr(e instanceof Error ? e.message : '生成失败'); }
    finally { setAiBusy(false); }
  };

  const start = async () => {
    if (!modelName.trim()) { setError('请先选择或填写模型名称'); return; }
    if (!charName.trim()) { setError('请输入角色名称'); return; }
    setLoading(true); setError('');
    try {
      // 开局前自动保存当前剧本编辑，避免丢失修改
      if (scenarioId) { await updateScenario(); }
      const isDnd = gameSystem === 'dnd5e' || gameSystem === 'dnd4e';
      const r = await fetch('/api/game/new', {
        method: 'POST', headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          username: username || '冒险者', character_name: charName,
          gender: gameSystem === 'coc' ? '未指定' : gender,
          race: gameSystem === 'coc' ? '调查员' : rc.name,
          char_class: gameSystem === 'coc' ? occupation : cc.name,
          attributes: finalAttrs,
          race_traits: isDnd ? rc.traits : undefined,
          class_proficiencies: isDnd ? cc.profs : undefined,
          api_key: apiKey || undefined, model_name: modelName || undefined,
          base_url: baseUrl || undefined,
          thinking_strength: thinkingStrength,
          backstory: aiGen?.backstory || undefined, world_context: scenarioText || undefined,
          world_outline: worldOutline || undefined, world_state_json: worldStateJson || undefined,
          reference_script: referenceScript || undefined, scenario_id: scenarioId || undefined,
          new_world: !scenarioId,
          skill_proficiencies: gameSystem === 'coc' ? cocSkillPicks : skillPicks,
          skills: gameSystem === 'coc' ? cocSkillValues : undefined,
          play_mode: playMode,
          game_system: gameSystem,
          custom_rules: gameSystem === 'custom' ? customRules : undefined,
          luck: gameSystem === 'coc' ? cocLuck : undefined,
          extension_ids: activeExtIds,
          character_image: characterImage || undefined,
          custom_classes: customClasses,
          custom_skills: customSkills,
          extra_attributes: extraAttributes,
          known_spells: gameSystem === 'dnd5e' ? spellPicks.map((s: any) => ({
            name: s.name, name_zh: s.name_zh, level: s.level, school: s.school,
            description: s.description, description_zh: s.description_zh,
            casting_time: s.casting_time, range: s.range, components: s.components,
            duration: s.duration, classes: s.classes, ritual: s.ritual, prepared: true,
          })) : [],
        }),
      });
      if (!r.ok) { const e = await r.json(); throw new Error(e.detail || '创建失败'); }
      const d = await r.json();
      if (d.status) updateStatus(d.status);
      setSession(d.session_id);
    } catch (e: unknown) { setError(e instanceof Error ? e.message : '未知错误'); setLoading(false); }
  };

  return { callAI, start };
}
