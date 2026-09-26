/** 已有剧本列表：选择、展开与删除（从 ScenarioStep 拆出；值经 useStartWizard 取用）。 */
import { useStartWizard } from '../StartWizardContext';
import { GAME_SYSTEM_LABELS, type GameSystem } from '../../../gameSystems';

export default function ExistingScenarioPicker() {
  const { scenarioMode, savedScenarios, setShowScenarioList, showScenarioList, selectedScenario,
    gameSystem, loadScenario, deleteScenario,
  } = useStartWizard();

  return (
    <>
      {scenarioMode==='existing'&&savedScenarios.length>0&&(
        <div className="card p-3 bg-indigo-50/50 border-indigo-200">
          <div className="flex items-center justify-between mb-2">
            <span className="text-xs font-medium text-indigo-700">已有剧本可直接使用（跳过世界生成）</span>
            <button onClick={()=>setShowScenarioList(!showScenarioList)} className="text-[10px] text-indigo-500 hover:text-indigo-700">{showScenarioList?'收起':'展开'}({savedScenarios.filter((s: any) =>!s.system||s.system===gameSystem).length}个)</button>
          </div>
          {!showScenarioList&&selectedScenario&&(
            <p className="text-[10px] text-indigo-600">已选择: {savedScenarios.find((s: any) =>s.id===selectedScenario)?.title||''}</p>
          )}
          {showScenarioList&&(
            <div className="space-y-1 max-h-48 overflow-y-auto">
              {savedScenarios.filter((s: any) =>!s.system||s.system===gameSystem).map((s: any) =>(
                <div key={s.id} className={`rounded-lg border text-xs transition-all ${selectedScenario===s.id?'border-indigo-400 bg-indigo-100 ring-1 ring-indigo-300':'border-gray-200 bg-white hover:border-gray-300'}`}>
                  <button onClick={()=>loadScenario(s.id)} className="w-full text-left p-2.5">
                    <div className="flex justify-between items-center">
                      <span className="font-medium text-ink-800">{s.title}</span>
                      <span className={`text-[10px] px-1.5 py-0.5 rounded-full ${s.score>=80?'bg-emerald-100 text-emerald-700':'bg-amber-100 text-amber-700'}`}>{s.score}分</span>
                    </div>
                    <div className="flex gap-3 mt-1 text-[10px] text-ink-500"><span>{(GAME_SYSTEM_LABELS as Record<string, string>)[(s.system as GameSystem)||'dnd5e']||s.system}</span><span>{s.tone}</span><span>游玩{s.total_sessions}次</span>{s.character_name&&<span>角色:{s.character_name}</span>}</div>
                    {s.summary&&<p className="mt-1 text-[10px] text-ink-500 line-clamp-2">{s.summary}</p>}
                  </button>
                  <div className="flex gap-1 px-2 pb-2">
                    <button onClick={()=>loadScenario(s.id)} className="text-[10px] px-2 py-1 bg-indigo-50 text-indigo-700 rounded-lg border border-indigo-200 hover:bg-indigo-100">选择/编辑</button>
                    <button onClick={()=>deleteScenario(s.id)} className="text-[10px] px-2 py-1 bg-red-50 text-red-600 rounded-lg border border-red-200 hover:bg-red-100">删除</button>
                  </div>
                </div>
              ))}
            </div>
          )}
          {selectedScenario&&(
            <p className="mt-2 text-[10px] text-indigo-600 font-medium">已选择已有剧本——点击“继续”即可跳过世界生成</p>
          )}
        </div>
      )}
    </>
  );
}
