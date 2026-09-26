/** 种族与职业选择（按规则系统）（从 CharacterStep 拆出；值经 useStartWizard 取用）。 */
import { useStartWizard } from '../StartWizardContext';
import { DND4_CLASSES } from '../../../gameSystems';
import { ATTRS, RACES, CLASSES } from '../../../data/dndData';

export default function SpeciesClassSection() {
  const {
    cc,
    charClass,
    customClasses,
    gameSystem,
    race,
    rc,
    setCharClass,
    setRace,
  } = useStartWizard();

  return (
    <>
                  {/* 种族（仅 D&D 系） */}
                  {(gameSystem==='dnd5e'||gameSystem==='dnd4e')&&(
                    <div>
                      <label className="block text-xs font-medium text-ink-600 mb-2">种族</label>
                      <div className="grid grid-cols-2 gap-1.5">
                        {Object.entries(RACES).map(([k,v])=>(
                          <button key={k} onClick={()=>setRace(k)} className={`p-2 rounded-lg border text-left text-xs transition-all ${race===k?'border-indigo-400 bg-indigo-50 text-indigo-700':'border-gray-200 bg-white text-ink-600 hover:border-gray-300'}`}>{v.name}</button>
                        ))}
                      </div>
                      <div className="mt-2 bg-gray-50 rounded-lg p-2.5 border border-gray-200">
                        <p className="text-[10px] text-ink-500 font-medium mb-1">{rc.name} 特性</p>
                        {rc.traits.map((t: any, i: any) =><p key={i} className="text-[11px] text-ink-600">· {t}</p>)}
                      </div>
                    </div>
                  )}

                  {/* 职业 / 调查员职业 */}
                  {(gameSystem==='dnd5e'||gameSystem==='dnd4e')&&(
                    <div>
                      <label className="block text-xs font-medium text-ink-600 mb-2">{gameSystem==='dnd4e'?'职业（4e）':'职业'}</label>
                      <div className="grid grid-cols-2 gap-1.5">
                        {[...(gameSystem==='dnd4e'?DND4_CLASSES:Object.keys(CLASSES)), ...customClasses].map((k: any) =>{
                          const v=CLASSES[k]||{name:k,hd:'?',pri:'str',profs:[]};
                          return(
                            <button key={k} onClick={()=>setCharClass(k)} className={`p-2 rounded-lg border text-left text-xs transition-all ${charClass===k?'border-indigo-400 bg-indigo-50 text-indigo-700':'border-gray-200 bg-white text-ink-600 hover:border-gray-300'}`}>{v.name} {gameSystem==='dnd4e'?'':<span className="text-[9px] text-ink-400">({v.hd})</span>}</button>
                          );
                        })}
                      </div>
                      <div className="mt-2 bg-gray-50 rounded-lg p-2.5 border border-gray-200">
                        <p className="text-[10px] text-ink-500 font-medium mb-1">{cc.name} · HP{cc.hd} · 主属性:{ATTRS.find((a: any) =>a.k===cc.pri)?.n}</p>
                        <div className="flex flex-wrap gap-1">{cc.profs.map((p: any, i: any) =><span key={i} className="text-[10px] bg-indigo-50 text-indigo-700 px-1.5 py-0.5 rounded-full border border-indigo-100">{p}</span>)}</div>
                      </div>
                    </div>
                  )}

    </>
  );
}
