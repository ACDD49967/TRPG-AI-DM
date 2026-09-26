/** DM 工具弹窗：新增角色/地点/生物/法术的快捷入口。
 *
 * 从 GameScreen 拆出：依赖经 props 显式传入，行为与拆分前一致。
 */
import Modal from '../ui/Modal';

export interface DmToolsModalProps {
  [key: string]: any;
}

export default function DmToolsModal(props: DmToolsModalProps) {
  const {
    addDmBeast,
    addDmMap,
    addDmNpc,
    addDmSpell,
    dmBeast,
    dmMap,
    dmNpc,
    dmSpell,
    setDmBeast,
    setDmBeastImage,
    setDmMap,
    setDmMapImage,
    setDmNpc,
    setDmNpcImage,
    setDmSpell,
    setShowDmTools,
    showDmTools,
  } = props;

  return (
    <>
          <Modal
            open={showDmTools}
            onClose={() => setShowDmTools(false)}
            paper
            size="md"
            icon="🛠️"
            title="DM 工具"
            subtitle="手动补充角色 / 地点 / 生物 / 法术，立即写入当前剧本图鉴"
          >

                {/* 低 token 快捷工具说明 */}
                <div className="mb-4 border-b border-amber-900/10 pb-3">
                  <p className="text-xs font-bold text-ink-700 mb-1">DM 低 token 快捷工具（Function Calling）</p>
                  <p className="text-[10px] text-ink-500 leading-relaxed">
                    get_character_state（查状态）· adjust_resource（资源增减）· cast_spell（扣法术位）·
                    learn_spell / forget_spell（习得/遗忘法术）· search_npcs（查NPC）· adjust_npc（NPC数值增减）·
                    search_bestiary / adjust_bestiary（查/改生物）· search_spells（查法术）
                  </p>
                </div>

                {/* 新增角色/NPC */}
                <div className="mb-4 border-b border-amber-900/10 pb-3">
                  <p className="text-xs font-bold text-ink-700 mb-2">新增角色 / NPC</p>
                  <div className="grid grid-cols-2 gap-2">
                    <input value={dmNpc.name} onChange={(e: any) =>setDmNpc({...dmNpc,name:e.target.value})} placeholder="名称 *" className="input-field text-xs" />
                    <input value={dmNpc.role} onChange={(e: any) =>setDmNpc({...dmNpc,role:e.target.value})} placeholder="身份" className="input-field text-xs" />
                    <input value={dmNpc.location} onChange={(e: any) =>setDmNpc({...dmNpc,location:e.target.value})} placeholder="位置" className="input-field text-xs" />
                    <div className="flex gap-2">
                      <input type="number" value={dmNpc.hp} onChange={(e: any) =>setDmNpc({...dmNpc,hp:Number(e.target.value)||10})} placeholder="HP" className="input-field text-xs" />
                      <input type="number" value={dmNpc.ac} onChange={(e: any) =>setDmNpc({...dmNpc,ac:Number(e.target.value)||10})} placeholder="AC" className="input-field text-xs" />
                    </div>
                  </div>
                  <input type="file" accept=".png,.jpg,.jpeg,.webp" onChange={(e: any) =>setDmNpcImage(e.target.files?.[0]||null)} className="block w-full text-[10px] mt-2 text-ink-500" />
                  <button onClick={addDmNpc} className="mt-2 text-xs px-3 py-1.5 bg-amber-50 text-amber-700 rounded-lg border border-amber-200 hover:bg-amber-100">新增角色</button>
                </div>

                {/* 新增地点 */}
                <div className="mb-4 border-b border-amber-900/10 pb-3">
                  <p className="text-xs font-bold text-ink-700 mb-2">新增地点</p>
                  <div className="grid grid-cols-1 gap-2">
                    <input value={dmMap.name} onChange={(e: any) =>setDmMap({...dmMap,name:e.target.value})} placeholder="地点名称 *" className="input-field text-xs" />
                    <textarea value={dmMap.description} onChange={(e: any) =>setDmMap({...dmMap,description:e.target.value})} placeholder="描述" rows={2} className="input-field text-xs resize-none" />
                  </div>
                  <input type="file" accept=".png,.jpg,.jpeg,.webp" onChange={(e: any) =>setDmMapImage(e.target.files?.[0]||null)} className="block w-full text-[10px] mt-2 text-ink-500" />
                  <button onClick={addDmMap} className="mt-2 text-xs px-3 py-1.5 bg-amber-50 text-amber-700 rounded-lg border border-amber-200 hover:bg-amber-100">新增地点</button>
                </div>

                {/* 新增生物 */}
                <div>
                  <p className="text-xs font-bold text-ink-700 mb-2">新增生物（完整字段请在生物图鉴弹窗内填写）</p>
                  <div className="grid grid-cols-2 gap-2">
                    <input value={dmBeast.name} onChange={(e: any) =>setDmBeast({...dmBeast,name:e.target.value})} placeholder="生物名称 *" className="input-field text-xs" />
                    <input value={dmBeast.tags} onChange={(e: any) =>setDmBeast({...dmBeast,tags:e.target.value})} placeholder="标签" className="input-field text-xs" />
                    <input value={dmBeast.ac} onChange={(e: any) =>setDmBeast({...dmBeast,ac:e.target.value})} placeholder="AC" className="input-field text-xs" />
                    <input value={dmBeast.hp} onChange={(e: any) =>setDmBeast({...dmBeast,hp:e.target.value})} placeholder="HP" className="input-field text-xs" />
                  </div>
                  <textarea value={dmBeast.description} onChange={(e: any) =>setDmBeast({...dmBeast,description:e.target.value})} placeholder="描述" rows={2} className="input-field text-xs resize-none mt-2 w-full" />
                  <input type="file" accept=".png,.jpg,.jpeg,.webp" onChange={(e: any) =>setDmBeastImage(e.target.files?.[0]||null)} className="block w-full text-[10px] mt-2 text-ink-500" />
                  <button onClick={addDmBeast} className="mt-2 text-xs px-3 py-1.5 bg-amber-50 text-amber-700 rounded-lg border border-amber-200 hover:bg-amber-100">新增生物</button>
                </div>

                {/* 新增法术/仪式（玩家/DM 自建） */}
                <div className="mt-4 pt-3 border-t border-amber-900/10">
                  <p className="text-xs font-bold text-ink-700 mb-2">新增法术 / 仪式（玩家或 DM 自建）</p>
                  <div className="grid grid-cols-2 gap-2">
                    <input value={dmSpell.name} onChange={(e: any) =>setDmSpell({...dmSpell,name:e.target.value})} placeholder="法术名称 *" className="input-field text-xs" />
                    <input value={dmSpell.level} onChange={(e: any) =>setDmSpell({...dmSpell,level:e.target.value})} placeholder="环位（0=戏法）" className="input-field text-xs" />
                    <input value={dmSpell.school} onChange={(e: any) =>setDmSpell({...dmSpell,school:e.target.value})} placeholder="学派（塑能/防护/...）" className="input-field text-xs" />
                    <input value={dmSpell.casting_time} onChange={(e: any) =>setDmSpell({...dmSpell,casting_time:e.target.value})} placeholder="施法时间（1 动作）" className="input-field text-xs" />
                    <input value={dmSpell.range} onChange={(e: any) =>setDmSpell({...dmSpell,range:e.target.value})} placeholder="施法距离（150 尺/触及/自身）" className="input-field text-xs" />
                    <input value={dmSpell.components} onChange={(e: any) =>setDmSpell({...dmSpell,components:e.target.value})} placeholder="成分（V、S、M）" className="input-field text-xs" />
                    <input value={dmSpell.duration} onChange={(e: any) =>setDmSpell({...dmSpell,duration:e.target.value})} placeholder="持续时间（立即/专注）" className="input-field text-xs" />
                    <input value={dmSpell.classes} onChange={(e: any) =>setDmSpell({...dmSpell,classes:e.target.value})} placeholder="职业（术士、法师）" className="input-field text-xs" />
                    <label className="col-span-2 flex items-center gap-2 text-[10px] text-ink-500">
                      <input type="checkbox" checked={dmSpell.ritual} onChange={(e: any) =>setDmSpell({...dmSpell,ritual:e.target.checked})} /> 仪式法术
                    </label>
                    <textarea value={dmSpell.description} onChange={(e: any) =>setDmSpell({...dmSpell,description:e.target.value})} placeholder="效果描述（含伤害、豁免、升环效应）" rows={3} className="input-field text-xs resize-none col-span-2" />
                  </div>
                  <button onClick={addDmSpell} className="mt-2 text-xs px-3 py-1.5 bg-amber-50 text-amber-700 rounded-lg border border-amber-200 hover:bg-amber-100">新增法术</button>
                </div>
          </Modal>
    </>
  );
}
