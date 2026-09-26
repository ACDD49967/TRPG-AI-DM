/** 角色创建 —— localStorage持久化 + URL配置 + 技能熟练 + 特长 */
import { useMediaActions } from './start/useMediaActions';
import { useCharacterCardActions } from './start/useCharacterCardActions';
import { useSaveActions } from './start/useSaveActions';
import { useKnowledgeActions } from './start/useKnowledgeActions';
import StartWizardShell from './start/StartWizardShell';

import { useState, useEffect, useRef } from 'react';
import { useGameStore } from '../store/gameStore';
import { useToastStore } from '../store/toastStore';
import { StartWizardProvider, type StartWizardValue } from './start/StartWizardContext';
import { useCharacterDraft } from './start/useCharacterDraft';
import { useScenarioStudio } from './start/useScenarioStudio';
import { useStartActions } from './start/useStartActions';
import { useStartBootstrap, type CharCardRow, type SaveRow } from './start/useStartBootstrap';
import { useModelSettings } from './start/useModelSettings';
import { type GameSystem } from '../gameSystems';

import { loadConfig } from '../data/dndData';

// ═══════════════════════ 组件 ═══════════════════════

export default function StartScreen({ authUsername, onLogout }: { authUsername?: string; onLogout?: () => void }){
  const [step,setStep]=useState(1);
  const cfg=loadConfig();

  // API 连接 / 模型 / 向量模式 / 模型下载整体搬进 hook（含 localStorage 持久化）
  const settings = useModelSettings();
  const {
    apiKey, setApiKey, modelName, setModelName, baseUrl, setBaseUrl,
    showKey, setShowKey, provider, setProvider, modelOptions, modelFetchBusy,
    modelFetchErr, modelInputMode, setModelInputMode, thinkingStrength, setThinkingStrength, endpointPresets,
    endpointName, setEndpointName, vectorMode, bgeBusy, bgeStatus, bgeProgress,
    bgeDownloaded, bgeRerankerDownloaded, smallBusy, smallStatus, smallProgress, smallDownloaded,
    smallDeclined, setSmallDeclined, applyProvider, saveEndpointPreset, deleteEndpointPreset, fetchModels,
    setVectorModeNow, downloadBge, downloadSmall,
  } = settings;
  const [scenarioMode,setScenarioMode]=useState<'existing'|'split'|'generate'>('generate');
  const [username,setUsername]=useState(authUsername || cfg.username);

  // 登录账号是身份唯一来源：账号切换时同步用户名。
  useEffect(()=>{
    if(authUsername && authUsername!==username) setUsername(authUsername);
  },[authUsername]);

  // 法术池与创建期法术选择

  // 世界
  const [playMode,setPlayMode]=useState<'lite'|'deep'>('deep');
  const [gameSystem,setGameSystem]=useState<GameSystem>('dnd5e');


  const media = useMediaActions({ username });
  const {
    maps, mapName, setMapName, mapDesc, setMapDesc, mapSystem,
    setMapSystem, mapFile, setMapFile, bestiary, beastName, setBeastName,
    beastSystem, setBeastSystem, beastDesc, setBeastDesc, beastStats, setBeastStats,
    beastTags, setBeastTags, beastFile, setBeastFile, characterImage, setCharacterImage,
    mediaBusy, mediaErr, uploadMap, deleteMap, uploadBeast, deleteBeast,
    uploadCharacterImage,
  } = media;

  const [saves,setSaves]=useState<SaveRow[]>([]);
  const [saveLabel,setSaveLabel]=useState('');
  const [charCards,setCharCards]=useState<CharCardRow[]>([]);
  const [charCardName,setCharCardName]=useState('');

  const [showRulebook,setShowRulebook]=useState(false);

  const [loading,setLoading]=useState(false);
  const [error,setError]=useState('');
  const setSession=useGameStore(s=>s.setSession);
  const updateStatus=useGameStore(s=>s.updateStatus);
  const showToast=useToastStore(s=>s.showToast);

  const draft = useCharacterDraft({
    username, gameSystem: gameSystem || 'dnd5e', apiKey, modelName, baseUrl, setError,
  });
  const {
    charName, setCharName, gender, setGender, race, setRace,
    charClass, setCharClass, attrs, setAttrs, attrMode, setAttrMode,
    backstoryText, setBackstoryText, aiGen, setAiGen, aiBusy, setAiBusy,
    aiErr, setAiErr, skillPicks, setSkillPicks, spellPool, spellPicks,
    setSpellPicks, spellPoolBusy, cocAttrs, setCocAttrs, occupation, setOccupation,
    cocSkillPicks, setCocSkillPicks, cocOccInc, setCocOccInc, cocPerInc, setCocPerInc,
    cocLuck, setCocLuck, customAttrs, setCustomAttrs, pb, rm,
    finalAttrs, rc, cc, d5Derived, d4Derived, cocOccPool,
    cocPerPool, cocOccRemain, cocPerRemain, cocSkillValues, cantripQuota, spellQuota,
    availableCantrips, availableLevel1, selectedCantrips, selectedLevel1, toggleSpell, inc,
    dec, incCocOcc, decCocOcc, incCocPer, decCocPer, toggleSkill,
  } = draft;


  const saveActions = useSaveActions({ apiKey, baseUrl, modelName, saves, setError, setSaves, setSession, updateStatus, username });
  const {
    loadSaves,
    loadSaveGame,
    deleteSave,
  } = saveActions;

  /** 剧本导入后要刷新知识库列表；知识库 hook 在下面才调用，用 ref 惰性取用 */
  const loadKbRef = useRef<(() => Promise<void>) | null>(null);
  const scenario = useScenarioStudio({
    username, apiKey, modelName, baseUrl, gameSystem: gameSystem || 'dnd5e',
    charName, rc, cc, thinkingStrength, setGameSystem, loadKbRef,
  });
  const {
    worldDesc, setWorldDesc, worldTone, setWorldTone, customTone, setCustomTone,
    toneCustom, setToneCustom, worldNote, setWorldNote, referenceScript, setReferenceScript,
    worldOutline, setWorldOutline, worldScore, setWorldScore, worldStateJson, setWorldStateJson,
    scenarioId, setScenarioId, worldGenBusy, worldGenErr, worldGenStage, worldGenDetail,
    worldGenLive, savedScenarios, setSavedScenarios, classicScenarios, setClassicScenarios, selectedScenario,
    setSelectedScenario, showScenarioList, setShowScenarioList, scenarioText, setScenarioText, scenarioSystem,
    setScenarioSystem, customRules, setCustomRules, splitter, setSplitter, chunkSize,
    setChunkSize, scenarioSummary, setScenarioSummary, sourceChunks, setSourceChunks, importBusy,
    customClassesText, setCustomClassesText, customSkillsText, setCustomSkillsText, extraAttributesText, setExtraAttributesText,
    customClasses, customSkills, extraAttributes, importProgress, importStage, importLive,
    importErr, importFileName, genWorld, loadScenario, deleteScenario, updateScenario,
    importScenario, cancelImport,
  } = scenario;

  const knowledge = useKnowledgeActions({ username, apiKey, baseUrl, modelName, scenarioId, splitter });
  const {
    kbDocs, kbTitle, setKbTitle, kbContent, setKbContent, kbSystem,
    setKbSystem, kbTags, setKbTags, kbBusy, kbLlmBusy, kbErr,
    kbUploadFile, setKbUploadFile, kbProgress, extList, extName, setExtName,
    extDesc, setExtDesc, extContent, setExtContent, extSystem, setExtSystem,
    extTags, setExtTags, extGenDesc, setExtGenDesc, extBusy, extErr,
    activeExtIds, setActiveExtIds, loadKb, addKbNote, uploadKb, cancelKbUpload,
    deleteKb, seedKb, llmProcessKb, loadExts, addExt, genExt,
    deleteExt,
  } = knowledge;
  loadKbRef.current = loadKb;
  useStartBootstrap({
    username, step, apiKey, modelName, baseUrl,
    error, aiErr, mediaErr, kbErr, extErr, worldGenErr, importErr,
    setSaves, setCharCards, setSavedScenarios, setClassicScenarios, showToast,
  });

  // ── 法术选择：按职业/种族配额 ──
  const cardActions = useCharacterCardActions({ aiGen, backstoryText, cc, charCardName, charCards, charName, characterImage, cocLuck, cocOccInc, cocPerInc, cocSkillPicks, cocSkillValues, customClasses, customRules, customSkills, extraAttributes, finalAttrs, gameSystem, gender, occupation, race, rc, setAiGen, setAttrs, setBackstoryText, setCharCardName, setCharCards, setCharClass, setCharName, setCharacterImage, setCocAttrs, setCocLuck, setCocOccInc, setCocPerInc, setCocSkillPicks, setCustomAttrs, setCustomClassesText, setCustomRules, setCustomSkillsText, setError, setExtraAttributesText, setGameSystem, setGender, setRace, setSkillPicks, setSpellPicks, skillPicks, spellPicks, username });
  const {
    saveCharCard,
    loadCharCard,
    deleteCharCard,
  } = cardActions;
  // AI 生成角色/背景 与 开始冒险 两个页面级动作已拆到 useStartActions
  const { callAI, start } = useStartActions({
    apiKey, attrs, aiGen, backstoryText, baseUrl, cc, charName, characterImage,
    cocAttrs, cocLuck, cocSkillPicks, cocSkillValues, customClasses, customRules,
    customSkills, extraAttributes, finalAttrs, gameSystem, gender, modelName,
    occupation, playMode, rc, scenarioId, scenarioSummary, scenarioText,
    referenceScript, skillPicks, spellPicks, thinkingStrength, username,
    worldOutline, worldStateJson, activeExtIds, updateScenario,
    setAiBusy, setAiErr, setAiGen, setError, setLoading,
  });

  // ═══════════════════════ 渲染 ═══════════════════════

  /** 步骤组件统一从 context 取值：聚合各 hook 返回值与本页局部状态 */
  const wizard = {
    ...settings, ...draft, ...scenario, ...media, ...knowledge, ...saveActions, ...cardActions,
    step, setStep, scenarioMode, setScenarioMode, username, setUsername, playMode, setPlayMode,
    gameSystem, setGameSystem, showRulebook, setShowRulebook, loading, error, setError, start,
    authUsername, onLogout,
    // 仍留在本页的列表/表单状态（存档与角色卡库），步骤组件也要用
    saves, setSaves, saveLabel, setSaveLabel, charCards, setCharCards, charCardName, setCharCardName,
    callAI,
  } satisfies StartWizardValue;

  return(
    <StartWizardProvider value={wizard}>
      <StartWizardShell />
    </StartWizardProvider>
  );
}
