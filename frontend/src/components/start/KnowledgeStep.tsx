import { useStartWizard } from './StartWizardContext';
import KbIngestSection from './knowledge/KbIngestSection';
import VectorModelSection from './knowledge/VectorModelSection';
import ExtensionsSection from './knowledge/ExtensionsSection';
import MediaSection from './knowledge/MediaSection';
/** 知识库步骤：备注/文件上传、模型与向量模式、扩展包/地图/图鉴管理。
 *
 * 从 StartScreen 拆出：依赖项通过 props 显式传入，行为与拆分前一致。
 */

export default function KnowledgeStep() {
  const props = useStartWizard();
  const {
    activeExtIds,
    addExt,
    addKbNote,
    beastDesc,
    beastFile,
    beastName,
    beastStats,
    beastSystem,
    beastTags,
    bestiary,
    bgeBusy,
    bgeDownloaded,
    bgeProgress,
    bgeRerankerDownloaded,
    bgeStatus,
    cancelKbUpload,
    deleteBeast,
    deleteExt,
    deleteKb,
    deleteMap,
    downloadBge,
    downloadSmall,
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
    kbBusy,
    kbContent,
    kbDocs,
    kbErr,
    kbLlmBusy,
    kbProgress,
    kbSystem,
    kbTags,
    kbTitle,
    kbUploadFile,
    llmProcessKb,
    loadExts,
    loadKb,
    mapDesc,
    mapFile,
    mapName,
    mapSystem,
    maps,
    mediaBusy,
    seedKb,
    setActiveExtIds,
    setBeastDesc,
    setBeastFile,
    setBeastName,
    setBeastStats,
    setBeastSystem,
    setBeastTags,
    setExtContent,
    setExtDesc,
    setExtGenDesc,
    setExtName,
    setExtSystem,
    setExtTags,
    setKbContent,
    setKbSystem,
    setKbTags,
    setKbTitle,
    setKbUploadFile,
    setMapDesc,
    setMapFile,
    setMapName,
    setMapSystem,
    setSmallDeclined,
    setSplitter,
    setVectorModeNow,
    smallBusy,
    smallDeclined,
    smallDownloaded,
    smallProgress,
    smallStatus,
    splitter,
    uploadBeast,
    uploadKb,
    username,
    uploadMap,
    vectorMode,
  } = props;

  return (
    <>
                <div className="space-y-5">
                  <div className="flex items-center justify-between">
                    <h2 className="text-lg font-bold text-ink-900">知识库 / RAG 设定库</h2>
                    <div className="flex items-center gap-2">
                      <button onClick={llmProcessKb} disabled={kbLlmBusy || kbBusy} className="text-[10px] px-2.5 py-1 rounded-lg border border-amber-200 bg-amber-50 text-amber-700 hover:bg-amber-100">
                        {kbLlmBusy ? 'LLM 处理中...' : 'LLM 智能切分与图鉴注入'}
                      </button>
                      <button onClick={seedKb} disabled={kbBusy} className="text-[10px] px-2.5 py-1 rounded-lg border border-indigo-200 bg-indigo-50 text-indigo-700 hover:bg-indigo-100">重置内置规则备注</button>
                    </div>
                  </div>

                  <div className="bg-indigo-50/40 rounded-lg p-3 border border-indigo-100">
                  </div>

                  <div className="grid md:grid-cols-2 gap-4">
                  <KbIngestSection />
                  <VectorModelSection />
                  <ExtensionsSection />
                  <MediaSection />
                </div>
                </div>
    </>
  );
}
