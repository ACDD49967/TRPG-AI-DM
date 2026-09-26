/** 世界生成进度与错误提示（从 ScenarioStep 拆出；值经 useStartWizard 取用）。 */
import { useStartWizard } from '../StartWizardContext';
import { WORLD_STAGES } from '../../../data/dndData';

export default function ScenarioWorldProgress() {
  const { worldGenBusy, worldGenStage, worldGenDetail, worldGenLive, worldGenErr,
  } = useStartWizard();

  return (
    <>
      {worldGenBusy&&(
        <div className="bg-gray-50 rounded-lg p-4 border border-gray-200 space-y-2">
          <div className="flex items-center gap-2 text-sm font-medium text-ink-700"><span className="animate-pulse">●</span>铸造世界中</div>
          <div className="h-1.5 bg-gray-200 rounded-full overflow-hidden"><div className="h-full bg-gradient-to-r from-indigo-500 to-purple-500 rounded-full transition-all duration-1000" style={{width:`${((worldGenStage+1)/WORLD_STAGES.length)*100}%`}}/></div>
          {worldGenDetail&&<p className="text-xs text-indigo-600 animate-pulse">{worldGenDetail}</p>}
          {worldGenLive && <pre className="text-[9px] text-ink-500 bg-white rounded p-2 mt-1 max-h-40 overflow-y-auto whitespace-pre-wrap">{worldGenLive}</pre>}
          <div className="space-y-0.5">
            {WORLD_STAGES.map((st: any, i: any) =>(<div key={st.key} className={`flex items-center gap-2 text-xs ${i<worldGenStage?'text-emerald-600':i===worldGenStage?'text-indigo-600 font-medium':'text-ink-400'}`}><span>{i<worldGenStage?'✓':i===worldGenStage?'◉':'○'}</span><span>{st.label}</span>{i===worldGenStage&&<span className="text-ink-400 font-normal">— {st.desc}</span>}</div>))}
          </div>
        </div>
      )}

      {worldGenErr&&<p className="text-red-700 text-xs">{worldGenErr}</p>}
    </>
  );
}
