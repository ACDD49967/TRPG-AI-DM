/** 剧本模式切换（已有 / 切分 / AI 生成）（从 ScenarioStep 拆出；值经 useStartWizard 取用）。 */
import { useStartWizard } from '../StartWizardContext';

export default function ScenarioModeTabs() {
  const { setScenarioMode, scenarioMode,
  } = useStartWizard();

  return (
    <>
      <div className="grid grid-cols-3 gap-2">
        {([
          {id:'existing', label:'已有剧本', desc:'直接使用已保存剧本'},
          {id:'split', label:'本体切分', desc:'上传剧本文件后切分生成'},
          {id:'generate', label:'AI 自动生成', desc:'从描述生成全新剧本'},
        ] as const).map((mode: any) =>(
          <button key={mode.id} onClick={()=>setScenarioMode(mode.id)} className={`p-2.5 rounded-xl border text-left transition-all ${scenarioMode===mode.id?'border-indigo-400 bg-indigo-50 ring-1 ring-indigo-200':'border-gray-200 bg-white hover:border-gray-300'}`}>
            <div className="text-xs font-bold text-ink-800">{mode.label}</div>
            <div className="text-[9px] text-ink-500 mt-0.5">{mode.desc}</div>
          </button>
        ))}
      </div>
    </>
  );
}
