/** 戏法与法术选择（D&D 5e 施法职业）（从 CharacterStep 拆出；值经 useStartWizard 取用）。 */
import { useStartWizard } from '../StartWizardContext';
import { COC_OCCUPATIONS } from '../../../gameSystems';

export default function SpellPickerSection() {
  const {
    availableCantrips,
    availableLevel1,
    cantripQuota,
    customClasses,
    gameSystem,
    occupation,
    selectedCantrips,
    selectedLevel1,
    setOccupation,
    spellPicks,
    spellPoolBusy,
    spellQuota,
    toggleSpell,
  } = useStartWizard();

  return (
    <>
                  {/* 戏法与法术选择（D&D 5e 施法职业） */}
                  {gameSystem==='dnd5e' && (cantripQuota>0 || spellQuota>0) && (
                    <div>
                      <label className="block text-xs font-medium text-ink-600 mb-2">
                        戏法与法术选择
                        <span className="text-ink-400 font-normal">（戏法 {selectedCantrips.length}/{cantripQuota} · 一环法术 {selectedLevel1.length}/{spellQuota}）</span>
                      </label>
                      {spellPoolBusy&&<p className="text-[10px] text-ink-400 mb-1">正在加载法术池（首次会从知识库自动抓取 SRD 法术）...</p>}
                      {!spellPoolBusy && availableCantrips.length===0 && availableLevel1.length===0 && (
                        <p className="text-[10px] text-ink-400">该职业暂无可用法术列表。</p>
                      )}
                      {availableCantrips.length>0 && (
                        <div className="mb-2">
                          <p className="text-[10px] text-indigo-600 font-medium mb-1">戏法（等级0）</p>
                          <div className="space-y-1 max-h-40 overflow-y-auto pr-1">
                            {availableCantrips.map((s: any) =>{
                              const sel=spellPicks.some((p: any) =>p.name===s.name);
                              return (
                                <button key={s.name} onClick={()=>toggleSpell(s)} className={`w-full text-left p-2 rounded-lg border text-xs transition-all ${sel?'border-indigo-400 bg-indigo-50 text-indigo-700':'border-gray-200 bg-white text-ink-600 hover:border-gray-300'}`}>
                                  <div className="flex items-center justify-between">
                                    <span className="font-medium">{s.name_zh||s.name}</span>
                                    <span className="text-[9px] text-ink-400">{s.school}</span>
                                  </div>
                                  <p className="text-[10px] text-ink-500 mt-0.5 line-clamp-2">{s.description_zh||s.description}</p>
                                </button>
                              );
                            })}
                          </div>
                        </div>
                      )}
                      {availableLevel1.length>0 && (
                        <div>
                          <p className="text-[10px] text-indigo-600 font-medium mb-1">一环法术</p>
                          <div className="space-y-1 max-h-44 overflow-y-auto pr-1">
                            {availableLevel1.map((s: any) =>{
                              const sel=spellPicks.some((p: any) =>p.name===s.name);
                              return (
                                <button key={s.name} onClick={()=>toggleSpell(s)} className={`w-full text-left p-2 rounded-lg border text-xs transition-all ${sel?'border-indigo-400 bg-indigo-50 text-indigo-700':'border-gray-200 bg-white text-ink-600 hover:border-gray-300'}`}>
                                  <div className="flex items-center justify-between">
                                    <span className="font-medium">{s.name_zh||s.name}</span>
                                    <span className="text-[9px] text-ink-400">{s.school}{s.ritual?' · 仪式':''}</span>
                                  </div>
                                  <p className="text-[10px] text-ink-500 mt-0.5 line-clamp-2">{s.description_zh||s.description}</p>
                                </button>
                              );
                            })}
                          </div>
                        </div>
                      )}
                      {spellPicks.length>0 && (
                        <p className="text-[10px] text-indigo-500 mt-1">已选: {spellPicks.map((s: any) =>s.name).join('、')}</p>
                      )}
                    </div>
                  )}

                  {gameSystem==='coc'&&(
                    <div>
                      <label className="block text-xs font-medium text-ink-600 mb-2">调查员职业</label>
                      <div className="grid grid-cols-2 gap-1.5">
                        {[...COC_OCCUPATIONS, ...customClasses].map((o: any) =>(
                          <button key={o} onClick={()=>setOccupation(o)} className={`p-2 rounded-lg border text-left text-xs transition-all ${occupation===o?'border-indigo-400 bg-indigo-50 text-indigo-700':'border-gray-200 bg-white text-ink-600 hover:border-gray-300'}`}>{o}</button>
                        ))}
                      </div>
                    </div>
                  )}

    </>
  );
}
