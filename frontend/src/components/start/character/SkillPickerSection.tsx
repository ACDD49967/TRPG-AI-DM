/** 技能熟练选择与 COC 技能点分配（从 CharacterStep 拆出；值经 useStartWizard 取用）。
 *
 * 注意：COC 的技能点区嵌在技能选择区内部，两者原本被误切成两个组件，
 * 合并后 JSX 才是平衡的。
 */
import { useStartWizard } from '../StartWizardContext';
import { COC_SKILLS, COC_SKILL_BASE } from '../../../gameSystems';
import { ATTRS, SKILLS } from '../../../data/dndData';

export default function SkillPickerSection() {
  const {
    cocSkillPicks,
    customSkills,
    gameSystem,
    setCocSkillPicks,
    skillPicks,
    toggleSkill,
    cocOccInc,
    cocOccPool,
    cocOccRemain,
    cocPerInc,
    cocPerPool,
    cocPerRemain,
    decCocOcc,
    decCocPer,
    incCocOcc,
    incCocPer,
  } = useStartWizard();

  return (
    <>
                  {/* 技能熟练选择（按系统） */}
                  {(gameSystem==='dnd5e'||gameSystem==='dnd4e')&&(
                    <div>
                      <label className="block text-xs font-medium text-ink-600 mb-2">
                        技能熟练 <span className="text-ink-400 font-normal">（选择2项 — 检定中获得+2熟练加值）</span>
                      </label>
                      <div className="grid grid-cols-3 gap-1">
                        {SKILLS.map((s: any) =>{
                          const sel=skillPicks.includes(s.n);
                          const attrName=ATTRS.find((a: any) =>a.k===s.a)?.n||s.a;
                          return(
                            <button key={s.n} onClick={()=>toggleSkill(s.n)}
                              className={`p-1.5 rounded-lg border text-left text-[10px] transition-all ${
                                sel?'border-indigo-400 bg-indigo-50 text-indigo-700':'border-gray-200 bg-white text-ink-500 hover:border-gray-300'
                              }`}>
                              <div className="font-medium">{s.n}</div>
                              <div className="text-[8px] opacity-60">{attrName} · {s.d}</div>
                            </button>
                          );
                        })}
                        {customSkills.map((s: any) =>{
                          const sel=skillPicks.includes(s);
                          return(
                            <button key={s} onClick={()=>toggleSkill(s)}
                              className={`p-1.5 rounded-lg border text-left text-[10px] transition-all ${
                                sel?'border-indigo-400 bg-indigo-50 text-indigo-700':'border-gray-200 bg-white text-ink-500 hover:border-gray-300'
                              }`}>
                              <div className="font-medium">{s}</div>
                              <div className="text-[8px] opacity-60">剧本专属</div>
                            </button>
                          );
                        })}
                      </div>
                      {skillPicks.length>0&&<p className="text-[10px] text-indigo-500 mt-1">已选: {skillPicks.join('、')}</p>}
                    </div>
                  )}
                  {gameSystem==='coc'&&(
                    <div>
                      <label className="block text-xs font-medium text-ink-600 mb-2">
                        职业技能 <span className="text-ink-400 font-normal">（选择最多8项，作为初始技能熟练）</span>
                      </label>
                      <div className="grid grid-cols-3 gap-1">
                        {[...COC_SKILLS, ...customSkills].map((s: any) =>{
                          const sel=cocSkillPicks.includes(s);
                          return(
                            <button key={s} onClick={()=>setCocSkillPicks((p: any) =>p.includes(s)?p.filter((x: any) =>x!==s):p.length<8?[...p,s]:p)}
                              className={`p-1.5 rounded-lg border text-left text-[10px] transition-all ${
                                sel?'border-indigo-400 bg-indigo-50 text-indigo-700':'border-gray-200 bg-white text-ink-500 hover:border-gray-300'
                              }`}>
                              <div className="font-medium">{s}</div>
                            </button>
                          );
                        })}
                      </div>
                      {cocSkillPicks.length>0&&<p className="text-[10px] text-indigo-500 mt-1">已选: {cocSkillPicks.join('、')}</p>}

                      {/* COC 技能点分配（双池官方规则） */}
                      <div className="mt-3 bg-gray-50 rounded-lg p-3 border border-gray-200">
                        <div className="grid grid-cols-2 gap-2 text-xs">
                          <div className="bg-white rounded-lg border border-gray-200 p-2">
                            <p className="text-ink-600">职业技能点（教育×4）</p>
                            <p>可用 <b className="text-ink-800">{cocOccPool}</b> · 剩余 <b className={cocOccRemain<0?'text-red-700':'text-emerald-600'}>{cocOccRemain}</b></p>
                          </div>
                          <div className="bg-white rounded-lg border border-gray-200 p-2">
                            <p className="text-ink-600">个人兴趣点（智力×2）</p>
                            <p>可用 <b className="text-ink-800">{cocPerPool}</b> · 剩余 <b className={cocPerRemain<0?'text-red-700':'text-emerald-600'}>{cocPerRemain}</b></p>
                          </div>
                        </div>
                        <div className="max-h-56 overflow-y-auto mt-2 space-y-1">
                          {COC_SKILLS.map((s: any) =>{
                            const base=COC_SKILL_BASE[s]||0;
                            const occ=cocOccInc[s]||0;
                            const per=cocPerInc[s]||0;
                            const final=base+occ+per;
                            return (
                              <div key={s} className="bg-white rounded-lg border border-gray-200 px-2 py-1">
                                <div className="flex items-center justify-between">
                                  <span className="text-[10px] text-ink-600">{s} <span className="text-ink-400">基础{base} → 最终{final}</span></span>
                                  <span className="text-xs font-bold text-ink-800">{final}</span>
                                </div>
                                <div className="flex items-center gap-1 mt-1 text-[9px]">
                                  <span className="text-ink-400 w-7">职业</span>
                                  <button onClick={()=>decCocOcc(s)} disabled={occ<=0} className="w-5 h-5 rounded bg-gray-100 border border-gray-200 text-ink-500 disabled:opacity-30">−</button>
                                  <span className="w-6 text-center font-medium">{occ}</span>
                                  <button onClick={()=>incCocOcc(s)} disabled={final>=75||cocOccRemain<=0} className="w-5 h-5 rounded bg-gray-100 border border-gray-200 text-ink-500 disabled:opacity-30">+</button>
                                  <span className="text-ink-400 w-7 ml-2">个人</span>
                                  <button onClick={()=>decCocPer(s)} disabled={per<=0} className="w-5 h-5 rounded bg-gray-100 border border-gray-200 text-ink-500 disabled:opacity-30">−</button>
                                  <span className="w-6 text-center font-medium">{per}</span>
                                  <button onClick={()=>incCocPer(s)} disabled={final>=75||cocPerRemain<=0} className="w-5 h-5 rounded bg-gray-100 border border-gray-200 text-ink-500 disabled:opacity-30">+</button>
                                </div>
                              </div>
                            );
                          })}
                        </div>
                        <p className="text-[9px] text-ink-400 mt-1">COC 7e 官方规则：职业技能点=教育×4，个人兴趣点=智力×2；每项最终值=基础+职业+个人，最高75（含基础值）。</p>
                      </div>
                    </div>
                  )}
                  {gameSystem==='custom'&&(
                    <p className="text-[11px] text-ink-500 bg-gray-50 rounded-lg p-2 border border-gray-200">自定义规则：技能与判定方式由你在「自定义规则」文本中定义，AI DM 会按规则文本处理。</p>
                  )}

    </>
  );
}
