/** 地图与生物图鉴管理（从 KnowledgeStep 拆出；值经 useStartWizard 取用）。 */
import { useStartWizard } from '../StartWizardContext';
import { GAME_SYSTEM_OPTIONS, type GameSystem } from '../../../gameSystems';

export default function MediaSection() {
  const {
    beastDesc,
    beastFile,
    beastName,
    beastStats,
    beastSystem,
    beastTags,
    bestiary,
    deleteBeast,
    deleteMap,
    mapDesc,
    mapFile,
    mapName,
    mapSystem,
    maps,
    mediaBusy,
    setBeastDesc,
    setBeastFile,
    setBeastName,
    setBeastStats,
    setBeastSystem,
    setBeastTags,
    setMapDesc,
    setMapFile,
    setMapName,
    setMapSystem,
    uploadBeast,
    uploadMap,
  } = useStartWizard();

  return (
    <>
                  {/* 地图管理 */}
                  <div className="border-t border-gray-200 pt-4 space-y-3">
                    <p className="text-xs font-bold text-ink-800">通用地区地图（所有剧本可用）</p>
                    <p className="text-[10px] text-ink-400">这里只管理通用图鉴；剧本专属地点请在对局内由 DM 自建，或导入剧本时自动生成。</p>
                    <div className="grid md:grid-cols-2 gap-3">
                      <div className="bg-gray-50 rounded-lg p-3 border border-gray-200 space-y-2">
                        <input value={mapName} onChange={(e: any) =>setMapName(e.target.value)} placeholder="地图名称" className="input-field text-xs" />
                        <input value={mapDesc} onChange={(e: any) =>setMapDesc(e.target.value)} placeholder="地图简介" className="input-field text-xs" />
                        <select value={mapSystem} onChange={(e: any) =>setMapSystem(e.target.value as GameSystem)} className="input-field text-xs">
                          {GAME_SYSTEM_OPTIONS.map((o: any) =><option key={o.id} value={o.id}>{o.label}</option>)}
                        </select>
                        <input type="file" accept=".png,.jpg,.jpeg,.webp" onChange={(e: any) =>setMapFile(e.target.files?.[0]||null)} className="block w-full text-xs" />
                        <button onClick={()=>mapFile&&uploadMap(mapFile)} disabled={mediaBusy||!mapFile} className="w-full py-2 bg-indigo-50 border border-indigo-200 hover:bg-indigo-100 text-indigo-700 rounded-lg text-xs font-medium disabled:opacity-50">上传地图</button>
                      </div>
                      <div className="space-y-1.5 max-h-48 overflow-y-auto">
                        {maps.length===0&&<p className="text-xs text-ink-400">暂无地图</p>}
                        {maps.map((m: any) =>(
                          <div key={m.id} className="flex items-center gap-2 bg-white rounded-lg p-2 border border-gray-200">
                            {m.image_path&&<img src={m.image_path} alt={m.name} className="w-10 h-10 object-cover rounded border" />}
                            <div className="min-w-0 flex-1"><p className="text-xs font-medium truncate">{m.name}</p><p className="text-[9px] text-ink-400">{m.locations.length} 个地点</p></div>
                            {!String(m.id).startsWith('kb-') && <button onClick={()=>deleteMap(m.id)} className="text-[10px] text-red-700">删除</button>}
                          </div>
                        ))}
                      </div>
                    </div>
                  </div>

                  {/* 生物图鉴 */}
                  <div className="border-t border-gray-200 pt-4 space-y-3">
                    <p className="text-xs font-bold text-ink-800">通用生物图鉴（所有剧本可用）</p>
                    <p className="text-[10px] text-ink-400">这里只管理通用图鉴；剧本专属生物请在对局内由 DM 自建，避免覆盖通用条目。</p>
                    <div className="grid md:grid-cols-2 gap-3">
                      <div className="bg-gray-50 rounded-lg p-3 border border-gray-200 space-y-2">
                        <input value={beastName} onChange={(e: any) =>setBeastName(e.target.value)} placeholder="生物名称" className="input-field text-xs" />
                        <select value={beastSystem} onChange={(e: any) =>setBeastSystem(e.target.value as GameSystem)} className="input-field text-xs">
                          {GAME_SYSTEM_OPTIONS.map((o: any) =><option key={o.id} value={o.id}>{o.label}</option>)}
                        </select>
                        <textarea value={beastDesc} onChange={(e: any) =>setBeastDesc(e.target.value)} placeholder="生物描述" rows={2} className="input-field resize-none text-xs" />
                        <input value={beastStats} onChange={(e: any) =>setBeastStats(e.target.value)} placeholder={'属性JSON，如 {"HP":20,"AC":14}'} className="input-field font-mono text-xs" />
                        <input value={beastTags} onChange={(e: any) =>setBeastTags(e.target.value)} placeholder="标签，逗号分隔" className="input-field text-xs" />
                        <input type="file" accept=".png,.jpg,.jpeg,.webp" onChange={(e: any) =>setBeastFile(e.target.files?.[0]||null)} className="block w-full text-xs" />
                        <button onClick={()=>beastFile&&uploadBeast(beastFile)} disabled={mediaBusy||!beastFile} className="w-full py-2 bg-emerald-50 border border-emerald-200 hover:bg-emerald-100 text-emerald-700 rounded-lg text-xs font-medium disabled:opacity-50">上传生物</button>
                      </div>
                      <div className="space-y-1.5 max-h-48 overflow-y-auto">
                        {bestiary.length===0&&<p className="text-xs text-ink-400">暂无生物</p>}
                        {bestiary.map((b: any) =>(
                          <div key={b.id} className="flex items-center gap-2 bg-white rounded-lg p-2 border border-gray-200">
                            {b.image_path&&<img src={b.image_path} alt={b.name} className="w-10 h-10 object-cover rounded border" />}
                            <div className="min-w-0 flex-1"><p className="text-xs font-medium truncate">{b.name}</p><p className="text-[9px] text-ink-400">{b.system} · {Object.keys(b.stats||{}).length} 项属性</p></div>
                            {!String(b.id).startsWith('kb-') && <button onClick={()=>deleteBeast(b.id)} className="text-[10px] text-red-700">删除</button>}
                          </div>
                        ))}
                      </div>
                    </div>
                  </div>

    </>
  );
}
