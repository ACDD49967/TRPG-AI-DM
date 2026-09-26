/** 知识库文字备注与文件上传（从 KnowledgeStep 拆出；值经 useStartWizard 取用）。 */
import { useStartWizard } from '../StartWizardContext';
import { GAME_SYSTEM_OPTIONS, type GameSystem } from '../../../gameSystems';

export default function KbIngestSection() {
  const {
    addKbNote,
    bgeBusy,
    bgeDownloaded,
    bgeProgress,
    bgeRerankerDownloaded,
    bgeStatus,
    cancelKbUpload,
    downloadBge,
    kbBusy,
    kbContent,
    kbProgress,
    kbSystem,
    kbTags,
    kbTitle,
    kbUploadFile,
    setKbContent,
    setKbSystem,
    setKbTags,
    setKbTitle,
    setKbUploadFile,
    setSplitter,
    splitter,
    uploadKb,
  } = useStartWizard();

  return (
    <>
                    {/* 添加文字备注 */}
                    <div className="bg-gray-50 rounded-lg p-3 border border-gray-200 space-y-2">
                      <p className="text-xs font-medium text-ink-700">添加文字备注</p>
                      <input value={kbTitle} onChange={(e: any) =>setKbTitle(e.target.value)} placeholder="标题（可选）" className="input-field text-xs" />
                      <select value={kbSystem} onChange={(e: any) =>setKbSystem(e.target.value as GameSystem)} className="input-field text-xs">
                        {GAME_SYSTEM_OPTIONS.map((o: any) =><option key={o.id} value={o.id}>{o.label}</option>)}
                      </select>
                      <textarea value={kbContent} onChange={(e: any) =>setKbContent(e.target.value)} placeholder="输入规则、设定、备注..." rows={4} className="input-field resize-none text-xs" />
                      <input value={kbTags} onChange={(e: any) =>setKbTags(e.target.value)} placeholder="标签，用逗号分隔" className="input-field text-xs" />
                      <button onClick={addKbNote} disabled={kbBusy || !kbContent.trim()} className="w-full py-2 bg-indigo-50 border border-indigo-200 hover:bg-indigo-100 text-indigo-700 rounded-lg text-xs font-medium disabled:opacity-50">保存到知识库</button>
                    </div>

                    {/* 上传文件 */}
                    <div className="bg-gray-50 rounded-lg p-3 border border-gray-200 space-y-2">
                      <p className="text-xs font-medium text-ink-700">上传 PDF/DOCX/TXT/MD</p>
                      <input
                        type="file"
                        accept=".txt,.md,.markdown,.pdf,.doc,.docx,.png,.jpg,.jpeg,.webp,.gif,.bmp"
                        onChange={(e: any) =>setKbUploadFile(e.target.files?.[0]||null)}
                        className="block w-full text-xs text-ink-500 file:mr-3 file:py-2 file:px-3 file:rounded-lg file:border-0 file:bg-indigo-50 file:text-indigo-700 file:text-xs file:font-medium"
                      />
                      <input value={kbTitle} onChange={(e: any) =>setKbTitle(e.target.value)} placeholder="标题（默认文件名）" className="input-field text-xs" />
                      <select value={kbSystem} onChange={(e: any) =>setKbSystem(e.target.value as GameSystem)} className="input-field text-xs">
                        {GAME_SYSTEM_OPTIONS.map((o: any) =><option key={o.id} value={o.id}>{o.label}</option>)}
                      </select>
                      <input value={kbTags} onChange={(e: any) =>setKbTags(e.target.value)} placeholder="标签，用逗号分隔" className="input-field text-xs" />
                      <div>
                        <label className="block text-[10px] text-ink-500 mb-1">切分方式</label>
                        <select value={splitter} onChange={(e: any) =>setSplitter(e.target.value as 'semantic'|'llm'|'recursive')} className="input-field text-xs">
                          <option value="recursive">递归切分</option>
                          <option value="semantic">语义切分</option>
                          <option value="llm">LLM 切分</option>
                        </select>
                      </div>
                      {!bgeDownloaded && (
                        <div className="pt-1 border-t border-gray-200 space-y-1.5">
                          <p className="text-[10px] font-medium text-ink-500">下载向量模型</p>
                          <button onClick={()=>downloadBge('embedding')} disabled={bgeBusy!==null} className="btn-secondary text-xs px-3 whitespace-nowrap">
                            {bgeBusy==='embedding' ? '下载中...' : '下载 BGE-M3'}
                          </button>
                          {bgeBusy==='embedding' && (
                            <div className="h-1.5 bg-gray-200 rounded-full overflow-hidden">
                              {bgeProgress!==null ? (
                                <div className="h-full bg-emerald-500 transition-all" style={{width:`${bgeProgress}%`}} />
                              ) : (
                                <div className="h-full bg-emerald-500 animate-pulse" style={{width:'100%'}} />
                              )}
                            </div>
                          )}
                        </div>
                      )}
                      {!bgeRerankerDownloaded && (
                        <div className="pt-1 border-t border-gray-200 space-y-1.5">
                          <p className="text-[10px] font-medium text-ink-500">可选重排模型</p>
                          <button onClick={()=>downloadBge('reranker')} disabled={bgeBusy!==null} className="btn-secondary text-xs px-3 whitespace-nowrap">
                            {bgeBusy==='reranker' ? '下载中...' : '下载 BGE-Reranker-base'}
                          </button>
                          {bgeBusy==='reranker' && (
                            <div className="h-1.5 bg-gray-200 rounded-full overflow-hidden">
                              <div className="h-full bg-emerald-500 animate-pulse" style={{width:'100%'}} />
                            </div>
                          )}
                        </div>
                      )}
                      {bgeStatus&&<p className={`text-[10px] ${bgeStatus.startsWith('下载失败')?'text-red-700':'text-emerald-600'}`}>{bgeStatus}</p>}
                      <button onClick={()=>kbUploadFile&&uploadKb(kbUploadFile)} disabled={kbBusy || !kbUploadFile} className="w-full py-2 bg-emerald-50 border border-emerald-200 hover:bg-emerald-100 text-emerald-700 rounded-lg text-xs font-medium disabled:opacity-50">
                        {kbBusy?'处理中...':'上传到知识库'}
                      </button>
                      {kbProgress&&(
                        <div className="space-y-1">
                          <div className="h-1.5 bg-gray-200 rounded-full overflow-hidden">
                            <div className="h-full bg-emerald-500 transition-all" style={{width:`${Math.max(2,Math.min(100,kbProgress.progress||5))}%`}} />
                          </div>
                          <p className="text-[10px] text-ink-500">
                            {kbProgress.phase}：{kbProgress.message||'处理中'}
                            {kbProgress.total>0&&(` (${kbProgress.current}/${kbProgress.total})`)}
                          </p>
                          {kbBusy&&<button onClick={cancelKbUpload} className="w-full py-1.5 bg-red-50 border border-red-200 text-red-600 rounded-lg text-[10px] font-medium hover:bg-red-100">取消上传</button>}
                        </div>
                      )}
                    </div>

    </>
  );
}
