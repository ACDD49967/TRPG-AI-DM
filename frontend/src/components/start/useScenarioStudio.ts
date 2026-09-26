/**
 * 剧本工坊：世界大纲生成、剧本保存/读取/删除/更新、剧本文件导入与切分。
 *
 * 状态与返回值都在本 hook；两个长流程（世界生成、文件导入）的流式逻辑拆到
 * `scenarioActions`（含共用的 SSE 读取 `scenarioStream`），这里只做参数装配。
 */
import { useEffect, useRef, useState, type MutableRefObject } from 'react';
import type { GameSystem } from '../../gameSystems';
import { generateWorld, importScenarioFile } from './scenarioActions';
import { createScenarioCrud } from './scenario/scenarioCrud';
import { refreshScenarioList } from './scenarioStream';

type SavedScenario = {
  id: string; title: string; description: string; summary?: string;
  system?: string; tone: string; score: number; total_sessions: number;
  character_name?: string; race?: string; char_class?: string;
};
type ClassicScenario = {
  name: string; system: string; tone: string; summary: string; source: string; outline: string[];
};
type ScenarioOverrides = {
  world_outline?: string; summary?: string; custom_rules?: string;
  custom_classes?: string[]; custom_skills?: string[]; extra_attributes?: Record<string, string>;
};

