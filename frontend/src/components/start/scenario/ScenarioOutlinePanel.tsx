/** 世界大纲结果：评分、总结、编辑/展开与切分统计（从 ScenarioStep 拆出；值经 useStartWizard 取用）。 */
import { useStartWizard } from '../StartWizardContext';
import { GAME_SYSTEM_LABELS } from '../../../gameSystems';

export default function ScenarioOutlinePanel() {
  const { worldOutline, worldGenBusy, worldScore, scenarioSummary, scenarioSystem, gameSystem,
    customRules, scenarioId, setWorldOutline, updateScenario, sourceChunks, splitter,
  } = useStartWizard();

  return (
    <>
      {worldOutline&&!worldGenBusy&&(
        <div className="space-y-2">
          {worldScore!==null&&(
            <div className="flex items-center gap-3 bg-gray-50 rounded-lg p-2.5 border border-gray-200">
              <span className={`text-lg font-bold ${worldScore>=90?'text-emerald-600':worldScore>=75?'text-amber-700':'text-red-700'}`}>{worldScore}/100</span>
              <div className="flex-1 h-1.5 bg-gray-200 rounded-full overflow-hidden"><div className={`h-full rounded-full ${worldScore>=90?'bg-emerald-500':worldScore>=75?'bg-amber-500':'bg-red-500'}`} style={{width:`${worldScore}%`}}/></div>
            </div>
          )}
          {scenarioSummary&&(
            <div className="bg-emerald-50 border border-emerald-200 rounded-lg p-3">
              <p className="text-[10px] text-emerald-700 font-medium mb-1">剧本总结</p>
              <p className="text-xs text-ink-700 leading-relaxed">{scenarioSummary}</p>
            </div>
          )}
          <div className="flex flex-wrap gap-1">
            <span className="text-[10px] bg-indigo-100 text-indigo-700 px-2 py-0.5 rounded-full border border-indigo-200">剧本系统：{(GAME_SYSTEM_LABELS as Record<string, string>)[scenarioSystem]}</span>
            <span className="text-[10px] bg-emerald-100 text-emerald-700 px-2 py-0.5 rounded-full border border-emerald-200">角色系统：{(GAME_SYSTEM_LABELS as Record<string, string>)[gameSystem]}</span>
            {gameSystem==='custom'&&customRules&&<span className="text-[10px] bg-amber-100 text-amber-700 px-2 py-0.5 rounded-full border border-amber-200">自定义规则已填写</span>}
          </div>
          {scenarioId ? (
            <div className="space-y-2">
              <label className="text-[10px] text-ink-500 font-medium">编辑剧本大纲</label>
              <textarea value={worldOutline} onChange={(e: any) =>setWorldOutline(e.target.value)} rows={8} className="input-field text-xs resize-y" />
              <button onClick={()=>updateScenario()} className="text-[10px] px-3 py-1.5 bg-indigo-50 text-indigo-700 rounded-lg border border-indigo-200 hover:bg-indigo-100">保存修改</button>
            </div>
          ) : (
            <details className="bg-gray-50 rounded-lg p-3 border border-gray-200">
              <summary className="text-xs text-ink-500 cursor-pointer select-none">展开完整大纲</summary>
              <pre className="text-xs text-ink-700 whitespace-pre-wrap font-sans leading-relaxed mt-2 max-h-64 overflow-y-auto">{worldOutline.slice(0,2500)}{worldOutline.length>2500?'...':''}</pre>
            </details>
          )}
          {sourceChunks.length>0&&(
            <p className="text-[10px] text-ink-400">已切分为 {sourceChunks.length} 个片段 · 切分方式: {splitter==='llm'?'LLM 智能切分':splitter==='recursive'?'递归切分':'语义切分'}</p>
          )}
          {scenarioId&&<p className="text-[10px] text-ink-400">已保存 · 可在下次游戏时直接加载</p>}
        </div>
      )}
    </>
  );
}
