/** 角色创建 —— localStorage持久化 + URL配置 + 技能熟练 + 特长 */

import { useState, useMemo, useCallback, useEffect } from 'react';
import { useGameStore } from '../store/gameStore';
import RulebookModal from './RulebookModal';
import {
  COC_ATTRIBUTES,
  COC_OCCUPATIONS,
  COC_SKILLS,
  CUSTOM_ATTRIBUTES,
  DND4_CLASSES,
  GAME_SYSTEM_LABELS,
  GAME_SYSTEM_OPTIONS,
  GAME_SYSTEM_SHORT,
  getDnd4Derived,
  getDnd5Derived,
  rollCocAttributes,
  rollCocLuck,
  rollDndAttributes,
  type GameSystem,
} from '../gameSystems';

const COST: Record<number,number>={8:0,9:1,10:2,11:3,12:4,13:5,14:7,15:9,16:11,17:13,18:15,19:17,20:19};
const TOTAL=27,MIN=8,MAX=20;
const LS_KEY='dnd_config';

const ATTRS=[
  {k:'str',n:'力量',e:'STR',icon:'STR',s:'运动·近战'},
  {k:'dex',n:'敏捷',e:'DEX',icon:'DEX',s:'特技·巧手·潜行·远程'},
  {k:'con',n:'体质',e:'CON',icon:'CON',s:'HP·抗毒·专注'},
  {k:'int',n:'智力',e:'INT',icon:'INT',s:'奥秘·历史·调查·自然·宗教'},
  {k:'wis',n:'感知',e:'WIS',icon:'WIS',s:'洞察·医药·察觉·生存'},
  {k:'cha',n:'魅力',e:'CHA',icon:'CHA',s:'欺瞒·威吓·表演·游说'},
];

const RACES:Record<string,{name:string;traits:string[]}>={
  '人类':{name:'人类',traits:['全属性均衡','额外1技能熟练','额外1语言']},
  '高等精灵':{name:'高等精灵',traits:['黑暗视觉60尺','敏锐感官','精灵血统','1法师戏法']},
  '木精灵':{name:'木精灵',traits:['黑暗视觉60尺','敏锐感官','野性面具','移速35尺']},
  '山地矮人':{name:'山地矮人',traits:['黑暗视觉60尺','矮人体魄','石匠知识','中甲熟练']},
  '半身人':{name:'半身人',traits:['幸运(自然1可重掷)','勇敢','灵巧']},
  '龙裔':{name:'龙裔',traits:['龙族吐息','元素抗性','额外语言:龙语']},
  '半精灵':{name:'半精灵',traits:['黑暗视觉60尺','精灵血统','两项额外技能']},
  '半兽人':{name:'半兽人',traits:['黑暗视觉60尺','坚韧不屈','凶蛮攻击']},
  '提夫林':{name:'提夫林',traits:['黑暗视觉60尺','地狱抗性','地狱遗赠']},
  '侏儒':{name:'侏儒',traits:['黑暗视觉60尺','侏儒狡黠','工匠知识']},
};

const CLASSES:Record<string,{name:string;pri:string;hd:string;profs:string[]}>={
  '战士':{name:'战士',pri:'str',hd:'d10',profs:['全盔甲·盾牌','军用/简易武器','运动·威吓']},
  '法师':{name:'法师',pri:'int',hd:'d6',profs:['匕首·飞镖·投石索·棍棒·轻弩','奥秘·调查']},
  '游荡者':{name:'游荡者',pri:'dex',hd:'d8',profs:['轻甲','简易武器·手弩·长剑·细剑·短剑','盗贼工具','潜行·巧手·察觉·洞悉']},
  '牧师':{name:'牧师',pri:'wis',hd:'d8',profs:['中甲·盾牌','简易武器','宗教·医药']},
  '游侠':{name:'游侠',pri:'dex',hd:'d10',profs:['中甲·盾牌','军用/简易武器','生存·自然·察觉']},
  '吟游诗人':{name:'吟游诗人',pri:'cha',hd:'d8',profs:['轻甲','简易武器·手弩·长剑·细剑·短剑','3种乐器','表演·游说·历史']},
  '野蛮人':{name:'野蛮人',pri:'str',hd:'d12',profs:['中甲·盾牌','军用/简易武器','运动·自然·威吓']},
  '圣武士':{name:'圣武士',pri:'str',hd:'d10',profs:['全盔甲·盾牌','军用/简易武器','游说·宗教']},
  '武僧':{name:'武僧',pri:'dex',hd:'d8',profs:['简易武器·短剑','巧手·运动·洞悉·隐匿']},
  '术士':{name:'术士',pri:'cha',hd:'d6',profs:['匕首·飞镖·投石索·棍棒·轻弩','奥秘·欺瞒']},
  '德鲁伊':{name:'德鲁伊',pri:'wis',hd:'d8',profs:['中甲·盾牌(非金属)','木棒·匕首·飞镖·投石索·弯刀·矛','自然·生存·驯兽']},
  '邪术师':{name:'邪术师',pri:'cha',hd:'d8',profs:['轻甲','简易武器','奥秘·欺瞒·威吓·调查']},
};

const SKILLS=[
  {n:'运动',a:'str',d:'攀爬、跳跃、游泳'},{n:'特技',a:'dex',d:'平衡、翻滚、闪避'},
  {n:'巧手',a:'dex',d:'扒窃、开锁'},{n:'潜行',a:'dex',d:'隐匿移动'},
  {n:'奥秘',a:'int',d:'魔法知识、符文'},{n:'历史',a:'int',d:'往昔事件、古文明'},
  {n:'调查',a:'int',d:'搜索、推理'},{n:'自然',a:'int',d:'动植物、地理'},
  {n:'宗教',a:'int',d:'神祇、仪式'},{n:'洞悉',a:'wis',d:'辨别谎言'},
  {n:'医药',a:'wis',d:'诊断、稳定伤势'},{n:'察觉',a:'wis',d:'发现细节'},
  {n:'生存',a:'wis',d:'追踪、觅食'},{n:'欺瞒',a:'cha',d:'说谎、伪装'},
  {n:'威吓',a:'cha',d:'胁迫、施压'},{n:'表演',a:'cha',d:'演出、演说'},
  {n:'游说',a:'cha',d:'谈判、说服'},
];

const TONES=[
  '史诗奇幻','黑暗奇幻','悬疑探案','轻松幽默','末日废土','东方武侠','哥特恐怖','蒸汽朋克',
  '剑与魔法','克苏鲁恐怖','太空歌剧','赛博朋克','低魔写实','高魔冒险','政治权谋','宫廷阴谋',
  '海盗冒险','西部荒野','现代都市','神话史诗','童话暗黑','推理本格','战斗爽文','生存探索',
  '神秘学','宗教史诗','精灵森林','矮人王国','龙裔战争','深海恐惧','梦境异界','废土求生',
];
const WORLD_STAGES=[
  {key:'conflict',label:'构建世界冲突',desc:'雕琢世界的伤痕与张力'},
  {key:'plot',label:'编织三幕结构',desc:'铺设命运的丝线'},
  {key:'npc',label:'塑造众生百态',desc:'赋予每个灵魂呼吸'},
  {key:'encounter',label:'布置遭遇与秘密',desc:'埋藏等待发现的宝藏'},
  {key:'review',label:'首席评委审阅',desc:'逐项打分，严苛修订'},
];

function mod(v:number){const m=Math.floor((v-10)/2);return m>=0?`+${m}`:`${m}`;}
function spent(a:Record<string,number>){let s=0;for(const v of Object.values(a))s+=COST[v]||0;return s;}

// ═══════════════════════ localStorage持久化 ═══════════════════════

function loadConfig():{apiKey:string;modelName:string;baseUrl:string;username:string}{
  try{const d=JSON.parse(localStorage.getItem(LS_KEY)||'{}');return{
    apiKey:d.apiKey||'',modelName:d.modelName||'',
    baseUrl:d.baseUrl||'https://api.openai.com/v1',username:d.username||'',
  };}catch{return{apiKey:'',modelName:'',baseUrl:'https://api.openai.com/v1',username:''};}
}
function saveConfig(cfg:{apiKey:string;modelName:string;baseUrl:string;username:string}){
  localStorage.setItem(LS_KEY,JSON.stringify(cfg));
}

// ═══════════════════════ 组件 ═══════════════════════