export function useScenarioStudio({ username, apiKey, modelName, baseUrl, gameSystem,
                                    charName, rc, cc, thinkingStrength, setGameSystem, loadKbRef }: {
  username: string;
  apiKey: string;
  modelName: string;
  baseUrl: string;
  gameSystem: string;
  charName: string;
  rc: { name: string; traits?: string[] };
  cc: { name: string; profs?: string[] };
  thinkingStrength: string;
  setGameSystem: (v: GameSystem) => void;
  loadKbRef: MutableRefObject<(() => Promise<void>) | null>;
}) {
  const importAbortRef = useRef<AbortController|null>(null);

  const [worldDesc,setWorldDesc]=useState('');
  const [worldTone,setWorldTone]=useState('史诗奇幻');
  const [customTone,setCustomTone]=useState('');
  const [toneCustom,setToneCustom]=useState(false);
  const [customClassesText,setCustomClassesText]=useState('');
  const [customSkillsText,setCustomSkillsText]=useState('');
  const [extraAttributesText,setExtraAttributesText]=useState('');
  const [worldNote,setWorldNote]=useState('');
  const [referenceScript,setReferenceScript]=useState('');
  const [worldOutline,setWorldOutline]=useState('');
  const [worldScore,setWorldScore]=useState<number|null>(null);
  const [worldStateJson,setWorldStateJson]=useState('');
  const [scenarioId,setScenarioId]=useState('');
  const [worldGenBusy,setWorldGenBusy]=useState(false);
  const [worldGenErr,setWorldGenErr]=useState('');
  const [worldGenStage,setWorldGenStage]=useState(-1);
  const [worldGenDetail,setWorldGenDetail]=useState('');
  const [worldGenLive,setWorldGenLive]=useState('');
  const [savedScenarios,setSavedScenarios]=useState<SavedScenario[]>([]);
  const [classicScenarios,setClassicScenarios]=useState<ClassicScenario[]>([]);
  const [selectedScenario,setSelectedScenario]=useState('');
  const [showScenarioList,setShowScenarioList]=useState(false);
  const [scenarioText,setScenarioText]=useState('');

  const [scenarioSystem,setScenarioSystem]=useState<GameSystem>('dnd5e');
  const [customRules,setCustomRules]=useState('');

  const [splitter,setSplitter]=useState<'semantic'|'llm'|'recursive'>('recursive');

  const [chunkSize,setChunkSize]=useState(900);
  const [scenarioSummary,setScenarioSummary]=useState('');
  const [sourceChunks,setSourceChunks]=useState<string[]>([]);
  const [importBusy,setImportBusy]=useState(false);
  const [importProgress,setImportProgress]=useState(0);
  const [importStage,setImportStage]=useState('');
  const [importLive,setImportLive]=useState('');
  const [importErr,setImportErr]=useState('');
  const [importFileName,setImportFileName]=useState('');

  // 角色系统绑定剧本系统：切换规则系统时，清掉不匹配的已选剧本
  useEffect(()=>{
    if(!selectedScenario) return;
    const s = savedScenarios.find(x=>x.id===selectedScenario);
    if(s && s.system && s.system!==gameSystem){
      setSelectedScenario(''); setScenarioId('');
    }
  },[gameSystem, selectedScenario, savedScenarios]);

  const cancelImport=()=>{
    importAbortRef.current?.abort();
    setImportErr('已取消');
    setImportBusy(false);
    setImportProgress(0);
  };

  // 自定义职业/技能/额外属性的解析结果（原文存在本 hook 里，就地派生并导出）
  const customClasses = customClassesText.split(/[,，]/).map(s=>s.trim()).filter(Boolean);
  const customSkills = customSkillsText.split(/[,，]/).map(s=>s.trim()).filter(Boolean);
  const extraAttributes: Record<string,string> = {};
  extraAttributesText.split('\n').forEach(line=>{
    const idx = line.indexOf('=') >= 0 ? line.indexOf('=') : line.indexOf('：');
    if(idx>0) extraAttributes[line.slice(0,idx).trim()]=line.slice(idx+1).trim();
  });

  const { loadScenario, deleteScenario, updateScenario } = createScenarioCrud({
    username, savedScenarios, selectedScenario, scenarioId, scenarioSummary,
    worldOutline, customRules, customClasses, customSkills, extraAttributes,
    setWorldOutline, setWorldStateJson, setScenarioSummary, setSourceChunks,
    setCustomRules, setCustomClassesText, setCustomSkillsText, setExtraAttributesText,
    setScenarioSystem, setGameSystem, setScenarioId, setSelectedScenario,
    setShowScenarioList, setWorldScore, setSavedScenarios, setWorldGenErr,
  });

  const genWorld = () => generateWorld({
    username, apiKey, modelName, baseUrl, gameSystem, charName,
    raceName: rc.name, className: cc.name, thinkingStrength,
    worldDesc, worldTone, customRules, customClasses, customSkills, extraAttributes,
    setBusy: setWorldGenBusy, setError: setWorldGenErr, setStage: setWorldGenStage,
    setDetail: setWorldGenDetail, setLive: setWorldGenLive,
    setOutline: setWorldOutline, setScore: setWorldScore, setWorldStateJson,
    setSummary: setScenarioSummary, setScenarioSystem, setSourceChunks,
    setScenarioId, setSelectedScenario, setShowScenarioList,
    setSavedScenarios: (v) => setSavedScenarios(v as SavedScenario[]),
    updateScenario: (overrides, sid) => { void updateScenario(overrides as ScenarioOverrides, sid); },
    loadKb: () => { void loadKbRef.current?.(); },
  });

  const importScenario = (file: File) => importScenarioFile({
    username, apiKey, modelName, baseUrl, thinkingStrength, worldTone,
    splitter, chunkSize, customRules, customClasses, customSkills, extraAttributes,
    abortRef: importAbortRef,
    setBusy: setImportBusy, setProgress: setImportProgress, setStage: setImportStage,
    setLive: setImportLive, setImportError: setImportErr, setFileName: setImportFileName,
    setOutline: setWorldOutline, setScore: setWorldScore, setWorldStateJson,
    setScenarioId, setSummary: setScenarioSummary, setScenarioSystem, setGameSystem,
    setSourceChunks, setSelectedScenario, setShowScenarioList,
    setSavedScenarios: (v) => setSavedScenarios(v as SavedScenario[]),
    updateScenario: (overrides, sid) => { void updateScenario(overrides as ScenarioOverrides, sid); },
    loadKb: () => { void loadKbRef.current?.(); },
  }, file);

  return {
    worldDesc, setWorldDesc, worldTone, setWorldTone, customTone, setCustomTone,
    toneCustom, setToneCustom, worldNote, setWorldNote, referenceScript, setReferenceScript,
    worldOutline, setWorldOutline, worldScore, setWorldScore, worldStateJson, setWorldStateJson,
    scenarioId, setScenarioId, worldGenBusy, worldGenErr, worldGenStage, worldGenDetail,
    worldGenLive, savedScenarios, setSavedScenarios, classicScenarios, setClassicScenarios, selectedScenario,
    setSelectedScenario, showScenarioList, setShowScenarioList, scenarioText, setScenarioText,
    scenarioSystem, setScenarioSystem, customRules, setCustomRules, splitter, setSplitter,
    chunkSize, setChunkSize, scenarioSummary, setScenarioSummary, sourceChunks, setSourceChunks,
    customClassesText, setCustomClassesText, customSkillsText, setCustomSkillsText,
    extraAttributesText, setExtraAttributesText,
    customClasses, customSkills, extraAttributes,
    importBusy, importProgress, importStage, importLive, importErr, importFileName,
    genWorld, loadScenario, deleteScenario, updateScenario, importScenario, cancelImport,
  };
}
