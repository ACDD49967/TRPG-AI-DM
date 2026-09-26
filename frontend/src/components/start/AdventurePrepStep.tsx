import { useStartWizard } from './StartWizardContext';
/**
 * 步骤 3「冒险准备」：额外剧本文本 + 角色速览卡 + 冒险规则提示。
 *
 * 从 StartScreen 拆出：这里原本是内联 JSX（约 66 行），并且从组件作用域直接读
 * 十来个派生值。拆成组件后 props 写成显式类型，派生值仍由 StartScreen 计算传入
 * （规则计算属于 gameSystems，不在这里重复实现）。
 */
import { GAME_SYSTEM_LABELS, getDnd4Derived, getDnd5Derived, type GameSystem } from '../../gameSystems';

interface Props {
  scenarioText: string;
  setScenarioText: (value: string) => void;
  characterImage: string;
  charName: string;
  occupation: string;
  rc: { name: string };
  cc: { name: string };
  gameSystem: GameSystem;
  playMode: 'lite' | 'deep';
  finalAttrs: Record<string, number>;
  cocAttrs: Record<string, number>;
  cocLuck: number;
  cocSkillPicks: string[];
  skillPicks: string[];
  d5Derived: ReturnType<typeof getDnd5Derived>;
  d4Derived: ReturnType<typeof getDnd4Derived>;
  error: string;
}

export default function AdventurePrepStep() {
  const props = useStartWizard() as unknown as Props;
  const {
  scenarioText, setScenarioText, characterImage, charName, occupation, rc, cc,
  gameSystem, playMode, finalAttrs, cocAttrs, cocLuck, cocSkillPicks, skillPicks,
  d5Derived, d4Derived, error,
} = props;
  return (
    <div className="space-y-5">
      <h2 className="text-lg font-bold text-ink-900">冒险准备</h2>

      <div>
        <label className="block text-xs font-medium text-ink-600 mb-1">额外剧本</label>
        <textarea value={scenarioText} onChange={e => setScenarioText(e.target.value)} placeholder="粘贴自定义剧本..." rows={4} className="input-field resize-none" />
      </div>

      <div className="bg-white rounded-xl border border-gray-200 overflow-hidden">
        <div className="flex">
          <div className="w-24 h-28 bg-gray-100 flex items-center justify-center shrink-0">
            {characterImage ? <img src={characterImage} alt="角色" className="w-full h-full object-cover" /> : <span className="text-[9px] text-ink-400">暂无头像</span>}
          </div>
          <div className="flex-1 p-3">
            <p className="text-sm font-bold text-ink-900">{charName || '???'}</p>
            <p className="text-[10px] text-ink-500">{gameSystem === 'coc' ? `${occupation}（调查员）` : gameSystem === 'custom' ? '自定义角色' : `${rc.name} ${cc.name} Lv.1`} · {GAME_SYSTEM_LABELS[gameSystem]}</p>
            <div className="grid grid-cols-2 gap-x-3 gap-y-1 mt-2">
              {gameSystem === 'coc' ? (
                <>
                  <span className="text-[10px] text-ink-500">HP <b className="text-ink-800">{Math.max(1, Math.floor(((cocAttrs.con || 50) + (cocAttrs.siz || 50)) / 10))}</b></span>
                  <span className="text-[10px] text-ink-500">MP <b className="text-ink-800">{Math.max(1, Math.floor((cocAttrs.pow || 50) / 5))}</b></span>
                  <span className="text-[10px] text-ink-500">SAN <b className="text-ink-800">{cocAttrs.pow || 50}</b></span>
                  <span className="text-[10px] text-ink-500">幸运 <b className="text-ink-800">{cocLuck}</b></span>
                </>
              ) : (
                <>
                  <span className="text-[10px] text-ink-500">HP <b className="text-ink-800">{gameSystem === 'dnd4e' ? d4Derived.hp : gameSystem === 'dnd5e' ? d5Derived.hp : 30}</b></span>
                  <span className="text-[10px] text-ink-500">AC <b className="text-ink-800">12</b></span>
                  {gameSystem === 'dnd4e' && <span className="text-[10px] text-ink-500">回复力 <b className="text-ink-800">{d4Derived.healingSurges}</b></span>}
                  <span className="text-[10px] text-ink-500">{playMode === 'lite' ? '精简模式' : '深度模式'}</span>
                </>
              )}
            </div>
            {gameSystem === 'coc' && cocSkillPicks.length > 0 && <p className="text-[10px] text-ink-500 mt-1">技能: {cocSkillPicks.join('、')}</p>}
            {gameSystem !== 'coc' && skillPicks.length > 0 && <p className="text-[10px] text-ink-500 mt-1">技能: {skillPicks.join('、')}</p>}
          </div>
        </div>
        <div className="border-t border-gray-200 p-3 grid grid-cols-3 gap-1.5 bg-gray-50/60">
          {Object.entries(gameSystem === 'coc' ? cocAttrs : finalAttrs).map(([k, v]) => (
            <div key={k} className="bg-white rounded border border-gray-200 px-2 py-1 flex items-center justify-between">
              <span className="text-[9px] text-ink-400 uppercase">{k}</span>
              <span className="text-[11px] font-bold text-ink-800">{v}</span>
            </div>
          ))}
        </div>
      </div>

      <div className="bg-amber-50 border border-amber-200 rounded-lg p-3">
        <p className="text-[10px] text-amber-800 font-medium mb-1">冒险规则</p>
        <ul className="text-[10px] text-amber-700 space-y-0.5">
          {gameSystem === 'dnd5e' && <li>· D&D 5e核心规则，检定失败有真实后果</li>}
          {gameSystem === 'dnd4e' && <li>· D&D 4e威能与防御规则，回复力决定续航</li>}
          {gameSystem === 'coc' && <li>· COC 7e：调查员会受伤、失去理智，直面未知</li>}
          {gameSystem === 'custom' && <li>· 自定义规则：按你提供的规则文本主持</li>}
          <li>· 背包中没有的物品无法使用</li>
          <li>· 角色可能受伤甚至死亡——冒险有代价</li>
          {gameSystem === 'dnd5e' && <li>· 每2级可选择一项特长</li>}
        </ul>
      </div>

      {error && <p className="text-red-700 text-xs">{error}</p>}
    </div>
  );
}
