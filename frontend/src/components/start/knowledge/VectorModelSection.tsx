/** 基底模型安装确认与向量检索模式（从 KnowledgeStep 拆出；值经 useStartWizard 取用）。 */
import { useStartWizard } from '../StartWizardContext';
import { GAME_SYSTEM_LABELS, type GameSystem } from '../../../gameSystems';
import InlineEdit from '../../ui/InlineEdit';

export default function VectorModelSection() {
  const {
    bgeDownloaded,
    deleteKb,
    downloadSmall,
    kbDocs,
    kbErr,
    loadKb,
    setSmallDeclined,
    setVectorModeNow,
    smallBusy,
    smallDeclined,
    smallDownloaded,
    smallProgress,
    smallStatus,
    username,
    vectorMode,
  } = useStartWizard();

  return (
    <>
                  {/* 基底模型安装确认：进入 setup 后运行时确认是否下载，避免静默占用磁盘/内存 */}
                  {!smallDownloaded && !bgeDownloaded && !smallDeclined && !smallBusy && (
                    <div className="bg-amber-50 border border-amber-200 rounded-lg p-3 space-y-2">
                      <p className="text-xs font-medium text-amber-800">检测到尚未安装基底模型</p>
                      <p className="text-[10px] text-amber-700">轻量中文向量模型 + 重排模型约占用 1GB+ 磁盘空间，运行时还会占用一定内存。是否现在下载？</p>
                      <div className="flex gap-2">
                        <button onClick={downloadSmall} className="text-xs px-3 py-1.5 bg-amber-500 text-white rounded-lg hover:bg-amber-600">确认下载</button>
                        <button onClick={()=>setSmallDeclined(true)} className="text-xs px-3 py-1.5 bg-white text-ink-500 rounded-lg border border-gray-200 hover:bg-gray-50">暂不</button>
                      </div>
                    </div>
                  )}
                  {smallBusy && (
                    <div className="bg-sky-50 border border-sky-200 rounded-lg p-3 space-y-2">
                      <p className="text-xs font-medium text-sky-700">正在下载基底模型...</p>
                      <div className="h-1.5 bg-gray-200 rounded-full overflow-hidden">
                        {smallProgress !== null ? (
                          <div className="h-full bg-sky-500 transition-all" style={{width:`${smallProgress}%`}} />
                        ) : (
                          <div className="h-full bg-sky-500 animate-pulse" style={{width:'100%'}} />
                        )}
                      </div>
                      {smallStatus && <p className="text-[10px] text-sky-700">{smallStatus}</p>}
                    </div>
                  )}

                  {/* 向量检索模式：小模型为固定基底，BGE 下载后自动替换 */}
                  <div className="bg-white rounded-lg p-3 border border-gray-200 space-y-2">
                    <p className="text-xs font-medium text-ink-700">向量检索模式</p>
                    <div className="flex flex-wrap gap-2">
                      <button onClick={()=>setVectorModeNow('local')} className={`text-xs px-3 py-1.5 rounded-lg border transition-all ${vectorMode==='local'?'border-indigo-400 bg-indigo-50 text-indigo-700':'border-gray-200 bg-white text-ink-500 hover:border-gray-300'}`}>基底</button>
                      <button onClick={()=>setVectorModeNow('bge')} className={`text-xs px-3 py-1.5 rounded-lg border transition-all ${vectorMode==='bge'?'border-emerald-400 bg-emerald-50 text-emerald-700':'border-gray-200 bg-white text-ink-500 hover:border-gray-300'}`} disabled={!bgeDownloaded}>BGE</button>
                    </div>
                  </div>

                  {kbErr&&<p className="text-red-700 text-xs">{kbErr}</p>}

                  <div className="space-y-1.5">
                    <p className="text-xs font-medium text-ink-700">已有知识条目（{kbDocs.length}）</p>
                    {kbDocs.length===0&&<p className="text-xs text-ink-400">暂无条目，点击上方“重置内置规则备注”或添加内容。</p>}
                    {kbDocs.map((d: any) =>(
                      <div key={d.id} className="flex items-center justify-between bg-white rounded-lg p-2.5 border border-gray-200">
                        <div className="min-w-0">
                          <p className="text-xs font-medium text-ink-800 truncate">{d.title}</p>
                          <p className="text-[10px] text-ink-500">{(GAME_SYSTEM_LABELS as Record<string, string>)[(d.system as GameSystem)||'custom']} · {d.source} · {d.chunk_count} 块 · {d.tags.join(' / ')||'无标签'}</p>
                        </div>
                        <div className="flex items-center gap-1 shrink-0">
                          <InlineEdit
                            label="编辑知识条目"
                            fields={[{ key: 'title', label: '标题', value: d.title || '' }]}
                            onSave={async (values: Record<string, any>) => {
                              const title = (values.title || '').trim();
                              if (!title) return;
                              const response = await fetch(
                                `/api/knowledge/${encodeURIComponent(d.id)}?username=${encodeURIComponent(username || 'default')}`,
                                {
                                  method: 'PUT',
                                  headers: { 'Content-Type': 'application/json' },
                                  body: JSON.stringify({ title }),
                                });
                              if (!response.ok) return;
                              await loadKb?.();
                            }}
                          />
                          <button onClick={()=>deleteKb(d.id)} className="text-[10px] text-red-700 hover:text-red-700 px-2 py-1">删除</button>
                        </div>
                      </div>
                    ))}
                  </div>

    </>
  );
}