export default function StartScreen(){
  const [step,setStep]=useState(1);
  const cfg=loadConfig();

  const [apiKey,setApiKey]=useState(cfg.apiKey);
  const [modelName,setModelName]=useState(cfg.modelName);
  const [baseUrl,setBaseUrl]=useState(cfg.baseUrl);
  const [showKey,setShowKey]=useState(false);
  const [provider,setProvider]=useState<'openai'|'deepseek'|'custom'>(baseUrl.includes('deepseek')?'deepseek':baseUrl.includes('openai')?'openai':'custom');
  const [modelOptions,setModelOptions]=useState<string[]>([]);
  const [modelFetchBusy,setModelFetchBusy]=useState(false);
  const [modelFetchErr,setModelFetchErr]=useState('');
  const [modelInputMode,setModelInputMode]=useState<'select'|'manual'>('manual');
  const [scenarioMode,setScenarioMode]=useState<'existing'|'split'|'generate'>('generate');
  const [username,setUsername]=useState(cfg.username);
  const [charName,setCharName]=useState('');
  const [gender,setGender]=useState('未指定');
  const [race,setRace]=useState('人类');
  const [charClass,setCharClass]=useState('战士');
  const [attrs,setAttrs]=useState<Record<string,number>>({str:8,dex:8,con:8,int:8,wis:8,cha:8});
  const [attrMode,setAttrMode]=useState<'manual'|'ai'>('manual');
  const [backstoryText,setBackstoryText]=useState('');
  const [aiGen,setAiGen]=useState<{attributes:Record<string,number>;backstory:string}|null>(null);
  const [aiBusy,setAiBusy]=useState(false);
  const [aiErr,setAiErr]=useState('');

  // 技能熟练选择（选2项）
  const [skillPicks,setSkillPicks]=useState<string[]>([]);

  // 世界
  const [worldDesc,setWorldDesc]=useState('');
  const [worldTone,setWorldTone]=useState('史诗奇幻');
  const [customTone,setCustomTone]=useState('');
  const [toneCustom,setToneCustom]=useState(false);
  const [worldNote,setWorldNote]=useState('');
  const [referenceScript,setReferenceScript]=useState('');
  const [worldOutline,setWorldOutline]=useState('');
  const [worldScore,setWorldScore]=useState<number|null>(null);
  const [worldStateJson,setWorldStateJson]=useState('');
  const [scenarioId,setScenarioId]=useState('');
  const [worldGenBusy,setWorldGenBusy]=useState(false);
  const [worldGenErr,setWorldGenErr]=useState('');
  const [worldGenStage,setWorldGenStage]=useState(-1);
  const [savedScenarios,setSavedScenarios]=useState<Array<{id:string;title:string;description:string;summary?:string;system?:string;tone:string;score:number;total_sessions:number;character_name?:string;race?:string;char_class?:string}>>([]);
  const [selectedScenario,setSelectedScenario]=useState('');
  const [showScenarioList,setShowScenarioList]=useState(false);
  const [scenarioText,setScenarioText]=useState('');
  const [playMode,setPlayMode]=useState<'lite'|'deep'>('deep');
  const [gameSystem,setGameSystem]=useState<GameSystem>('dnd5e');
  const [scenarioSystem,setScenarioSystem]=useState<GameSystem>('dnd5e');
  const [customRules,setCustomRules]=useState('');
  const [cocAttrs,setCocAttrs]=useState<Record<string,number>>({str:50,con:50,dex:50,int:50,pow:50,cha:50,siz:50,edu:50});
  const [occupation,setOccupation]=useState('学者');
  const [cocSkillPicks,setCocSkillPicks]=useState<string[]>([]);
  const [cocLuck,setCocLuck]=useState(50);
  const [customAttrs,setCustomAttrs]=useState<Record<string,number>>({str:10,dex:10,con:10,int:10,wis:10,cha:10});
  const [splitter,setSplitter]=useState<'naive'|'semantic'>('naive');
  const [chunkSize,setChunkSize]=useState(900);
  const [scenarioSummary,setScenarioSummary]=useState('');
  const [sourceChunks,setSourceChunks]=useState<string[]>([]);
  const [importBusy,setImportBusy]=useState(false);
  const [importErr,setImportErr]=useState('');
  const [importFileName,setImportFileName]=useState('');

  // 知识库
  const [kbDocs,setKbDocs]=useState<Array<{id:string;title:string;source:string;system:string;tags:string[];chunk_count:number;created_at:string}>>([]);
  const [kbTitle,setKbTitle]=useState('');
  const [kbContent,setKbContent]=useState('');
  const [kbSystem,setKbSystem]=useState<GameSystem>('custom');
  const [kbTags,setKbTags]=useState('');
  const [kbBusy,setKbBusy]=useState(false);
  const [kbErr,setKbErr]=useState('');
  const [kbUploadFile,setKbUploadFile]=useState<File|null>(null);

  // 扩展包与存档
  const [extList,setExtList]=useState<Array<{id:string;name:string;description:string;system:string;tags:string[];source:string;created_at:string}>>([]);
  const [extName,setExtName]=useState('');
  const [extDesc,setExtDesc]=useState('');
  const [extContent,setExtContent]=useState('');
  const [extSystem,setExtSystem]=useState<GameSystem>('custom');
  const [extTags,setExtTags]=useState('');
  const [extGenDesc,setExtGenDesc]=useState('');
  const [extBusy,setExtBusy]=useState(false);
  const [extErr,setExtErr]=useState('');
  const [activeExtIds,setActiveExtIds]=useState<string[]>([]);
  const [saves,setSaves]=useState<Array<{id:string;label:string;auto:boolean;session_id:string;created_at:string;character_name:string;game_system:string}>>([]);
  const [saveLabel,setSaveLabel]=useState('');

  // 地图 / 生物图鉴 / 角色图片
  const [maps,setMaps]=useState<Array<{id:string;name:string;description:string;image_path:string;locations:Array<{name:string;x:number;y:number}>;system:string}>>([]);
  const [mapName,setMapName]=useState(''); const [mapDesc,setMapDesc]=useState(''); const [mapSystem,setMapSystem]=useState<GameSystem>('custom'); const [mapFile,setMapFile]=useState<File|null>(null);
  const [bestiary,setBestiary]=useState<Array<{id:string;name:string;system:string;description:string;stats:Record<string,string>;image_path:string;tags:string[]}>>([]);
  const [beastName,setBeastName]=useState(''); const [beastSystem,setBeastSystem]=useState<GameSystem>('custom'); const [beastDesc,setBeastDesc]=useState(''); const [beastStats,setBeastStats]=useState(''); const [beastTags,setBeastTags]=useState(''); const [beastFile,setBeastFile]=useState<File|null>(null);
  const [characterImage,setCharacterImage]=useState('');
  const [mediaBusy,setMediaBusy]=useState(false); const [mediaErr,setMediaErr]=useState('');
  const [showRulebook,setShowRulebook]=useState(false);

  const [loading,setLoading]=useState(false);
  const [error,setError]=useState('');
  const setSession=useGameStore(s=>s.setSession);

  // 自动加载已保存剧本
  useEffect(()=>{
    fetch('/api/scenarios').then(r=>r.json()).then(d=>setSavedScenarios(d.scenarios||[])).catch(()=>{});
    fetch('/api/knowledge').then(r=>r.json()).then(d=>setKbDocs(d.documents||[])).catch(()=>{});
    fetch(`/api/extensions?username=${encodeURIComponent(username||'default')}`).then(r=>r.json()).then(d=>setExtList(d.extensions||[])).catch(()=>{});
    fetch(`/api/maps?username=${encodeURIComponent(username||'default')}`).then(r=>r.json()).then(d=>setMaps(d.maps||[])).catch(()=>{});
    fetch(`/api/bestiary?username=${encodeURIComponent(username||'default')}`).then(r=>r.json()).then(d=>setBestiary(d.bestiary||[])).catch(()=>{});
    fetch(`/api/saves?username=${encodeURIComponent(username||'default')}`).then(r=>r.json()).then(d=>setSaves(d.saves||[])).catch(()=>{});
  },[]);

  // 自动保持配置（每次关键字段变化）
  useEffect(()=>{saveConfig({apiKey,modelName,baseUrl,username});},[apiKey,modelName,baseUrl,username]);

  const applyProvider=(p:'openai'|'deepseek'|'custom')=>{
    setProvider(p);
    if(p==='openai')setBaseUrl('https://api.openai.com/v1');
    else if(p==='deepseek')setBaseUrl('https://api.deepseek.com/v1');
  };

  const fetchModels=async()=>{
    setModelFetchBusy(true);setModelFetchErr('');
    try{
      const r=await fetch('/api/models',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({base_url:baseUrl,api_key:apiKey})});
      if(!r.ok){const e=await r.json().catch(()=>({}));throw new Error(e.detail||'获取模型失败');}
      const d=await r.json();
      setModelOptions(d.models||[]);
      if(d.models?.length===1)setModelName(d.models[0]);
      if(d.models?.length>0)setModelInputMode('select');
    }catch(e:unknown){setModelFetchErr(e instanceof Error?e.message:'获取模型失败');}
    finally{setModelFetchBusy(false);}
  };

  const rm=useMemo(()=>TOTAL-spent(attrs),[attrs]);
  const finalAttrs=useMemo(()=>{
    if(gameSystem==='coc') return cocAttrs;
    if(gameSystem==='custom') return customAttrs;
    return aiGen?.attributes||attrs;
  },[attrs,aiGen,gameSystem,cocAttrs,customAttrs]);
  const rc=RACES[race]||RACES['人类'];
  const cc=CLASSES[charClass]||CLASSES['战士'];
  const d5Derived = getDnd5Derived(cc.name, finalAttrs, 1);
  const d4Derived = getDnd4Derived(cc.name, finalAttrs);

  const inc=useCallback((k:string)=>setAttrs(p=>{const c=p[k];if(c>=MAX)return p;const nv=c+1;if(spent(p)+(COST[nv]||0)-(COST[c]||0)>TOTAL)return p;return{...p,[k]:nv};}),[]);
  const dec=useCallback((k:string)=>setAttrs(p=>p[k]<=MIN?p:{...p,[k]:p[k]-1}),[]);

  const toggleSkill=(name:string)=>{setSkillPicks(p=>p.includes(name)?p.filter(s=>s!==name):p.length<2?[...p,name]:p);};

  const callAI=async(backstoryOnly:boolean)=>{
    setAiBusy(true);setAiErr('');
    try{
      const isCoc=gameSystem==='coc';
      const body:Record<string,unknown>={
        character_name:charName||'冒险者',
        gender,
        race:isCoc?'调查员':rc.name,
        char_class:isCoc?occupation:cc.name,
        game_system:gameSystem,
        scenario_summary:scenarioSummary||undefined,
        custom_rules:gameSystem==='custom'?customRules:undefined,
        api_key:apiKey||undefined,
        model_name:modelName||undefined,
        base_url:baseUrl||undefined,
      };
      if(backstoryOnly)body.attributes=isCoc?cocAttrs:attrs;
      else if(backstoryText.trim())body.backstory=backstoryText.trim();
      const r=await fetch('/api/generate/character',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(body)});
      if(!r.ok)throw new Error('生成失败');
      const d=await r.json();
      if(backstoryOnly){
        d.attributes=isCoc?cocAttrs:attrs;
      }
      setAiGen(d);
    }catch(e:unknown){setAiErr(e instanceof Error?e.message:'生成失败');}
    finally{setAiBusy(false);}
  };

  const genWorld=async()=>{
    setWorldGenBusy(true);setWorldGenErr('');setWorldGenStage(0);
    const timer=setInterval(()=>setWorldGenStage(s=>s<4?s+1:s),3000);
    try{
      const r=await fetch('/api/generate/world',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({
        description:worldDesc||'一个'+worldTone+'的冒险',character_name:charName||'冒险者',
        race:rc.name,char_class:cc.name,tone:worldTone,
        game_system:gameSystem,custom_rules:customRules||undefined,
        api_key:apiKey||undefined,model_name:modelName||undefined,base_url:baseUrl||undefined,
      })});
      clearInterval(timer);setWorldGenStage(4);
      if(!r.ok)throw new Error('生成失败');
      const d=await r.json();setWorldOutline(d.content);setWorldScore(d.score);
      if(d.scenario_id){setScenarioId(d.scenario_id);setSelectedScenario(d.scenario_id);setShowScenarioList(false);}
      if(d.world_state_json)setWorldStateJson(d.world_state_json);
      if(d.summary)setScenarioSummary(d.summary);
      if(d.system)setScenarioSystem(d.system as GameSystem);
      if(d.source_chunks)setSourceChunks(d.source_chunks);
      fetch('/api/scenarios').then(r=>r.json()).then(d=>setSavedScenarios(d.scenarios||[])).catch(()=>{});
      loadKb();
    }catch(e:unknown){setWorldGenErr(e instanceof Error?e.message:'生成失败');clearInterval(timer);}
    finally{setWorldGenBusy(false);}
  };

  const loadScenario=async(sid:string)=>{
    try{
      const r=await fetch(`/api/scenarios/${sid}`);
      if(!r.ok)return;
      const d=await r.json();
      setWorldOutline(d.world_outline);setWorldStateJson(d.world_state_json||'');
      setScenarioSummary(d.summary||d.meta?.summary||'');
      setSourceChunks(d.source_chunks||[]);
      setCustomRules(d.custom_rules||d.meta?.custom_rules||'');
      if(d.meta?.system||d.system)setScenarioSystem((d.meta?.system||d.system) as GameSystem);
      setScenarioId(sid);setSelectedScenario(sid);setShowScenarioList(false);
      setWorldScore(d.meta?.score||null);
    }catch{}
  };

  const importScenario=async(file:File)=>{
    setImportBusy(true);setImportErr('');setImportFileName(file.name);
    try{
      const fd=new FormData();
      fd.append('file',file);
      fd.append('splitter',splitter);
      fd.append('chunk_size',String(chunkSize));
      fd.append('tone',worldTone);
      fd.append('system',gameSystem);
      fd.append('custom_rules',customRules||'');
      fd.append('api_key',apiKey||'');
      fd.append('model_name',modelName||'');
      fd.append('base_url',baseUrl||'');
      const r=await fetch('/api/scenarios/import',{method:'POST',body:fd});
      if(!r.ok){const e=await r.json().catch(()=>({}));throw new Error(e.detail||'导入失败');}
      const d=await r.json();
      setWorldOutline(d.content);setWorldScore(d.score);
      setWorldStateJson(d.world_state_json||'');
      setScenarioId(d.scenario_id);
      setScenarioSummary(d.summary||'');
      if(d.system)setScenarioSystem(d.system as GameSystem);
      setSourceChunks(d.source_chunks||[]);
      setSelectedScenario(d.scenario_id);setShowScenarioList(false);
      fetch('/api/scenarios').then(r=>r.json()).then(d=>setSavedScenarios(d.scenarios||[])).catch(()=>{});
      loadKb();
    }catch(e:unknown){setImportErr(e instanceof Error?e.message:'导入失败');}
    finally{setImportBusy(false);}
  };

  const loadKb=async()=>{
    try{
      const r=await fetch('/api/knowledge');
      if(r.ok)setKbDocs((await r.json()).documents||[]);
    }catch{}
  };

  const addKbNote=async()=>{
    setKbBusy(true);setKbErr('');
    try{
      const r=await fetch('/api/knowledge',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({
        title:kbTitle||'未命名知识',
        content:kbContent,
        system:kbSystem,
        source:'player-note',
        tags:kbTags.split(',').map(s=>s.trim()).filter(Boolean),
      })});
      if(!r.ok){const e=await r.json().catch(()=>({}));throw new Error(e.detail||'添加失败');}
      setKbTitle('');setKbContent('');setKbTags('');
      await loadKb();
    }catch(e:unknown){setKbErr(e instanceof Error?e.message:'添加失败');}
    finally{setKbBusy(false);}
  };

  const uploadKb=async(file:File)=>{
    setKbBusy(true);setKbErr('');
    try{
      const fd=new FormData();
      fd.append('file',file);
      fd.append('title',kbTitle||file.name);
      fd.append('system',kbSystem);
      fd.append('source','upload');
      fd.append('tags',kbTags);
      const r=await fetch('/api/knowledge/upload',{method:'POST',body:fd});
      if(!r.ok){const e=await r.json().catch(()=>({}));throw new Error(e.detail||'上传失败');}
      setKbTitle('');setKbTags('');setKbUploadFile(null);
      await loadKb();
    }catch(e:unknown){setKbErr(e instanceof Error?e.message:'上传失败');}
    finally{setKbBusy(false);}
  };

  const deleteKb=async(id:string)=>{
    try{
      await fetch(`/api/knowledge/${id}`,{method:'DELETE'});
      await loadKb();
    }catch{}
  };

  const seedKb=async()=>{
    setKbBusy(true);
    try{
      await fetch('/api/knowledge/seed',{method:'POST'});
      await loadKb();
    }catch{}
    finally{setKbBusy(false);}
  };

  const loadExts=async()=>{
    try{
      const r=await fetch(`/api/extensions?username=${encodeURIComponent(username||'default')}`);
      if(r.ok)setExtList((await r.json()).extensions||[]);
    }catch{}
  };

  const loadSaves=async()=>{
    try{
      const r=await fetch(`/api/saves?username=${encodeURIComponent(username||'default')}`);
      if(r.ok)setSaves((await r.json()).saves||[]);
    }catch{}
  };

  const addExt=async()=>{
    setExtBusy(true);setExtErr('');
    try{
      const r=await fetch('/api/extensions',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({
        username:username||'default',name:extName||'未命名扩展包',description:extDesc,content:extContent,
        system:extSystem,tags:extTags.split(',').map(s=>s.trim()).filter(Boolean),
      })});
      if(!r.ok){const e=await r.json().catch(()=>({}));throw new Error(e.detail||'添加失败');}
      setExtName('');setExtDesc('');setExtContent('');setExtTags('');
      await loadExts();
    }catch(e:unknown){setExtErr(e instanceof Error?e.message:'添加失败');}
    finally{setExtBusy(false);}
  };

  const genExt=async()=>{
    setExtBusy(true);setExtErr('');
    try{
      const r=await fetch('/api/extensions/generate',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({
        username:username||'default',description:extGenDesc,system:extSystem,
        api_key:apiKey||undefined,model_name:modelName||undefined,base_url:baseUrl||undefined,
      })});
      if(!r.ok){const e=await r.json().catch(()=>({}));throw new Error(e.detail||'生成失败');}
      setExtGenDesc('');await loadExts();
    }catch(e:unknown){setExtErr(e instanceof Error?e.message:'生成失败');}
    finally{setExtBusy(false);}
  };

  const deleteExt=async(id:string)=>{
    try{
      await fetch(`/api/extensions/${id}?username=${encodeURIComponent(username||'default')}`,{method:'DELETE'});
      setActiveExtIds(ids=>ids.filter(x=>x!==id));
      await loadExts();
    }catch{}
  };

  const loadSaveGame=async(saveId:string)=>{
    try{
      const r=await fetch('/api/saves/load',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({username:username||'default',save_id:saveId})});
      if(!r.ok)return;
      const d=await r.json();
      setSession(d.session_id);
    }catch{}
  };

  const uploadMap=async(file:File)=>{
    setMediaBusy(true);setMediaErr('');
    try{
      const fd=new FormData(); fd.append('file',file); fd.append('username',username||'default'); fd.append('name',mapName||file.name); fd.append('description',mapDesc); fd.append('system',mapSystem);
      const r=await fetch('/api/maps/upload',{method:'POST',body:fd});
      if(!r.ok){const e=await r.json().catch(()=>({}));throw new Error(e.detail||'上传失败');}
      setMapName('');setMapDesc('');setMapFile(null);
      const d=await (await fetch(`/api/maps?username=${encodeURIComponent(username||'default')}`)).json(); setMaps(d.maps||[]);
    }catch(e:unknown){setMediaErr(e instanceof Error?e.message:'上传失败');}
    finally{setMediaBusy(false);}
  };

  const deleteMap=async(id:string)=>{
    try{await fetch(`/api/maps/${id}?username=${encodeURIComponent(username||'default')}`,{method:'DELETE'}); setMaps(maps.filter(m=>m.id!==id));}catch{}
  };

  const uploadBeast=async(file:File)=>{
    setMediaBusy(true);setMediaErr('');
    try{
      const fd=new FormData(); fd.append('file',file); fd.append('username',username||'default'); fd.append('name',beastName||file.name); fd.append('system',beastSystem); fd.append('description',beastDesc); fd.append('stats',beastStats||'{}'); fd.append('tags',beastTags);
      const r=await fetch('/api/bestiary/upload',{method:'POST',body:fd});
      if(!r.ok){const e=await r.json().catch(()=>({}));throw new Error(e.detail||'上传失败');}
      setBeastName('');setBeastDesc('');setBeastStats('');setBeastTags('');setBeastFile(null);
      const d=await (await fetch(`/api/bestiary?username=${encodeURIComponent(username||'default')}`)).json(); setBestiary(d.bestiary||[]);
    }catch(e:unknown){setMediaErr(e instanceof Error?e.message:'上传失败');}
    finally{setMediaBusy(false);}
  };

  const deleteBeast=async(id:string)=>{
    try{await fetch(`/api/bestiary/${id}?username=${encodeURIComponent(username||'default')}`,{method:'DELETE'}); setBestiary(bestiary.filter(b=>b.id!==id));}catch{}
  };

  const uploadCharacterImage=async(file:File)=>{
    setMediaBusy(true);setMediaErr('');
    try{
      const fd=new FormData(); fd.append('file',file); fd.append('username',username||'default');
      const r=await fetch('/api/media/character',{method:'POST',body:fd});
      if(!r.ok){const e=await r.json().catch(()=>({}));throw new Error(e.detail||'上传失败');}
      setCharacterImage((await r.json()).image_path||'');
    }catch(e:unknown){setMediaErr(e instanceof Error?e.message:'上传失败');}
    finally{setMediaBusy(false);}
  };

  const start=async()=>{
    if(!charName.trim()){setError('请输入角色名称');return;}
    setLoading(true);setError('');
    try{
      const isDnd = gameSystem==='dnd5e'||gameSystem==='dnd4e';
      const r=await fetch('/api/game/new',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({
        username:username||'冒险者',character_name:charName,
        gender:gameSystem==='coc'?'未指定':gender,
        race:gameSystem==='coc'?'调查员':rc.name,
        char_class:gameSystem==='coc'?occupation:cc.name,
        attributes:finalAttrs,
        race_traits:isDnd?rc.traits:undefined,
        class_proficiencies:isDnd?cc.profs:undefined,
        api_key:apiKey||undefined,model_name:modelName||undefined,base_url:baseUrl||undefined,
        backstory:aiGen?.backstory||undefined,world_context:scenarioText||undefined,
        world_outline:worldOutline||undefined,world_state_json:worldStateJson||undefined,
        reference_script:referenceScript||undefined,scenario_id:scenarioId||undefined,
        new_world:!scenarioId,
        skill_proficiencies:gameSystem==='coc'?cocSkillPicks:skillPicks,
        play_mode:playMode,
        game_system:gameSystem,
        custom_rules:gameSystem==='custom'?customRules:undefined,
        luck:gameSystem==='coc'?cocLuck:undefined,
        extension_ids:activeExtIds,
        character_image:characterImage||undefined,
      })});
      if(!r.ok){const e=await r.json();throw new Error(e.detail||'创建失败');}
      setSession((await r.json()).session_id);
    }catch(e:unknown){setError(e instanceof Error?e.message:'未知错误');setLoading(false);}
  };

  // ═══════════════════════ 渲染 ═══════════════════════

  return(
    <div className="min-h-screen bg-gradient-to-b from-white via-gray-50 to-white flex items-center justify-center p-4">
      <div className="w-full max-w-2xl max-h-screen overflow-y-auto">
        <div className="text-center mb-6">
          <h1 className="text-3xl font-bold text-gray-900 tracking-tight">TRPG 跑团</h1>
          <p className="text-gray-500 text-sm mt-1">单人冒险 · 智能主持</p>
          <button onClick={()=>setShowRulebook(true)} className="mt-2 text-xs text-indigo-500 hover:text-indigo-700 underline underline-offset-2">打开玩家说明书</button>
        </div>

        {/* API 连接设置：放在选择剧本前，突出且必须 */}
        <div className="card p-4 mb-4 space-y-3">
          <div className="flex items-center justify-between">
            <p className="text-xs font-bold text-gray-800">API 连接</p>
            <div className="flex gap-1">
              {(['openai','deepseek','custom'] as const).map(p=>(
                <button key={p} onClick={()=>applyProvider(p)} className={`text-[10px] px-2.5 py-1 rounded-lg border transition-colors ${provider===p?'border-indigo-400 bg-indigo-50 text-indigo-700':'border-gray-200 text-gray-500 hover:border-gray-300'}`}>
                  {p==='openai'?'OpenAI':p==='deepseek'?'DeepSeek':'自定义'}
                </button>
              ))}
            </div>
          </div>
          <div className="grid gap-2">
            <div>
              <label className="block text-[10px] text-gray-500 mb-1">API 地址</label>
              <input value={baseUrl} onChange={e=>{setBaseUrl(e.target.value); if(!e.target.value.includes('deepseek')&&!e.target.value.includes('openai'))setProvider('custom');}} placeholder="https://api.openai.com/v1" className="input-field font-mono text-xs" />
            </div>
            <div>
              <label className="block text-[10px] text-gray-500 mb-1">API Key</label>
              <div className="flex gap-2">
                <input type={showKey?'text':'password'} value={apiKey} onChange={e=>setApiKey(e.target.value)} placeholder="sk-..." className="input-field font-mono text-xs flex-1" />
                <button onClick={()=>setShowKey(!showKey)} className="btn-secondary text-xs px-3">{showKey?'隐藏':'显示'}</button>
              </div>
            </div>
            <div>
              <label className="block text-[10px] text-gray-500 mb-1">模型（可从服务商自动获取，也可手动填写）</label>
              <div className="flex gap-2">
                {modelInputMode==='select' && modelOptions.length>0 ? (
                  <>
                    <select
                      value={modelOptions.includes(modelName) ? modelName : ''}
                      onChange={e=>{
                        if(e.target.value==='__manual__'){ setModelInputMode('manual'); return; }
                        setModelName(e.target.value);
                      }}
                      className="input-field font-mono text-xs flex-1"
                    >
                      <option value="" disabled>选择模型...</option>
                      {modelOptions.map(m=><option key={m} value={m}>{m}</option>)}
                      <option value="__manual__">手动输入...</option>
                    </select>
                    <button onClick={()=>setModelInputMode('manual')} className="btn-secondary text-xs px-3 whitespace-nowrap">手动</button>
                  </>
                ) : (
                  <>
                    <input value={modelName} onChange={e=>setModelName(e.target.value)} placeholder="输入模型名称" className="input-field font-mono text-xs flex-1" />
                    {modelOptions.length>0&&<button onClick={()=>setModelInputMode('select')} className="btn-secondary text-xs px-3 whitespace-nowrap">列表</button>}
                  </>
                )}
                <button onClick={fetchModels} disabled={modelFetchBusy || !apiKey} className="btn-secondary text-xs px-3 whitespace-nowrap">{modelFetchBusy?'获取中...':'获取模型'}</button>
              </div>
              {modelFetchErr&&<p className="text-red-500 text-[10px] mt-1">{modelFetchErr}</p>}
              {modelOptions.length>0&&<p className="text-[10px] text-gray-400 mt-1">已获取 {modelOptions.length} 个模型，可从下拉中选择。</p>}
            </div>
          </div>
        </div>

        {/* 游玩模式：在最开始选择，影响 token 消耗与扮演深度 */}
        <div className="grid grid-cols-2 gap-2 mb-4">
          <button onClick={()=>setPlayMode('lite')} className={`p-3 rounded-xl border text-left transition-all ${playMode==='lite'?'border-emerald-400 bg-emerald-50 ring-1 ring-emerald-200':'border-gray-200 bg-white hover:border-gray-300'}`}>
            <div className="flex items-center gap-2">
              <span className="text-[10px] font-bold text-emerald-700 bg-emerald-100 rounded px-1.5 py-0.5">精简</span>
              <div>
                <div className="text-sm font-bold text-gray-800">精简模式</div>
                <div className="text-[10px] text-gray-500">低 token 消耗 · 快节奏 · 性价比玩法</div>
              </div>
            </div>
          </button>
          <button onClick={()=>setPlayMode('deep')} className={`p-3 rounded-xl border text-left transition-all ${playMode==='deep'?'border-indigo-400 bg-indigo-50 ring-1 ring-indigo-200':'border-gray-200 bg-white hover:border-gray-300'}`}>
            <div className="flex items-center gap-2">
              <span className="text-[10px] font-bold text-indigo-700 bg-indigo-100 rounded px-1.5 py-0.5">深度</span>
              <div>
                <div className="text-sm font-bold text-gray-800">深度模式</div>
                <div className="text-[10px] text-gray-500">高 token 消耗 · 高深度扮演 · 沉浸体验</div>
              </div>
            </div>
          </button>
        </div>

        <div className="flex gap-1 mb-5">
          {['剧本','角色创建','冒险准备','知识库'].map((s,i)=>(
            <button key={i} onClick={()=>setStep(i+1)} className={`flex-1 py-2 rounded-lg text-xs font-medium transition-all ${
              step===i+1?'bg-indigo-600 text-white shadow-sm':step>i+1?'bg-indigo-50 text-indigo-600':'bg-gray-100 text-gray-400'}`}>{s}</button>
          ))}
        </div>

        <div className="card p-6 space-y-5">
          {/* ═══════ 步骤2: 角色创建 ═══════ */}
          {step===2&&(
            <div className="space-y-5">
              <p className="text-[10px] text-gray-400 bg-gray-50 rounded-lg p-2 border border-gray-200">
                剧本系统：{GAME_SYSTEM_LABELS[scenarioSystem]} ｜ 角色系统：{GAME_SYSTEM_LABELS[gameSystem]}
                <span className="text-emerald-600">（角色不绑定剧本，可自由选择）</span>
              </p>
              {/* 基础信息 */}
              <div className="grid grid-cols-2 gap-3">
                <div><label className="block text-xs font-medium text-gray-600 mb-1">玩家</label><input value={username} onChange={e=>setUsername(e.target.value)} placeholder="你的名字" className="input-field" /></div>
                <div><label className="block text-xs font-medium text-gray-600 mb-1">角色名 <span className="text-red-400">*</span></label><input value={charName} onChange={e=>setCharName(e.target.value)} placeholder="取名..." className="input-field" /></div>
              </div>

              {/* 角色图片 */}
              <div className="flex items-center gap-3 bg-gray-50 rounded-lg p-3 border border-gray-200">
                {characterImage?<img src={characterImage} alt="角色" className="w-16 h-16 object-cover rounded-lg border border-gray-300" />:<div className="w-16 h-16 bg-gray-200 rounded-lg flex items-center justify-center text-[9px] text-gray-400">暂无头像</div>}
                <div className="flex-1">
                  <label className="block text-[10px] text-gray-500 mb-1">角色图片（可自定义）</label>
                  <input type="file" accept=".png,.jpg,.jpeg,.webp" onChange={e=>{const f=e.target.files?.[0]; if(f)uploadCharacterImage(f);}} className="block w-full text-xs" />
                  {mediaErr&&<p className="text-red-500 text-[10px] mt-1">{mediaErr}</p>}
                </div>
              </div>

              {/* 性别 */}
              <div>
                <label className="block text-xs font-medium text-gray-600 mb-2">性别</label>
                <div className="flex gap-2">
                  {['未指定','男','女'].map(g=>(
                    <button key={g} onClick={()=>setGender(g)} className={`px-4 py-1.5 rounded-lg border text-xs transition-all ${gender===g?'border-indigo-400 bg-indigo-50 text-indigo-700':'border-gray-200 bg-white text-gray-500 hover:border-gray-300'}`}>{g}</button>
                  ))}
                </div>
              </div>

              {/* 种族（仅 D&D 系） */}
              {(gameSystem==='dnd5e'||gameSystem==='dnd4e')&&(
                <div>
                  <label className="block text-xs font-medium text-gray-600 mb-2">种族</label>
                  <div className="grid grid-cols-2 gap-1.5">
                    {Object.entries(RACES).map(([k,v])=>(
                      <button key={k} onClick={()=>setRace(k)} className={`p-2 rounded-lg border text-left text-xs transition-all ${race===k?'border-indigo-400 bg-indigo-50 text-indigo-700':'border-gray-200 bg-white text-gray-600 hover:border-gray-300'}`}>{v.name}</button>
                    ))}
                  </div>
                  <div className="mt-2 bg-gray-50 rounded-lg p-2.5 border border-gray-200">
                    <p className="text-[10px] text-gray-500 font-medium mb-1">{rc.name} 特性</p>
                    {rc.traits.map((t,i)=><p key={i} className="text-[11px] text-gray-600">· {t}</p>)}
                  </div>
                </div>
              )}

              {/* 职业 / 调查员职业 */}
              {(gameSystem==='dnd5e'||gameSystem==='dnd4e')&&(
                <div>
                  <label className="block text-xs font-medium text-gray-600 mb-2">{gameSystem==='dnd4e'?'职业（4e）':'职业'}</label>
                  <div className="grid grid-cols-2 gap-1.5">
                    {(gameSystem==='dnd4e'?DND4_CLASSES:Object.keys(CLASSES)).map(k=>{
                      const v=CLASSES[k]||{name:k,hd:'?',pri:'str',profs:[]};
                      return(
                        <button key={k} onClick={()=>setCharClass(k)} className={`p-2 rounded-lg border text-left text-xs transition-all ${charClass===k?'border-indigo-400 bg-indigo-50 text-indigo-700':'border-gray-200 bg-white text-gray-600 hover:border-gray-300'}`}>{v.name} {gameSystem==='dnd4e'?'':<span className="text-[9px] text-gray-400">({v.hd})</span>}</button>
                      );
                    })}
                  </div>
                  <div className="mt-2 bg-gray-50 rounded-lg p-2.5 border border-gray-200">
                    <p className="text-[10px] text-gray-500 font-medium mb-1">{cc.name} · HP{cc.hd} · 主属性:{ATTRS.find(a=>a.k===cc.pri)?.n}</p>
                    <div className="flex flex-wrap gap-1">{cc.profs.map((p,i)=><span key={i} className="text-[10px] bg-indigo-50 text-indigo-700 px-1.5 py-0.5 rounded-full border border-indigo-100">{p}</span>)}</div>
                  </div>
                </div>
              )}
              {gameSystem==='coc'&&(
                <div>
                  <label className="block text-xs font-medium text-gray-600 mb-2">调查员职业</label>
                  <div className="grid grid-cols-2 gap-1.5">
                    {COC_OCCUPATIONS.map(o=>(
                      <button key={o} onClick={()=>setOccupation(o)} className={`p-2 rounded-lg border text-left text-xs transition-all ${occupation===o?'border-indigo-400 bg-indigo-50 text-indigo-700':'border-gray-200 bg-white text-gray-600 hover:border-gray-300'}`}>{o}</button>
                    ))}
                  </div>
                </div>
              )}

              {/* 技能熟练选择（按系统） */}
              {(gameSystem==='dnd5e'||gameSystem==='dnd4e')&&(
                <div>
                  <label className="block text-xs font-medium text-gray-600 mb-2">
                    技能熟练 <span className="text-gray-400 font-normal">（选择2项 — 检定中获得+2熟练加值）</span>
                  </label>
                  <div className="grid grid-cols-3 gap-1">
                    {SKILLS.map(s=>{
                      const sel=skillPicks.includes(s.n);
                      const attrName=ATTRS.find(a=>a.k===s.a)?.n||s.a;
                      return(
                        <button key={s.n} onClick={()=>toggleSkill(s.n)}
                          className={`p-1.5 rounded-lg border text-left text-[10px] transition-all ${
                            sel?'border-indigo-400 bg-indigo-50 text-indigo-700':'border-gray-200 bg-white text-gray-500 hover:border-gray-300'
                          }`}>
                          <div className="font-medium">{s.n}</div>
                          <div className="text-[8px] opacity-60">{attrName} · {s.d}</div>
                        </button>
                      );
                    })}
                  </div>
                  {skillPicks.length>0&&<p className="text-[10px] text-indigo-500 mt-1">已选: {skillPicks.join('、')}</p>}
                </div>
              )}
              {gameSystem==='coc'&&(
                <div>
                  <label className="block text-xs font-medium text-gray-600 mb-2">
                    职业技能 <span className="text-gray-400 font-normal">（选择最多8项，作为初始技能熟练）</span>
                  </label>
                  <div className="grid grid-cols-3 gap-1">
                    {COC_SKILLS.map(s=>{
                      const sel=cocSkillPicks.includes(s);
                      return(
                        <button key={s} onClick={()=>setCocSkillPicks(p=>p.includes(s)?p.filter(x=>x!==s):p.length<8?[...p,s]:p)}
                          className={`p-1.5 rounded-lg border text-left text-[10px] transition-all ${
                            sel?'border-indigo-400 bg-indigo-50 text-indigo-700':'border-gray-200 bg-white text-gray-500 hover:border-gray-300'
                          }`}>
                          <div className="font-medium">{s}</div>
                        </button>
                      );
                    })}
                  </div>
                  {cocSkillPicks.length>0&&<p className="text-[10px] text-indigo-500 mt-1">已选: {cocSkillPicks.join('、')}</p>}
                </div>
              )}
              {gameSystem==='custom'&&(
                <p className="text-[11px] text-gray-500 bg-gray-50 rounded-lg p-2 border border-gray-200">自定义规则：技能与判定方式由你在「自定义规则」文本中定义，AI DM 会按规则文本处理。</p>
              )}

              {/* 属性分配（按系统） */}
              {(gameSystem==='dnd5e'||gameSystem==='dnd4e')&&(
                <div>
                  <div className="flex items-center justify-between mb-2">
                    <label className="text-xs font-medium text-gray-600">属性分配</label>
                    <div className="flex gap-1">
                      <button onClick={()=>{setAttrs(rollDndAttributes()); setAttrMode('manual');}} className="text-[10px] px-2.5 py-1 rounded-lg border border-gray-200 text-gray-500 hover:border-gray-300">随机</button>
                      <button onClick={()=>setAttrMode('manual')} className={`text-[10px] px-2.5 py-1 rounded-lg border ${attrMode==='manual'?'border-indigo-400 bg-indigo-50 text-indigo-700':'border-gray-200 text-gray-400'}`}>手动</button>
                      <button onClick={()=>setAttrMode('ai')} className={`text-[10px] px-2.5 py-1 rounded-lg border ${attrMode==='ai'?'border-indigo-400 bg-indigo-50 text-indigo-700':'border-gray-200 text-gray-400'}`}>自动</button>
                    </div>
                  </div>

                  {attrMode==='manual'&&(
                    <div className="space-y-1.5">
                      <div className="flex items-center justify-between bg-gray-50 rounded-lg px-3 py-1.5 border border-gray-200">
                        <span className="text-[10px] text-gray-500">购点{TOTAL}pt · 8-20 · 15以上每点2pt</span>
                        <div className="flex items-center gap-2">
                          <div className="w-20 h-1.5 bg-gray-200 rounded-full overflow-hidden"><div className="h-full bg-indigo-500 rounded-full transition-all" style={{width:`${((TOTAL-rm)/TOTAL)*100}%`}}/></div>
                          <span className={`text-xs font-bold ${rm<0?'text-red-500':'text-indigo-600'}`}>{rm}</span>
                        </div>
                      </div>
                      {ATTRS.map(a=>{const v=attrs[a.k]||8;const pri=cc.pri===a.k;return(
                        <div key={a.k} className={`flex items-center gap-2 p-2 rounded-lg border ${pri?'border-amber-300 bg-amber-50/50':'border-gray-200 bg-white'}`}>
                          <span className="text-sm w-6 text-center">{a.icon}</span>
                          <div className="w-12"><span className="text-xs font-semibold text-gray-700">{a.n}</span><span className="text-[9px] text-gray-400 ml-0.5">{a.e}</span></div>
                          <span className="text-[9px] text-gray-400 hidden sm:block w-20">{a.s}</span>
                          {pri&&<span className="text-[9px] bg-amber-100 text-amber-700 px-1 rounded-full">主</span>}
                          <div className="flex items-center gap-1 ml-auto">
                            <button onClick={()=>dec(a.k)} disabled={v<=MIN} className="w-6 h-6 rounded bg-gray-100 border border-gray-200 text-gray-500 hover:text-gray-700 disabled:opacity-30 text-xs">−</button>
                            <span className="w-6 text-center text-xs font-bold text-gray-700">{v}</span>
                            <button onClick={()=>inc(a.k)} disabled={v>=MAX||rm<(COST[v+1]||99)-(COST[v]||0)} className="w-6 h-6 rounded bg-gray-100 border border-gray-200 text-gray-500 hover:text-gray-700 disabled:opacity-30 text-xs">+</button>
                          </div>
                          <span className="w-12 text-right text-xs font-bold text-indigo-600">{v}<span className={`ml-0.5 ${(v-10)>=0?'text-emerald-500':'text-red-400'}`}>({mod(v)})</span></span>
                        </div>
                      );})}
                    </div>
                  )}

                  {attrMode==='ai'&&(
                    <div className="space-y-2">
                      <p className="text-[11px] text-gray-500">描述角色背景，系统自动分配属性。留空则全自动生成。</p>
                      <textarea value={backstoryText} onChange={e=>setBackstoryText(e.target.value)} placeholder="例如：森林中长大的精灵，跟随猎人父亲学箭..." rows={3} className="input-field resize-none" />
                    </div>
                  )}

                  {aiErr&&<p className="text-red-500 text-xs">{aiErr}</p>}

                  <button onClick={()=>callAI(attrMode==='manual')} disabled={aiBusy} className="mt-2 w-full py-2 bg-indigo-50 border border-indigo-200 hover:bg-indigo-100 text-indigo-700 rounded-lg text-sm font-medium transition-all disabled:opacity-50">
                    {aiBusy?'生成中...':attrMode==='manual'?'根据属性生成背景故事':'自动生成属性与背景'}
                  </button>

                  {aiGen&&(
                    <div className="mt-3 bg-gray-50 rounded-lg p-3 border border-gray-200 space-y-2">
                      {aiGen.backstory&&<div><p className="text-[10px] text-gray-500 font-medium mb-1">背景故事</p><p className="text-xs text-gray-700 leading-relaxed">{aiGen.backstory}</p></div>}
                      <div className="grid grid-cols-3 gap-1.5">
                        {ATTRS.map(a=>{const v=aiGen.attributes[a.k]||12;return(
                          <div key={a.k} className={`flex items-center gap-1.5 p-1.5 rounded ${cc.pri===a.k?'bg-amber-50':'bg-white'}`}>
                            <span className="text-xs">{a.icon}</span><span className="text-[10px] text-gray-500">{a.n}</span>
                            <span className="text-xs font-bold text-indigo-600 ml-auto">{v}</span><span className={`text-[9px] ${(v-10)>=0?'text-emerald-500':'text-red-400'}`}>({mod(v)})</span>
                          </div>
                        );})}
                      </div>
                    </div>
                  )}
                </div>
              )}

              {gameSystem==='coc'&&(
                <div>
                  <div className="flex items-center justify-between mb-2">
                    <label className="text-xs font-medium text-gray-600">调查员属性（1-99）</label>
                    <button onClick={()=>{setCocAttrs(rollCocAttributes()); setCocLuck(rollCocLuck());}} className="text-[10px] px-2.5 py-1 rounded-lg border border-indigo-200 bg-indigo-50 text-indigo-700 hover:bg-indigo-100">随机生成</button>
                  </div>
                  <div className="grid grid-cols-2 gap-2">
                    {COC_ATTRIBUTES.map(a=>(
                      <div key={a.key} className="flex items-center gap-2 p-2 rounded-lg border border-gray-200 bg-white">
                        <span className="text-sm">{a.icon}</span>
                        <span className="text-xs font-semibold text-gray-700 w-12">{a.label}</span>
                        <input type="number" min={1} max={99} value={cocAttrs[a.key]||50} onChange={e=>setCocAttrs(p=>({...p,[a.key]:Math.max(1,Math.min(99,Number(e.target.value)||50))}))} className="input-field text-xs py-1 px-2" />
                      </div>
                    ))}
                  </div>
                  <div className="mt-3 bg-gray-50 rounded-lg p-3 border border-gray-200 grid grid-cols-2 gap-2 text-xs">
                    <div>HP: <b>{(Math.floor(((cocAttrs.con||50)+(cocAttrs.siz||50))/2))}</b></div>
                    <div>MP: <b>{cocAttrs.pow||50}</b></div>
                    <div>SAN: <b>{(cocAttrs.pow||50)*5}</b></div>
                    <div>幸运: <b>{cocLuck}</b></div>
                  </div>
                  <button onClick={()=>callAI(true)} disabled={aiBusy} className="w-full py-2 bg-indigo-50 border border-indigo-200 hover:bg-indigo-100 text-indigo-700 rounded-lg text-sm font-medium transition-all disabled:opacity-50">
                    {aiBusy?'生成中...':'基于属性+剧本总结生成沉浸式背景'}
                  </button>
                  {aiErr&&<p className="text-red-500 text-xs">{aiErr}</p>}
                  {aiGen?.backstory&&(
                    <div className="bg-gray-50 rounded-lg p-3 border border-gray-200">
                      <p className="text-[10px] text-gray-500 font-medium mb-1">背景故事</p>
                      <p className="text-xs text-gray-700 leading-relaxed">{aiGen.backstory}</p>
                    </div>
                  )}
                </div>
              )}

              {gameSystem==='custom'&&(
                <div>
                  <label className="text-xs font-medium text-gray-600 mb-2">自定义属性（可在自定义规则中改名）</label>
                  <div className="grid grid-cols-2 gap-2">
                    {CUSTOM_ATTRIBUTES.map(a=>(
                      <div key={a.key} className="flex items-center gap-2 p-2 rounded-lg border border-gray-200 bg-white">
                        <span className="text-sm">{a.icon}</span>
                        <span className="text-xs font-semibold text-gray-700 w-12">{a.label}</span>
                        <input type="number" min={1} max={30} value={customAttrs[a.key]||10} onChange={e=>setCustomAttrs(p=>({...p,[a.key]:Math.max(1,Math.min(30,Number(e.target.value)||10))}))} className="input-field text-xs py-1 px-2" />
                      </div>
                    ))}
                  </div>
                  <button onClick={()=>callAI(true)} disabled={aiBusy} className="w-full py-2 bg-indigo-50 border border-indigo-200 hover:bg-indigo-100 text-indigo-700 rounded-lg text-sm font-medium transition-all disabled:opacity-50">
                    {aiBusy?'生成中...':'基于属性+剧本总结生成沉浸式背景'}
                  </button>
                  {aiErr&&<p className="text-red-500 text-xs">{aiErr}</p>}
                  {aiGen?.backstory&&(
                    <div className="bg-gray-50 rounded-lg p-3 border border-gray-200">
                      <p className="text-[10px] text-gray-500 font-medium mb-1">背景故事</p>
                      <p className="text-xs text-gray-700 leading-relaxed">{aiGen.backstory}</p>
                    </div>
                  )}
                </div>
              )}

              {/* 自行填写背景（所有规则系统通用） */}
              <div>
                <label className="block text-xs font-medium text-gray-600 mb-1">角色背景（可选，可自行填写）</label>
                <textarea value={backstoryText} onChange={e=>setBackstoryText(e.target.value)} placeholder="在这里直接写下你的角色过往；也可以留空并使用上方 AI 生成" rows={4} className="input-field resize-none" />
              </div>

              <div className="flex gap-2">
                <button onClick={()=>setStep(1)} className="flex-1 btn-secondary">← 返回剧本</button>
                <button onClick={()=>setStep(3)} className="flex-[2] btn-primary">继续 → 冒险准备</button>
              </div>
            </div>
          )}

          {/* ═══════ 步骤1: 剧本选择与生成 ═══════ */}
          {step===1&&(
            <div className="space-y-5">
              <h2 className="text-lg font-bold text-gray-900">剧本选择与生成</h2>

              {/* 剧本模式：已有 / 切分 / AI 自动生成 */}
              <div className="grid grid-cols-3 gap-2">
                {([
                  {id:'existing', label:'已有剧本', desc:'直接使用已保存剧本'},
                  {id:'split', label:'本体切分', desc:'上传剧本文件后切分生成'},
                  {id:'generate', label:'AI 自动生成', desc:'从描述生成全新剧本'},
                ] as const).map(mode=>(
                  <button key={mode.id} onClick={()=>setScenarioMode(mode.id)} className={`p-2.5 rounded-xl border text-left transition-all ${scenarioMode===mode.id?'border-indigo-400 bg-indigo-50 ring-1 ring-indigo-200':'border-gray-200 bg-white hover:border-gray-300'}`}>
                    <div className="text-xs font-bold text-gray-800">{mode.label}</div>
                    <div className="text-[9px] text-gray-500 mt-0.5">{mode.desc}</div>
                  </button>
                ))}
              </div>

              {scenarioMode==='existing'&&savedScenarios.length>0&&(
                <div className="card p-3 bg-indigo-50/50 border-indigo-200">
                  <div className="flex items-center justify-between mb-2">
                    <span className="text-xs font-medium text-indigo-700">📁 已有剧本可直接使用（跳过世界生成）</span>
                    <button onClick={()=>setShowScenarioList(!showScenarioList)} className="text-[10px] text-indigo-500 hover:text-indigo-700">{showScenarioList?'收起':'展开'}({savedScenarios.length}个)</button>
                  </div>
                  {!showScenarioList&&selectedScenario&&(
                    <p className="text-[10px] text-indigo-600">已选择: {savedScenarios.find(s=>s.id===selectedScenario)?.title||''}</p>
                  )}
                  {showScenarioList&&(
                    <div className="space-y-1 max-h-48 overflow-y-auto">
                      {savedScenarios.map(s=>(
                        <button key={s.id} onClick={()=>loadScenario(s.id)} className={`w-full text-left p-2.5 rounded-lg border text-xs transition-all ${selectedScenario===s.id?'border-indigo-400 bg-indigo-100 ring-1 ring-indigo-300':'border-gray-200 bg-white hover:border-gray-300'}`}>
                          <div className="flex justify-between items-center">
                            <span className="font-medium text-gray-800">{s.title}</span>
                            <span className={`text-[10px] px-1.5 py-0.5 rounded-full ${s.score>=80?'bg-emerald-100 text-emerald-700':'bg-amber-100 text-amber-700'}`}>{s.score}分</span>
                          </div>
                          <div className="flex gap-3 mt-1 text-[10px] text-gray-500"><span>{GAME_SYSTEM_LABELS[(s.system as GameSystem)||'dnd5e']||s.system}</span><span>{s.tone}</span><span>游玩{s.total_sessions}次</span>{s.character_name&&<span>角色:{s.character_name}</span>}</div>
                          {s.summary&&<p className="mt-1 text-[10px] text-gray-500 line-clamp-2">{s.summary}</p>}
                        </button>
                      ))}
                    </div>
                  )}
                  {selectedScenario&&(
                    <p className="mt-2 text-[10px] text-indigo-600 font-medium">✅ 已选择已有剧本——点击"继续"即可跳过世界生成</p>
                  )}
                </div>
              )}

              {scenarioMode==='generate'&&(
                <div className="space-y-4">
                  <div>
                    <label className="block text-xs font-medium text-gray-600 mb-1">世界描述</label>
                    <textarea value={worldDesc} onChange={e=>setWorldDesc(e.target.value)} placeholder="描述你想要的冒险..." rows={3} className="input-field resize-none" />
                  </div>

                  <div className="grid grid-cols-2 gap-3">
                    <div>
                      <label className="block text-xs font-medium text-gray-600 mb-1">基调</label>
                      <select
                        value={toneCustom ? '__custom__' : worldTone}
                        onChange={e=>{
                          if(e.target.value==='__custom__'){
                            setToneCustom(true);
                            if(customTone) setWorldTone(customTone);
                          } else {
                            setToneCustom(false);
                            setWorldTone(e.target.value);
                          }
                        }}
                        className="input-field"
                      >
                        {TONES.map(t=><option key={t} value={t}>{t}</option>)}
                        <option value="__custom__">自定义...</option>
                      </select>
                      {toneCustom&&(
                        <input
                          value={customTone}
                          onChange={e=>{ setCustomTone(e.target.value); setWorldTone(e.target.value); }}
                          placeholder="输入自定义基调"
                          className="input-field mt-1 text-xs"
                        />
                      )}
                    </div>
                    <div>
                      <label className="block text-xs font-medium text-gray-600 mb-1">参考剧本</label>
                      <textarea value={referenceScript} onChange={e=>setReferenceScript(e.target.value)} placeholder="粘贴参考文本..." rows={2} className="input-field resize-none" />
                    </div>
                  </div>

                  <div>
                    <label className="block text-xs font-medium text-gray-600 mb-1">备注</label>
                    <textarea value={worldNote} onChange={e=>setWorldNote(e.target.value)} placeholder="特殊规则、限制..." rows={2} className="input-field resize-none" />
                  </div>
                </div>
              )}

              {scenarioMode!=='existing'&&(
                <div className="bg-indigo-50/40 rounded-lg p-3 border border-indigo-100 space-y-2">
                  <label className="block text-xs font-medium text-gray-700 mb-1">角色规则系统（独立于剧本系统）</label>
                  <div className="grid grid-cols-2 gap-1.5">
                    {GAME_SYSTEM_OPTIONS.map(opt=>(
                      <button key={opt.id} onClick={()=>setGameSystem(opt.id)} className={`p-2 rounded-lg border text-left text-xs transition-all ${
                        gameSystem===opt.id?'border-indigo-400 bg-indigo-100 text-indigo-800':'border-gray-200 bg-white text-gray-600 hover:border-gray-300'
                      }`}>
                        <span className="font-bold">{opt.label}</span>
                        <span className="block text-[9px] opacity-70">{opt.short} · {opt.description}</span>
                      </button>
                    ))}
                  </div>
                  {gameSystem==='custom'&&(
                    <div>
                      <label className="block text-xs font-medium text-gray-600 mb-1">自定义规则</label>
                      <textarea value={customRules} onChange={e=>setCustomRules(e.target.value)} placeholder="粘贴你的自定义规则，例如属性名称、判定方式、特殊机制..." rows={3} className="input-field resize-none" />
                    </div>
                  )}
                  <p className="text-[10px] text-gray-400">生成时使用此规则系统；导入文件时也可让后端自动识别。</p>
                </div>
              )}

              {scenarioMode==='split'&&(
              <div className="bg-gray-50 rounded-lg p-3 border border-gray-200 space-y-3">
                <div>
                  <label className="block text-xs font-medium text-gray-600 mb-1">上传剧本文件（pdf / txt / docx / doc / md）</label>
                  <input
                    type="file"
                    accept=".txt,.md,.markdown,.pdf,.doc,.docx"
                    onChange={e=>{
                      const f=e.target.files?.[0];
                      if(f)importScenario(f);
                      e.target.value='';
                    }}
                    className="block w-full text-xs text-gray-500 file:mr-3 file:py-2 file:px-3 file:rounded-lg file:border-0 file:bg-indigo-50 file:text-indigo-700 file:text-xs file:font-medium hover:file:bg-indigo-100"
                  />
                  {importFileName&&<p className="text-[10px] text-gray-400 mt-1">已选择: {importFileName}</p>}
                </div>

                <div className="grid grid-cols-2 gap-3">
                  <div>
                    <label className="block text-xs font-medium text-gray-600 mb-1">切分方式</label>
                    <select value={splitter} onChange={e=>setSplitter(e.target.value as 'naive'|'semantic')} className="input-field">
                      <option value="naive">切分器（快速）</option>
                      <option value="semantic">语义切分（更连贯）</option>
                    </select>
                  </div>
                  <div>
                    <label className="block text-xs font-medium text-gray-600 mb-1">单块字数</label>
                    <input type="number" min={200} max={4000} step={100} value={chunkSize} onChange={e=>setChunkSize(Number(e.target.value)||900)} className="input-field" />
                  </div>
                </div>

                {importBusy&&<p className="text-xs text-indigo-600 animate-pulse">正在读取、切分并生成剧本（需要多次AI调用）...</p>}
                {importErr&&<p className="text-red-500 text-xs">{importErr}</p>}
              </div>
              )}

              {scenarioMode==='generate'&&!selectedScenario&&(
                <button onClick={genWorld} disabled={worldGenBusy} className="w-full btn-primary">{worldGenBusy?'正在生成世界...':'生成世界大纲'}</button>
              )}
              {scenarioMode==='existing'&&selectedScenario&&(
                <p className="text-xs text-gray-500 text-center">已加载已有剧本，无需生成。直接进入下一步。</p>
              )}

              {worldGenBusy&&(
                <div className="bg-gray-50 rounded-lg p-4 border border-gray-200 space-y-2">
                  <div className="flex items-center gap-2 text-sm font-medium text-gray-700"><span className="animate-pulse">●</span>铸造世界中</div>
                  <div className="h-1.5 bg-gray-200 rounded-full overflow-hidden"><div className="h-full bg-gradient-to-r from-indigo-500 to-purple-500 rounded-full transition-all duration-1000" style={{width:`${((worldGenStage+1)/WORLD_STAGES.length)*100}%`}}/></div>
                  <div className="space-y-0.5">
                    {WORLD_STAGES.map((st,i)=>(<div key={st.key} className={`flex items-center gap-2 text-xs ${i<worldGenStage?'text-emerald-600':i===worldGenStage?'text-indigo-600 font-medium':'text-gray-400'}`}><span>{i<worldGenStage?'✓':i===worldGenStage?'◉':'○'}</span><span>{st.label}</span>{i===worldGenStage&&<span className="text-gray-400 font-normal">— {st.desc}</span>}</div>))}
                  </div>
                </div>
              )}

              {worldGenErr&&<p className="text-red-500 text-xs">{worldGenErr}</p>}

              {worldOutline&&!worldGenBusy&&(
                <div className="space-y-2">
                  {worldScore!==null&&(
                    <div className="flex items-center gap-3 bg-gray-50 rounded-lg p-2.5 border border-gray-200">
                      <span className={`text-lg font-bold ${worldScore>=90?'text-emerald-600':worldScore>=75?'text-amber-600':'text-red-500'}`}>{worldScore}/100</span>
                      <div className="flex-1 h-1.5 bg-gray-200 rounded-full overflow-hidden"><div className={`h-full rounded-full ${worldScore>=90?'bg-emerald-500':worldScore>=75?'bg-amber-500':'bg-red-500'}`} style={{width:`${worldScore}%`}}/></div>
                    </div>
                  )}
                  {scenarioSummary&&(
                    <div className="bg-emerald-50 border border-emerald-200 rounded-lg p-3">
                      <p className="text-[10px] text-emerald-700 font-medium mb-1">📝 剧本总结（约400字）</p>
                      <p className="text-xs text-gray-700 leading-relaxed">{scenarioSummary}</p>
                    </div>
                  )}
                  <div className="flex flex-wrap gap-1">
                    <span className="text-[10px] bg-indigo-100 text-indigo-700 px-2 py-0.5 rounded-full border border-indigo-200">剧本系统：{GAME_SYSTEM_LABELS[scenarioSystem]}</span>
                    <span className="text-[10px] bg-emerald-100 text-emerald-700 px-2 py-0.5 rounded-full border border-emerald-200">角色系统：{GAME_SYSTEM_LABELS[gameSystem]}</span>
                    {gameSystem==='custom'&&customRules&&<span className="text-[10px] bg-amber-100 text-amber-700 px-2 py-0.5 rounded-full border border-amber-200">自定义规则已填写</span>}
                  </div>
                  <div className="bg-gray-50 rounded-lg p-3 border border-gray-200 max-h-64 overflow-y-auto"><pre className="text-xs text-gray-700 whitespace-pre-wrap font-sans leading-relaxed">{worldOutline.slice(0,2500)}{worldOutline.length>2500?'...':''}</pre></div>
                  {sourceChunks.length>0&&(
                    <p className="text-[10px] text-gray-400">已切分为 {sourceChunks.length} 个片段 · 切分方式: {splitter==='semantic'?'语义切分':'切分器'}</p>
                  )}
                  {scenarioId&&<p className="text-[10px] text-gray-400">已保存 · 可在下次游戏时直接加载</p>}
                </div>
              )}

              <button onClick={()=>setStep(2)} className="w-full btn-primary">继续 → 角色创建</button>
            </div>
          )}

          {/* ═══════ 步骤3: 冒险准备 ═══════ */}
          {step===3&&(
            <div className="space-y-5">
              <h2 className="text-lg font-bold text-gray-900">冒险准备</h2>

              <div>
                <label className="block text-xs font-medium text-gray-600 mb-1">额外剧本（可选）</label>
                <textarea value={scenarioText} onChange={e=>setScenarioText(e.target.value)} placeholder="粘贴自定义剧本..." rows={4} className="input-field resize-none" />
              </div>

              <div className="bg-white rounded-xl border border-gray-200 overflow-hidden">
                <div className="flex">
                  <div className="w-24 h-28 bg-gray-100 flex items-center justify-center shrink-0">
                    {characterImage?<img src={characterImage} alt="角色" className="w-full h-full object-cover" />:<span className="text-[9px] text-gray-400">暂无头像</span>}
                  </div>
                  <div className="flex-1 p-3">
                    <p className="text-sm font-bold text-gray-900">{charName||'???'}</p>
                    <p className="text-[10px] text-gray-500">{gameSystem==='coc'?`${occupation}（调查员）`:gameSystem==='custom'?'自定义角色':`${rc.name} ${cc.name} Lv.1`} · {GAME_SYSTEM_LABELS[gameSystem]}</p>
                    <div className="grid grid-cols-2 gap-x-3 gap-y-1 mt-2">
                      {gameSystem==='coc'?(
                        <>
                          <span className="text-[10px] text-gray-500">HP <b className="text-gray-800">{Math.floor(((cocAttrs.con||50)+(cocAttrs.siz||50))/2)}</b></span>
                          <span className="text-[10px] text-gray-500">MP <b className="text-gray-800">{cocAttrs.pow||50}</b></span>
                          <span className="text-[10px] text-gray-500">SAN <b className="text-gray-800">{(cocAttrs.pow||50)*5}</b></span>
                          <span className="text-[10px] text-gray-500">幸运 <b className="text-gray-800">{cocLuck}</b></span>
                        </>
                      ):(
                        <>
                          <span className="text-[10px] text-gray-500">HP <b className="text-gray-800">{gameSystem==='dnd4e'?d4Derived.hp:gameSystem==='dnd5e'?d5Derived.hp:30}</b></span>
                          <span className="text-[10px] text-gray-500">AC <b className="text-gray-800">12</b></span>
                          {gameSystem==='dnd4e'&&<span className="text-[10px] text-gray-500">回复力 <b className="text-gray-800">{d4Derived.healingSurges}</b></span>}
                          <span className="text-[10px] text-gray-500">{playMode==='lite'?'精简模式':'深度模式'}</span>
                        </>
                      )}
                    </div>
                    {gameSystem==='coc'&&cocSkillPicks.length>0&&<p className="text-[10px] text-gray-500 mt-1">技能: {cocSkillPicks.join('、')}</p>}
                    {gameSystem!=='coc'&&skillPicks.length>0&&<p className="text-[10px] text-gray-500 mt-1">技能: {skillPicks.join('、')}</p>}
                  </div>
                </div>
                <div className="border-t border-gray-200 p-3 grid grid-cols-3 gap-1.5 bg-gray-50/60">
                  {Object.entries(gameSystem==='coc'?cocAttrs:finalAttrs).map(([k,v])=>(
                    <div key={k} className="bg-white rounded border border-gray-200 px-2 py-1 flex items-center justify-between">
                      <span className="text-[9px] text-gray-400 uppercase">{k}</span>
                      <span className="text-[11px] font-bold text-gray-800">{v}</span>
                    </div>
                  ))}
                </div>
              </div>

              <div className="bg-amber-50 border border-amber-200 rounded-lg p-3">
                <p className="text-[10px] text-amber-800 font-medium mb-1">冒险规则</p>
                <ul className="text-[10px] text-amber-700 space-y-0.5">
                  {gameSystem==='dnd5e'&&<li>· D&D 5e核心规则，检定失败有真实后果</li>}
                  {gameSystem==='dnd4e'&&<li>· D&D 4e威能与防御规则，回复力决定续航</li>}
                  {gameSystem==='coc'&&<li>· COC 7e：调查员会受伤、失去理智，直面未知</li>}
                  {gameSystem==='custom'&&<li>· 自定义规则：按你提供的规则文本主持</li>}
                  <li>· 背包中没有的物品无法使用</li>
                  <li>· 角色可能受伤甚至死亡——冒险有代价</li>
                  {gameSystem==='dnd5e'&&<li>· 每2级可选择一项特长</li>}
                </ul>
              </div>

              {error&&<p className="text-red-500 text-xs">{error}</p>}

              <div className="flex gap-2">
                <button onClick={()=>setStep(2)} className="flex-1 btn-secondary">← 返回</button>
                <button onClick={start} disabled={loading} className="flex-[2] btn-primary text-base">{loading?'准备冒险中...':'开始冒险'}</button>
              </div>
            </div>
          )}

          {/* ═══════ 步骤4: 知识库 ═══════ */}
          {step===4&&(
            <div className="space-y-5">
              <div className="flex items-center justify-between">
                <h2 className="text-lg font-bold text-gray-900">知识库 / RAG 设定库</h2>
                <button onClick={seedKb} disabled={kbBusy} className="text-[10px] px-2.5 py-1 rounded-lg border border-indigo-200 bg-indigo-50 text-indigo-700 hover:bg-indigo-100">🔄 重置内置规则备注</button>
              </div>

              <div className="bg-indigo-50/40 rounded-lg p-3 border border-indigo-100">
                <p className="text-[10px] text-indigo-700 leading-relaxed">
                  知识库用于 RAG 检索：游戏中的规则细节、剧本设定、玩家备注会按需被检索并注入 AI 提示词，而不是全部塞进上下文。
                  你可以上传苹果园/克苏鲁公社的 PDF/DOCX，或直接添加文字备注。
                </p>
              </div>

              <div className="grid md:grid-cols-2 gap-4">
                {/* 添加文字备注 */}
                <div className="bg-gray-50 rounded-lg p-3 border border-gray-200 space-y-2">
                  <p className="text-xs font-medium text-gray-700">添加文字备注</p>
                  <input value={kbTitle} onChange={e=>setKbTitle(e.target.value)} placeholder="标题（可选）" className="input-field text-xs" />
                  <select value={kbSystem} onChange={e=>setKbSystem(e.target.value as GameSystem)} className="input-field text-xs">
                    {GAME_SYSTEM_OPTIONS.map(o=><option key={o.id} value={o.id}>{o.label}</option>)}
                  </select>
                  <textarea value={kbContent} onChange={e=>setKbContent(e.target.value)} placeholder="输入规则、设定、备注..." rows={4} className="input-field resize-none text-xs" />
                  <input value={kbTags} onChange={e=>setKbTags(e.target.value)} placeholder="标签，用逗号分隔" className="input-field text-xs" />
                  <button onClick={addKbNote} disabled={kbBusy || !kbContent.trim()} className="w-full py-2 bg-indigo-50 border border-indigo-200 hover:bg-indigo-100 text-indigo-700 rounded-lg text-xs font-medium disabled:opacity-50">保存到知识库</button>
                </div>

                {/* 上传文件 */}
                <div className="bg-gray-50 rounded-lg p-3 border border-gray-200 space-y-2">
                  <p className="text-xs font-medium text-gray-700">上传 PDF/DOCX/TXT/MD</p>
                  <input
                    type="file"
                    accept=".txt,.md,.markdown,.pdf,.doc,.docx"
                    onChange={e=>setKbUploadFile(e.target.files?.[0]||null)}
                    className="block w-full text-xs text-gray-500 file:mr-3 file:py-2 file:px-3 file:rounded-lg file:border-0 file:bg-indigo-50 file:text-indigo-700 file:text-xs file:font-medium"
                  />
                  <input value={kbTitle} onChange={e=>setKbTitle(e.target.value)} placeholder="标题（默认文件名）" className="input-field text-xs" />
                  <select value={kbSystem} onChange={e=>setKbSystem(e.target.value as GameSystem)} className="input-field text-xs">
                    {GAME_SYSTEM_OPTIONS.map(o=><option key={o.id} value={o.id}>{o.label}</option>)}
                  </select>
                  <input value={kbTags} onChange={e=>setKbTags(e.target.value)} placeholder="标签，用逗号分隔" className="input-field text-xs" />
                  <button onClick={()=>kbUploadFile&&uploadKb(kbUploadFile)} disabled={kbBusy || !kbUploadFile} className="w-full py-2 bg-emerald-50 border border-emerald-200 hover:bg-emerald-100 text-emerald-700 rounded-lg text-xs font-medium disabled:opacity-50">
                    {kbBusy?'处理中...':'上传到知识库'}
                  </button>
                </div>
              </div>

              {kbErr&&<p className="text-red-500 text-xs">{kbErr}</p>}

              <div className="space-y-1.5">
                <p className="text-xs font-medium text-gray-700">已有知识条目（{kbDocs.length}）</p>
                {kbDocs.length===0&&<p className="text-xs text-gray-400">暂无条目，点击上方“重置内置规则备注”或添加内容。</p>}
                {kbDocs.map(d=>(
                  <div key={d.id} className="flex items-center justify-between bg-white rounded-lg p-2.5 border border-gray-200">
                    <div className="min-w-0">
                      <p className="text-xs font-medium text-gray-800 truncate">{d.title}</p>
                      <p className="text-[10px] text-gray-500">{GAME_SYSTEM_LABELS[(d.system as GameSystem)||'custom']} · {d.source} · {d.chunk_count} 块 · {d.tags.join(' / ')||'无标签'}</p>
                    </div>
                    <button onClick={()=>deleteKb(d.id)} className="text-[10px] text-red-500 hover:text-red-700 px-2 py-1">删除</button>
                  </div>
                ))}
              </div>

              {/* 扩展包管理 */}
              <div className="border-t border-gray-200 pt-4 space-y-3">
                <p className="text-xs font-bold text-gray-800">扩展包（增强游戏性与个性）</p>
                <div className="grid md:grid-cols-2 gap-3">
                  <div className="bg-gray-50 rounded-lg p-3 border border-gray-200 space-y-2">
                    <p className="text-xs font-medium text-gray-700">手动添加扩展包</p>
                    <input value={extName} onChange={e=>setExtName(e.target.value)} placeholder="扩展包名称" className="input-field text-xs" />
                    <input value={extDesc} onChange={e=>setExtDesc(e.target.value)} placeholder="一句话简介" className="input-field text-xs" />
                    <select value={extSystem} onChange={e=>setExtSystem(e.target.value as GameSystem)} className="input-field text-xs">
                      {GAME_SYSTEM_OPTIONS.map(o=><option key={o.id} value={o.id}>{o.label}</option>)}
                    </select>
                    <textarea value={extContent} onChange={e=>setExtContent(e.target.value)} placeholder="扩展内容：规则、能力、物品、NPC、事件等" rows={4} className="input-field resize-none text-xs" />
                    <input value={extTags} onChange={e=>setExtTags(e.target.value)} placeholder="标签，用逗号分隔" className="input-field text-xs" />
                    <button onClick={addExt} disabled={extBusy || !extContent.trim()} className="w-full py-2 bg-indigo-50 border border-indigo-200 hover:bg-indigo-100 text-indigo-700 rounded-lg text-xs font-medium disabled:opacity-50">保存扩展包</button>
                  </div>
                  <div className="bg-gray-50 rounded-lg p-3 border border-gray-200 space-y-2">
                    <p className="text-xs font-medium text-gray-700">AI 生成扩展包</p>
                    <select value={extSystem} onChange={e=>setExtSystem(e.target.value as GameSystem)} className="input-field text-xs">
                      {GAME_SYSTEM_OPTIONS.map(o=><option key={o.id} value={o.id}>{o.label}</option>)}
                    </select>
                    <textarea value={extGenDesc} onChange={e=>setExtGenDesc(e.target.value)} placeholder="描述你想要的扩展包，例如：新增一个酒馆斗殴规则和三个NPC" rows={4} className="input-field resize-none text-xs" />
                    <button onClick={genExt} disabled={extBusy || !extGenDesc.trim()} className="w-full py-2 bg-emerald-50 border border-emerald-200 hover:bg-emerald-100 text-emerald-700 rounded-lg text-xs font-medium disabled:opacity-50">{extBusy?'生成中...':'让 AI 生成扩展包'}</button>
                  </div>
                </div>
                {extErr&&<p className="text-red-500 text-xs">{extErr}</p>}
                <div className="space-y-1.5">
                  <p className="text-xs font-medium text-gray-700">已有扩展包（{extList.length}）· 勾选后将在新游戏中启用</p>
                  {extList.length===0&&<p className="text-xs text-gray-400">暂无扩展包，可手动添加或让 AI 生成。</p>}
                  {extList.map(e=>(
                    <label key={e.id} className={`flex items-center justify-between bg-white rounded-lg p-2.5 border cursor-pointer ${activeExtIds.includes(e.id)?'border-indigo-300 bg-indigo-50/40':'border-gray-200'}`}>
                      <span className="min-w-0">
                        <span className="text-xs font-medium text-gray-800 truncate">{e.name}</span>
                        <span className="block text-[10px] text-gray-500">{GAME_SYSTEM_LABELS[(e.system as GameSystem)||'custom']} · {e.source} · {e.description}</span>
                      </span>
                      <span className="flex items-center gap-2">
                        <input type="checkbox" checked={activeExtIds.includes(e.id)} onChange={()=>setActiveExtIds(ids=>ids.includes(e.id)?ids.filter(x=>x!==e.id):[...ids,e.id])} />
                        <button onClick={()=>deleteExt(e.id)} className="text-[10px] text-red-500 hover:text-red-700 px-2 py-1">删除</button>
                      </span>
                    </label>
                  ))}
                </div>
              </div>

              {/* 地图管理 */}
              <div className="border-t border-gray-200 pt-4 space-y-3">
                <p className="text-xs font-bold text-gray-800">地区地图（可上传自定义地图）</p>
                <div className="grid md:grid-cols-2 gap-3">
                  <div className="bg-gray-50 rounded-lg p-3 border border-gray-200 space-y-2">
                    <input value={mapName} onChange={e=>setMapName(e.target.value)} placeholder="地图名称" className="input-field text-xs" />
                    <input value={mapDesc} onChange={e=>setMapDesc(e.target.value)} placeholder="地图简介" className="input-field text-xs" />
                    <select value={mapSystem} onChange={e=>setMapSystem(e.target.value as GameSystem)} className="input-field text-xs">
                      {GAME_SYSTEM_OPTIONS.map(o=><option key={o.id} value={o.id}>{o.label}</option>)}
                    </select>
                    <input type="file" accept=".png,.jpg,.jpeg,.webp" onChange={e=>setMapFile(e.target.files?.[0]||null)} className="block w-full text-xs" />
                    <button onClick={()=>mapFile&&uploadMap(mapFile)} disabled={mediaBusy||!mapFile} className="w-full py-2 bg-indigo-50 border border-indigo-200 hover:bg-indigo-100 text-indigo-700 rounded-lg text-xs font-medium disabled:opacity-50">上传地图</button>
                  </div>
                  <div className="space-y-1.5 max-h-48 overflow-y-auto">
                    {maps.length===0&&<p className="text-xs text-gray-400">暂无地图</p>}
                    {maps.map(m=>(
                      <div key={m.id} className="flex items-center gap-2 bg-white rounded-lg p-2 border border-gray-200">
                        {m.image_path&&<img src={m.image_path} alt={m.name} className="w-10 h-10 object-cover rounded border" />}
                        <div className="min-w-0 flex-1"><p className="text-xs font-medium truncate">{m.name}</p><p className="text-[9px] text-gray-400">{m.locations.length} 个地点</p></div>
                        <button onClick={()=>deleteMap(m.id)} className="text-[10px] text-red-500">删除</button>
                      </div>
                    ))}
                  </div>
                </div>
              </div>

              {/* 生物图鉴 */}
              <div className="border-t border-gray-200 pt-4 space-y-3">
                <p className="text-xs font-bold text-gray-800">生物图鉴（可上传自定义生物图片）</p>
                <div className="grid md:grid-cols-2 gap-3">
                  <div className="bg-gray-50 rounded-lg p-3 border border-gray-200 space-y-2">
                    <input value={beastName} onChange={e=>setBeastName(e.target.value)} placeholder="生物名称" className="input-field text-xs" />
                    <select value={beastSystem} onChange={e=>setBeastSystem(e.target.value as GameSystem)} className="input-field text-xs">
                      {GAME_SYSTEM_OPTIONS.map(o=><option key={o.id} value={o.id}>{o.label}</option>)}
                    </select>
                    <textarea value={beastDesc} onChange={e=>setBeastDesc(e.target.value)} placeholder="生物描述" rows={2} className="input-field resize-none text-xs" />
                    <input value={beastStats} onChange={e=>setBeastStats(e.target.value)} placeholder={'属性JSON，如 {"HP":20,"AC":14}'} className="input-field font-mono text-xs" />
                    <input value={beastTags} onChange={e=>setBeastTags(e.target.value)} placeholder="标签，逗号分隔" className="input-field text-xs" />
                    <input type="file" accept=".png,.jpg,.jpeg,.webp" onChange={e=>setBeastFile(e.target.files?.[0]||null)} className="block w-full text-xs" />
                    <button onClick={()=>beastFile&&uploadBeast(beastFile)} disabled={mediaBusy||!beastFile} className="w-full py-2 bg-emerald-50 border border-emerald-200 hover:bg-emerald-100 text-emerald-700 rounded-lg text-xs font-medium disabled:opacity-50">上传生物</button>
                  </div>
                  <div className="space-y-1.5 max-h-48 overflow-y-auto">
                    {bestiary.length===0&&<p className="text-xs text-gray-400">暂无生物</p>}
                    {bestiary.map(b=>(
                      <div key={b.id} className="flex items-center gap-2 bg-white rounded-lg p-2 border border-gray-200">
                        {b.image_path&&<img src={b.image_path} alt={b.name} className="w-10 h-10 object-cover rounded border" />}
                        <div className="min-w-0 flex-1"><p className="text-xs font-medium truncate">{b.name}</p><p className="text-[9px] text-gray-400">{b.system} · {Object.keys(b.stats||{}).length} 项属性</p></div>
                        <button onClick={()=>deleteBeast(b.id)} className="text-[10px] text-red-500">删除</button>
                      </div>
                    ))}
                  </div>
                </div>
              </div>

              {/* 存档管理 */}
              <div className="border-t border-gray-200 pt-4 space-y-3">
                <p className="text-xs font-bold text-gray-800">存档与载入（每轮自动存档，另可手动存档）</p>
                <div className="space-y-1.5">
                  {saves.length===0&&<p className="text-xs text-gray-400">暂无存档。开始游戏后每轮会自动存档。</p>}
                  {saves.map(s=>(
                    <div key={s.id} className="flex items-center justify-between bg-white rounded-lg p-2.5 border border-gray-200">
                      <div className="min-w-0">
                        <p className="text-xs font-medium text-gray-800">{s.label} {s.auto?'(自动)':'(手动)'}</p>
                        <p className="text-[10px] text-gray-500">{s.character_name} · {GAME_SYSTEM_LABELS[(s.game_system as GameSystem)||'dnd5e']} · {s.created_at}</p>
                      </div>
                      <button onClick={()=>loadSaveGame(s.id)} className="text-[10px] px-2 py-1 bg-indigo-50 text-indigo-700 rounded-lg border border-indigo-200 hover:bg-indigo-100">载入</button>
                    </div>
                  ))}
                </div>
              </div>
            </div>
          )}

        </div>
      </div>
      {showRulebook&&<RulebookModal onClose={()=>setShowRulebook(false)} />}
    </div>
  );
}
