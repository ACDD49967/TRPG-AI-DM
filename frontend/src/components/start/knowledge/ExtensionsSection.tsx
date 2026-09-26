/** 扩展包管理（从 KnowledgeStep 拆出；值经 useStartWizard 取用）。 */
import { useStartWizard } from '../StartWizardContext';
import { GAME_SYSTEM_LABELS, GAME_SYSTEM_OPTIONS, type GameSystem } from '../../../gameSystems';
import InlineEdit from '../../ui/InlineEdit';

export default function ExtensionsSection() {
  const {
    activeExtIds,
    addExt,
    deleteExt,
    extBusy,
    extContent,
    extDesc,
    extErr,
    extGenDesc,
    extList,
    extName,
    extSystem,
    extTags,
    genExt,
    loadExts,
    setActiveExtIds,
    setExtContent,
    setExtDesc,
    setExtGenDesc,
    setExtName,
    setExtSystem,
    setExtTags,
    username,
  } = useStartWizard();

  return (
    <>
                  {/* 扩展包管理 */}
                  <div className="border-t border-gray-200 pt-4 space-y-3">
                    <p className="text-xs font-bold text-ink-800">扩展包（增强游戏性与个性）</p>
                    <div className="grid md:grid-cols-2 gap-3">
                      <div className="bg-gray-50 rounded-lg p-3 border border-gray-200 space-y-2">
                        <p className="text-xs font-medium text-ink-700">手动添加扩展包</p>
                        <input value={extName} onChange={(e: any) =>setExtName(e.target.value)} placeholder="扩展包名称" className="input-field text-xs" />
                        <input value={extDesc} onChange={(e: any) =>setExtDesc(e.target.value)} placeholder="一句话简介" className="input-field text-xs" />
                        <select value={extSystem} onChange={(e: any) =>setExtSystem(e.target.value as GameSystem)} className="input-field text-xs">
                          {GAME_SYSTEM_OPTIONS.map((o: any) =><option key={o.id} value={o.id}>{o.label}</option>)}
                        </select>
                        <textarea value={extContent} onChange={(e: any) =>setExtContent(e.target.value)} placeholder="扩展内容：规则、能力、物品、NPC、事件等" rows={4} className="input-field resize-none text-xs" />
                        <input value={extTags} onChange={(e: any) =>setExtTags(e.target.value)} placeholder="标签，用逗号分隔" className="input-field text-xs" />
                        <button onClick={addExt} disabled={extBusy || !extContent.trim()} className="w-full py-2 bg-indigo-50 border border-indigo-200 hover:bg-indigo-100 text-indigo-700 rounded-lg text-xs font-medium disabled:opacity-50">保存扩展包</button>
                      </div>
                      <div className="bg-gray-50 rounded-lg p-3 border border-gray-200 space-y-2">
                        <p className="text-xs font-medium text-ink-700">AI 生成扩展包</p>
                        <select value={extSystem} onChange={(e: any) =>setExtSystem(e.target.value as GameSystem)} className="input-field text-xs">
                          {GAME_SYSTEM_OPTIONS.map((o: any) =><option key={o.id} value={o.id}>{o.label}</option>)}
                        </select>
                        <textarea value={extGenDesc} onChange={(e: any) =>setExtGenDesc(e.target.value)} placeholder="描述你想要的扩展包，例如：新增一个酒馆斗殴规则和三个NPC" rows={4} className="input-field resize-none text-xs" />
                        <button onClick={genExt} disabled={extBusy || !extGenDesc.trim()} className="w-full py-2 bg-emerald-50 border border-emerald-200 hover:bg-emerald-100 text-emerald-700 rounded-lg text-xs font-medium disabled:opacity-50">{extBusy?'生成中...':'让 AI 生成扩展包'}</button>
                      </div>
                    </div>
                    {extErr&&<p className="text-red-700 text-xs">{extErr}</p>}
                    <div className="space-y-1.5">
                      <p className="text-xs font-medium text-ink-700">已有扩展包（{extList.length}）· 勾选后将在新游戏中启用</p>
                      {extList.length===0&&<p className="text-xs text-ink-400">暂无扩展包，可手动添加或让 AI 生成。</p>}
                      {extList.map((e: any) =>(
                        <label key={e.id} className={`flex items-center justify-between bg-white rounded-lg p-2.5 border cursor-pointer ${activeExtIds.includes(e.id)?'border-indigo-300 bg-indigo-50/40':'border-gray-200'}`}>
                          <span className="min-w-0">
                            <span className="text-xs font-medium text-ink-800 truncate">{e.name}</span>
                            <span className="block text-[10px] text-ink-500">{(GAME_SYSTEM_LABELS as Record<string, string>)[(e.system as GameSystem)||'custom']} · {e.source} · {e.description}</span>
                          </span>
                          <span className="flex items-center gap-2">
                            <InlineEdit
                              label="编辑扩展包"
                              fields={[
                                { key: 'name', label: '名称', value: e.name || '' },
                                { key: 'description', label: '描述', value: e.description || '', type: 'textarea' },
                              ]}
                              onSave={async (values: Record<string, any>) => {
                                const response = await fetch(
                                  `/api/extensions/${encodeURIComponent(e.id)}?username=${encodeURIComponent(username || 'default')}`,
                                  {
                                    method: 'PUT',
                                    headers: { 'Content-Type': 'application/json' },
                                    body: JSON.stringify({ name: values.name, description: values.description }),
                                  });
                                if (!response.ok) return;
                                await loadExts?.();
                              }}
                            />
                            <input type="checkbox" checked={activeExtIds.includes(e.id)} onChange={()=>setActiveExtIds((ids: any) =>ids.includes(e.id)?ids.filter((x: any) =>x!==e.id):[...ids,e.id])} />
                            <button onClick={()=>deleteExt(e.id)} className="text-[10px] text-red-700 hover:text-red-700 px-2 py-1">删除</button>
                          </span>
                        </label>
                      ))}
                    </div>
                  </div>

    </>
  );
}
