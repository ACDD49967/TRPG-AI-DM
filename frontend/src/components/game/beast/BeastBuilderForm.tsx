/** 自建生物表单：名称/数值/描述/特性/动作/习性/图片（从 BeastModal 拆出）。 */
export default function BeastBuilderForm({ dmBeast, setDmBeast, setDmBeastImage, onSave }: {
  dmBeast: any;
  setDmBeast: (value: any) => void;
  setDmBeastImage: (file: File | null) => void;
  onSave: () => void;
}) {
  return (
                      <div className="rounded-xl border border-parch-400/50 bg-parch-100/60 p-3 space-y-2.5 mb-3">
                        <p className="text-xs font-bold text-ink-700">自建生物</p>
                        <div className="grid grid-cols-2 gap-2">
                          <input value={dmBeast.name} onChange={(e: any) =>setDmBeast({...dmBeast,name:e.target.value})} placeholder="生物名称 *" className="input-field text-xs" />
                          <input value={dmBeast.tags} onChange={(e: any) =>setDmBeast({...dmBeast,tags:e.target.value})} placeholder="标签（人形生物/神话...）" className="input-field text-xs" />
                          <input value={dmBeast.ac} onChange={(e: any) =>setDmBeast({...dmBeast,ac:e.target.value})} placeholder="AC" className="input-field text-xs" />
                          <input value={dmBeast.hp} onChange={(e: any) =>setDmBeast({...dmBeast,hp:e.target.value})} placeholder="HP" className="input-field text-xs" />
                          <input value={dmBeast.speed} onChange={(e: any) =>setDmBeast({...dmBeast,speed:e.target.value})} placeholder="速度（30尺）" className="input-field text-xs" />
                          <input value={dmBeast.str} onChange={(e: any) =>setDmBeast({...dmBeast,str:e.target.value})} placeholder="力量" className="input-field text-xs" />
                          <input value={dmBeast.dex} onChange={(e: any) =>setDmBeast({...dmBeast,dex:e.target.value})} placeholder="敏捷" className="input-field text-xs" />
                          <input value={dmBeast.con} onChange={(e: any) =>setDmBeast({...dmBeast,con:e.target.value})} placeholder="体质" className="input-field text-xs" />
                          <input value={dmBeast.int} onChange={(e: any) =>setDmBeast({...dmBeast,int:e.target.value})} placeholder="智力" className="input-field text-xs" />
                          <input value={dmBeast.wis} onChange={(e: any) =>setDmBeast({...dmBeast,wis:e.target.value})} placeholder="感知" className="input-field text-xs" />
                          <input value={dmBeast.cha} onChange={(e: any) =>setDmBeast({...dmBeast,cha:e.target.value})} placeholder="魅力" className="input-field text-xs" />
                          <input value={dmBeast.skills} onChange={(e: any) =>setDmBeast({...dmBeast,skills:e.target.value})} placeholder="技能（察觉+4，隐匿+5）" className="input-field text-xs" />
                        </div>
                        <textarea value={dmBeast.description} onChange={(e: any) =>setDmBeast({...dmBeast,description:e.target.value})} placeholder="生物描述" rows={2} className="input-field text-xs resize-none w-full" />
                        <textarea value={dmBeast.traits} onChange={(e: any) =>setDmBeast({...dmBeast,traits:e.target.value})} placeholder="特性（多行，如：黑暗视觉：...）" rows={2} className="input-field text-xs resize-none w-full" />
                        <textarea value={dmBeast.actions} onChange={(e: any) =>setDmBeast({...dmBeast,actions:e.target.value})} placeholder="动作（多行，如：啃咬：+5 1d8+3）" rows={2} className="input-field text-xs resize-none w-full" />
                        <div className="grid grid-cols-2 gap-2">
                          <input value={dmBeast.habits} onChange={(e: any) =>setDmBeast({...dmBeast,habits:e.target.value})} placeholder="习性" className="input-field text-xs" />
                          <input value={dmBeast.habitat} onChange={(e: any) =>setDmBeast({...dmBeast,habitat:e.target.value})} placeholder="栖息地" className="input-field text-xs" />
                          <input value={dmBeast.lore} onChange={(e: any) =>setDmBeast({...dmBeast,lore:e.target.value})} placeholder="传说/背景" className="input-field text-xs" />
                          <input value={dmBeast.weakness} onChange={(e: any) =>setDmBeast({...dmBeast,weakness:e.target.value})} placeholder="弱点" className="input-field text-xs" />
                        </div>
                        <input type="file" accept=".png,.jpg,.jpeg,.webp" onChange={(e: any) =>setDmBeastImage(e.target.files?.[0]||null)} className="block w-full text-[10px] text-ink-500" />
                      <button onClick={onSave} className="btn-xs-paper mt-1">保存到当前剧本生物库</button>
                      </div>
  );
}
