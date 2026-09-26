/**
 * 角色草稿：属性点购 / COC 技能点 / 自定义属性、法术选择与 AI 生成（属性或背景）。
 *
 * 从 StartScreen 拆出：这组 26 个 state 加上点购与 COC 的派生、增减 handler、
 * 法术配额与选择逻辑共约 150 行，与"剧本工坊""开局编排"是并列的三件事。
 * 跨切面输入只有会话级设置（用户名 / 模型 / 地址）与错误提示回调。
 */
import { useCallback, useEffect, useMemo, useState } from 'react';
import {
  COC_SKILLS, COC_SKILL_BASE, getDnd4Derived, getDnd5Derived,
  rollCocAttributes, rollCocLuck, type GameSystem,
} from '../../gameSystems';
import { CLASSES, RACES, pointBuyConfig, spent, type SpellOption } from '../../data/dndData';

export function useCharacterDraft({ username, gameSystem, apiKey, modelName, baseUrl, setError }: {
  username: string;
  gameSystem: GameSystem;
  apiKey: string;
  modelName: string;
  baseUrl: string;
  setError: (msg: string) => void;
}) {

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

  const [spellPool,setSpellPool]=useState<SpellOption[]>([]);
  const [spellPicks,setSpellPicks]=useState<SpellOption[]>([]);
  const [spellPoolBusy,setSpellPoolBusy]=useState(false);

  const [cocAttrs,setCocAttrs]=useState<Record<string,number>>(()=>rollCocAttributes());
  const [occupation,setOccupation]=useState('学者');
  const [cocSkillPicks,setCocSkillPicks]=useState<string[]>([]);
  const [cocOccInc,setCocOccInc]=useState<Record<string,number>>(()=>Object.fromEntries(COC_SKILLS.map(s=>[s,0])));
  const [cocPerInc,setCocPerInc]=useState<Record<string,number>>(()=>Object.fromEntries(COC_SKILLS.map(s=>[s,0])));
  const [cocLuck,setCocLuck]=useState<number>(()=>rollCocLuck());
  const [customAttrs,setCustomAttrs]=useState<Record<string,number>>({str:10,dex:10,con:10,int:10,wis:10,cha:10});

  // 法术池（内置经典 + 知识库 SRD 自动抓取）
  useEffect(()=>{
    if(gameSystem!=='dnd5e')return;
    setSpellPoolBusy(true);
    fetch(`/api/spells?username=${encodeURIComponent(username||'default')}&scenario_id=`)
      .then(r=>r.json())
      .then(d=>setSpellPool((d.spells||[]).filter((s:SpellOption)=>s.system==='dnd5e')))
      .catch(()=>{})
      .finally(()=>setSpellPoolBusy(false));
  },[username,gameSystem]);

  // 切换职业/种族时清空已选法术，避免带入不合法选项
  useEffect(()=>{setSpellPicks([]);},[charClass,race,gameSystem]);

  const pb = pointBuyConfig(gameSystem);
  const rm=useMemo(()=>pb.total-spent(attrs, pb.cost),[attrs, pb]);
  const cocOccPool = Math.max(0, (cocAttrs.edu||50)*4);
  const cocPerPool = Math.max(0, (cocAttrs.int||50)*2);
  const cocOccSpent = COC_SKILLS.reduce((sum,s)=>sum+(cocOccInc[s]||0),0);
  const cocPerSpent = COC_SKILLS.reduce((sum,s)=>sum+(cocPerInc[s]||0),0);
  const cocOccRemain = cocOccPool - cocOccSpent;
  const cocPerRemain = cocPerPool - cocPerSpent;
  const cocSkillValues = Object.fromEntries(COC_SKILLS.map(s=>[s,(COC_SKILL_BASE[s]||0)+(cocOccInc[s]||0)+(cocPerInc[s]||0)]));
  const finalAttrs=useMemo(()=>{
    if(gameSystem==='coc') return cocAttrs;
    if(gameSystem==='custom') return customAttrs;
    return aiGen?.attributes||attrs;
  },[attrs,aiGen,gameSystem,cocAttrs,customAttrs]);
  const rc=RACES[race]||{name:race||'人类',traits:[]};
  const cc=CLASSES[charClass]||{name:charClass||'战士',pri:'str',hd:'?',profs:[]};

  const wisMod = Math.floor((Number(finalAttrs.wis ?? 10)-10)/2);
  const cantripQuota = (cc.cantrips||0) + (race==='高等精灵'?1:0) + (race==='提夫林'?1:0);
  const spellQuota = cc.prepared && cc.spells===0 ? Math.max(1, wisMod+1) : (cc.spells||0);
  const availableCantrips = spellPool.filter(s=>s.level==='0' && (
    (s.classes||[]).includes(cc.name) ||
    (race==='高等精灵'&&(s.classes||[]).includes('法师')) ||
    (race==='提夫林'&&(s.classes||[]).includes('提夫林'))
  ));
  const availableLevel1 = spellPool.filter(s=>s.level==='1' && (s.classes||[]).includes(cc.name));
  const selectedCantrips = spellPicks.filter(p=>p.level==='0');
  const selectedLevel1 = spellPicks.filter(p=>p.level!=='0');
  const toggleSpell=(spell:SpellOption)=>{
    setSpellPicks(prev=>{
      const exists=prev.some(s=>s.name===spell.name);
      if(exists)return prev.filter(s=>s.name!==spell.name);
      const isCantrip=spell.level==='0';
      if(isCantrip && selectedCantrips.length>=cantripQuota)return prev;
      if(!isCantrip && selectedLevel1.length>=spellQuota)return prev;
      return [...prev,spell];
    });
  };
  const d5Derived = getDnd5Derived(cc.name, finalAttrs, 1);
  const d4Derived = getDnd4Derived(cc.name, finalAttrs);

  const inc=useCallback((k:string)=>setAttrs(p=>{const c=p[k];if(c>=pb.max)return p;const nv=c+1;if(spent(p, pb.cost)+(pb.cost[nv]||0)-(pb.cost[c]||0)>pb.total)return p;return{...p,[k]:nv};}),[pb]);
  const dec=useCallback((k:string)=>setAttrs(p=>p[k]<=pb.min?p:{...p,[k]:p[k]-1}),[pb]);

  const incCocOcc=(name:string)=>{
    if(cocOccRemain<=0) return;
    setCocOccInc(p=>{
      const next=(p[name]||0)+1;
      if((COC_SKILL_BASE[name]||0)+next+(cocPerInc[name]||0)>75) return p;
      return {...p,[name]:next};
    });
  };
  const decCocOcc=(name:string)=>{
    setCocOccInc(p=>({...p,[name]:Math.max(0,(p[name]||0)-1)}));
  };
  const incCocPer=(name:string)=>{
    if(cocPerRemain<=0) return;
    setCocPerInc(p=>{
      const next=(p[name]||0)+1;
      if((COC_SKILL_BASE[name]||0)+(cocOccInc[name]||0)+next>75) return p;
      return {...p,[name]:next};
    });
  };
  const decCocPer=(name:string)=>{
    setCocPerInc(p=>({...p,[name]:Math.max(0,(p[name]||0)-1)}));
  };

  const toggleSkill=(name:string)=>{setSkillPicks(p=>p.includes(name)?p.filter(s=>s!==name):p.length<2?[...p,name]:p);};

  return {
    charName, setCharName, gender, setGender,
    race, setRace, charClass, setCharClass,
    attrs, setAttrs, attrMode, setAttrMode,
    backstoryText, setBackstoryText, aiGen, setAiGen,
    aiBusy, setAiBusy, aiErr, setAiErr, skillPicks, setSkillPicks,
    spellPool, spellPicks, setSpellPicks, spellPoolBusy,
    cocAttrs, setCocAttrs, occupation, setOccupation,
    cocSkillPicks, setCocSkillPicks, cocOccInc, setCocOccInc, cocPerInc, setCocPerInc,
    cocLuck, setCocLuck, customAttrs, setCustomAttrs,
    pb, rm, finalAttrs, rc,
    cc, d5Derived, d4Derived, cocOccPool,
    cocPerPool, cocOccRemain, cocPerRemain, cocSkillValues,
    cantripQuota, spellQuota, availableCantrips, availableLevel1,
    selectedCantrips, selectedLevel1, toggleSpell, inc,
    dec, incCocOcc, decCocOcc, incCocPer,
    decCocPer, toggleSkill,
  };
}
