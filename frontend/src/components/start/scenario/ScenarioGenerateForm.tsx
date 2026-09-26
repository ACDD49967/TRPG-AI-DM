/** AI 生成剧本输入区：世界描述、经典参考、基调与备注（从 ScenarioStep 拆出；值经 useStartWizard 取用）。 */
import { useStartWizard } from '../StartWizardContext';
import { TONES } from '../../../data/dndData';
import { type GameSystem } from '../../../gameSystems';

export default function ScenarioGenerateForm() {
  const { scenarioMode, worldDesc, setWorldDesc, classicScenarios, setWorldTone, setGameSystem,
    toneCustom, worldTone, setToneCustom, customTone, setCustomTone, referenceScript,
    setReferenceScript, worldNote, setWorldNote,
  } = useStartWizard();

  return (
    <>
      {scenarioMode==='generate'&&(
        <div className="space-y-4">
          <div>
            <label className="block text-xs font-medium text-ink-600 mb-1">世界描述</label>
            <textarea value={worldDesc} onChange={(e: any) =>setWorldDesc(e.target.value)} placeholder="描述你想要的冒险..." rows={3} className="input-field resize-none" />
          </div>

          {classicScenarios.length>0 && (
            <details className="bg-amber-50/60 border border-amber-200 rounded-lg p-3">
              <summary className="text-xs text-amber-800 font-medium cursor-pointer">经典剧本参考（公开/免费，点击展开）</summary>
              <div className="mt-2 space-y-2">
                {classicScenarios.map((cs: any) =>(
                  <div key={cs.name} className="bg-white border border-amber-100 rounded-lg p-2">
                    <div className="flex items-center justify-between">
                      <div>
                        <p className="text-xs font-bold text-ink-800">{cs.name}</p>
                        <p className="text-[9px] text-ink-400">{cs.system} · {cs.tone} · {cs.source}</p>
                      </div>
                      <button
                        onClick={()=>{ setWorldDesc(cs.summary); setWorldTone(cs.tone); setGameSystem((cs.system==='coc'||cs.system==='dnd5e'||cs.system==='dnd4e'||cs.system==='custom')?cs.system as GameSystem:'dnd5e'); }}
                        className="text-[10px] px-2 py-1 bg-amber-50 text-amber-700 rounded-lg border border-amber-200 hover:bg-amber-100"
                      >使用此背景</button>
                    </div>
                    <p className="text-[10px] text-ink-500 mt-1">{cs.summary}</p>
                  </div>
                ))}
              </div>
            </details>
          )}

          <div className="grid grid-cols-2 gap-3">
            <div>
              <label className="block text-xs font-medium text-ink-600 mb-1">基调</label>
              <select
                value={toneCustom ? '__custom__' : worldTone}
                onChange={(e: any) =>{
                  if(e.target.value==='__custom__'){
                    setToneCustom(true);
                    if(customTone) setWorldTone(customTone);
                  } else {
                    setToneCustom(false);
                    setWorldTone(e.target.value);
                  }
                }}
                className="input-field"
              >
                {TONES.map((t: any) =><option key={t} value={t}>{t}</option>)}
                <option value="__custom__">自定义...</option>
              </select>
              {toneCustom&&(
                <input
                  value={customTone}
                  onChange={(e: any) =>{ setCustomTone(e.target.value); setWorldTone(e.target.value); }}
                  placeholder="输入自定义基调"
                  className="input-field mt-1 text-xs"
                />
              )}
            </div>
            <div>
              <label className="block text-xs font-medium text-ink-600 mb-1">参考剧本</label>
              <textarea value={referenceScript} onChange={(e: any) =>setReferenceScript(e.target.value)} placeholder="粘贴参考文本..." rows={2} className="input-field resize-none" />
            </div>
          </div>

          <div>
            <label className="block text-xs font-medium text-ink-600 mb-1">备注</label>
            <textarea value={worldNote} onChange={(e: any) =>setWorldNote(e.target.value)} placeholder="特殊规则、限制..." rows={2} className="input-field resize-none" />
          </div>
        </div>
      )}
    </>
  );
}
