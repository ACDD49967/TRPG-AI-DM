/** 生成剧本的规则系统选择与自定义规则（从 ScenarioStep 拆出；值经 useStartWizard 取用）。 */
import { useStartWizard } from '../StartWizardContext';
import { GAME_SYSTEM_OPTIONS } from '../../../gameSystems';

export default function ScenarioRuleSystem() {
  const { scenarioMode, setGameSystem, gameSystem, customRules, setCustomRules,
  } = useStartWizard();

  return (
    <>
      {scenarioMode==='generate'&&(
        <div className="bg-indigo-50/40 rounded-lg p-3 border border-indigo-100 space-y-2">
          <label className="block text-xs font-medium text-ink-700 mb-1">剧本规则系统（角色系统自动跟随）</label>
          <div className="grid grid-cols-2 gap-1.5">
            {GAME_SYSTEM_OPTIONS.map((opt: any) =>(
              <button key={opt.id} onClick={()=>setGameSystem(opt.id)} className={`p-2 rounded-lg border text-left text-xs transition-all ${
                gameSystem===opt.id?'border-indigo-400 bg-indigo-100 text-indigo-800':'border-gray-200 bg-white text-ink-600 hover:border-gray-300'
              }`}>
                <span className="font-bold">{opt.label}</span>
                <span className="block text-[9px] opacity-70">{opt.short} · {opt.description}</span>
              </button>
            ))}
          </div>
          {gameSystem==='custom'&&(
            <div>
              <label className="block text-xs font-medium text-ink-600 mb-1">自定义规则</label>
              <textarea value={customRules} onChange={(e: any) =>setCustomRules(e.target.value)} placeholder="粘贴你的自定义规则，例如属性名称、判定方式、特殊机制..." rows={3} className="input-field resize-none" />
            </div>
          )}
          <p className="text-[10px] text-ink-400">生成时按此规则系统创建剧本；角色系统由剧本系统决定，角色卡库不绑定具体剧本。</p>
        </div>
      )}
    </>
  );
}
