/** 本体切分导入：上传、切分方式与进度/取消（从 ScenarioStep 拆出；值经 useStartWizard 取用）。 */
import { useStartWizard } from '../StartWizardContext';

export default function ScenarioSplitImport() {
  const { scenarioMode, importScenario, importFileName, splitter, setSplitter, chunkSize,
    setChunkSize, importBusy, importProgress, importStage, cancelImport, importLive, importErr,
  } = useStartWizard();

  return (
    <>
      {scenarioMode==='split'&&(
      <div className="bg-gray-50 rounded-lg p-3 border border-gray-200 space-y-3">
        <div>
          <label className="block text-xs font-medium text-ink-600 mb-1">上传剧本文件</label>
          <input
            type="file"
            accept=".txt,.md,.markdown,.pdf,.doc,.docx,.png,.jpg,.jpeg,.webp,.gif,.bmp"
            onChange={(e: any) =>{
              const f=e.target.files?.[0];
              if(f)importScenario(f);
              e.target.value='';
            }}
            className="block w-full text-xs text-ink-500 file:mr-3 file:py-2 file:px-3 file:rounded-lg file:border-0 file:bg-indigo-50 file:text-indigo-700 file:text-xs file:font-medium hover:file:bg-indigo-100"
          />
          {importFileName&&<p className="text-[10px] text-ink-400 mt-1">已选择: {importFileName}</p>}
        </div>

        <div className="grid grid-cols-2 gap-3">
          <div>
            <label className="block text-xs font-medium text-ink-600 mb-1">切分方式</label>
            <select value={splitter} onChange={(e: any) =>setSplitter(e.target.value as 'semantic'|'llm'|'recursive')} className="input-field">
              <option value="recursive">递归切分</option>
              <option value="semantic">语义切分</option>
              <option value="llm">LLM 切分</option>
            </select>
          </div>
          <div>
            <label className="block text-xs font-medium text-ink-600 mb-1">单块字数</label>
            <input type="number" min={200} max={4000} step={100} value={chunkSize} onChange={(e: any) =>setChunkSize(Number(e.target.value)||900)} className="input-field" />
          </div>
        </div>

        {importBusy&&(
          <div className="mt-2">
            <p className="text-xs text-indigo-600 animate-pulse">正在读取、切分并生成剧本（需要多次AI调用）...</p>
            <div className="mt-1 h-1.5 bg-gray-200 rounded-full overflow-hidden">
              <div className="h-full bg-indigo-500 rounded-full transition-all duration-500" style={{width:`${importProgress}%`}} />
            </div>
            <p className="text-[9px] text-ink-400 mt-0.5">
              {importProgress}%{importStage?` · ${importStage}`:''}
            </p>
            {importProgress<=8&&splitter==='llm'&&(
              <p className="text-[9px] text-ink-400 mt-0.5">
                选择「LLM 切分」时会逐段调用模型划分语义片段，长剧本可能需要几分钟，可随时取消。
              </p>
            )}
            <button onClick={cancelImport} className="mt-1 text-[10px] px-2 py-1 rounded border border-red-200 bg-red-50 text-red-600 hover:bg-red-100">取消导入</button>
            {importLive && <pre className="text-[9px] text-ink-500 bg-white rounded p-2 mt-1 max-h-24 overflow-y-auto whitespace-pre-wrap">{importLive}</pre>}
          </div>
        )}
        {importErr&&<p className="text-red-700 text-xs">{importErr}</p>}
      </div>
      )}
    </>
  );
}
