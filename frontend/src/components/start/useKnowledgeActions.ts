import { useEffect, useRef, useState } from 'react';
import { createExtActions } from './knowledge/extActions';
import { createKbActions } from './knowledge/kbActions';

/** 知识库与扩展包：状态 + 操作（添加/上传/取消/删除/播种/LLM 处理，扩展包新增与生成）。
 *
 * 状态从 StartScreen 搬进本 hook：这组 state 只服务知识库步骤（外加开局时的
 * `extension_ids`）。留在页面里会让 StartScreen 一直背着 23 个 state、3 个 ref
 * 与 38 个 deps；搬进来后只留跨切面输入。
 */
export interface UseKnowledgeActionsDeps {
  username: string;
  apiKey: string;
  baseUrl: string;
  modelName: string;
  scenarioId: string;
  splitter: 'semantic' | 'llm' | 'recursive';
}

export function useKnowledgeActions(deps: UseKnowledgeActionsDeps) {
  const { username, apiKey, baseUrl, modelName, scenarioId, splitter } = deps;

  // ── 知识库 ──
  const [kbDocs,setKbDocs]=useState<Array<{id:string;title:string;source:string;system:string;tags:string[];chunk_count:number;created_at:string}>>([]);
  const [kbTitle,setKbTitle]=useState('');
  const [kbContent,setKbContent]=useState('');
  const [kbSystem,setKbSystem]=useState<'dnd5e'|'dnd4e'|'coc'|'custom'>('custom');
  const [kbTags,setKbTags]=useState('');
  const [kbBusy,setKbBusy]=useState(false);
  const [kbLlmBusy,setKbLlmBusy]=useState(false);
  const [kbErr,setKbErr]=useState('');
  const [kbUploadFile,setKbUploadFile]=useState<File|null>(null);
  const [kbProgress,setKbProgress]=useState<{phase:string;message:string;progress:number;current:number;total:number}|null>(null);
  const kbEsRef=useRef<EventSource|null>(null);
  const kbStopRef=useRef<(()=>void)|null>(null);
  const kbTaskIdRef=useRef('');

  // ── 扩展包 ──
  const [extList,setExtList]=useState<Array<{id:string;name:string;description:string;system:string;tags:string[];source:string;created_at:string}>>([]);
  const [extName,setExtName]=useState('');
  const [extDesc,setExtDesc]=useState('');
  const [extContent,setExtContent]=useState('');
  const [extSystem,setExtSystem]=useState<'dnd5e'|'dnd4e'|'coc'|'custom'>('custom');
  const [extTags,setExtTags]=useState('');
  const [extGenDesc,setExtGenDesc]=useState('');
  const [extBusy,setExtBusy]=useState(false);
  const [extErr,setExtErr]=useState('');
  const [activeExtIds,setActiveExtIds]=useState<string[]>([]);

  const kbActions = createKbActions({
    username, apiKey, baseUrl, modelName, scenarioId, splitter,
    kbTitle, kbContent, kbSystem, kbTags,
    setKbDocs, setKbTitle, setKbContent, setKbTags, setKbBusy, setKbLlmBusy,
    setKbErr, setKbUploadFile, setKbProgress,
    kbEsRef, kbStopRef, kbTaskIdRef,
  });
  const {
    loadKb, addKbNote, uploadKb, cancelKbUpload, deleteKb, seedKb, llmProcessKb,
  } = kbActions;
  const extActions = createExtActions({
    username, apiKey, baseUrl, modelName,
    extName, extDesc, extContent, extSystem, extTags, extGenDesc,
    setExtList, setExtName, setExtDesc, setExtContent, setExtTags, setExtGenDesc,
    setExtBusy, setExtErr, setActiveExtIds,
  });
  const { loadExts, addExt, genExt, deleteExt } = extActions;



  // 挂载时各拉一次（行为与拆分前 StartScreen 的挂载 effect 一致）
  useEffect(() => { loadKb(); loadExts(); }, []);   // eslint-disable-line react-hooks/exhaustive-deps

  return {
    // 知识库状态
    kbDocs, setKbDocs, kbTitle, setKbTitle, kbContent, setKbContent, kbSystem, setKbSystem,
    kbTags, setKbTags, kbBusy, kbLlmBusy, kbErr, kbUploadFile, setKbUploadFile, kbProgress,
    // 扩展包状态
    extList, setExtList, extName, setExtName, extDesc, setExtDesc, extContent, setExtContent,
    extSystem, setExtSystem, extTags, setExtTags, extGenDesc, setExtGenDesc, extBusy, extErr,
    activeExtIds, setActiveExtIds,
    // 操作
    loadKb, addKbNote, uploadKb, cancelKbUpload, deleteKb, seedKb, llmProcessKb,
    loadExts, addExt, genExt, deleteExt,
  };
}
