/** 玩家笔记 —— 白色简洁 · 场景/NPC/剧情/角色笔记 */

import { useEffect, useState } from 'react';
import { useGameStore } from '../store/gameStore';

interface CharNote { target:string;comment:string;clue?:string;turn:number; }
interface NpcView { name:string;race:string;role:string;attitude:string;alive:boolean|null;appearance:string;personality:string;motivation:string;secret:string;relation_to_plot:string;location:string;level?:number;ac?:number;hp?:number;max_hp?:number;attributes?:Record<string,number>;skills?:string[];traits?:string[];image_path?:string;_hidden_fields:number;_fully_revealed:boolean; }
interface JournalData {
  scene:{location:string;time:string;weather:string;atmosphere:string;npcs_here:string[]};
  npcs:{allies:NpcView[];enemies:NpcView[];neutrals:NpcView[];total:number};
  plot_flags:{key:string;status:string;description:string}[];
  locations:{name:string;description:string;status:string}[];
  character_notes:{npc_notes:CharNote[];event_notes:CharNote[];quest_clues:CharNote[];location_notes:CharNote[]};
  turn_count:number;
}

function NpcCard({npc,cat}:{npc:NpcView;cat:string}){
  const colors:Record<string,string>={ally:'border-emerald-200 bg-emerald-50/40',enemy:'border-red-200 bg-red-50/40',neutral:'border-gray-200 bg-gray-50/60'};
  const labels:Record<string,string>={ally:'友善',enemy:'敌对',neutral:'中立'};
  const attrNames:Record<string,string>={str:'力量',dex:'敏捷',con:'体质',int:'智力',wis:'感知',cha:'魅力',pow:'意志',siz:'体型',edu:'教育'};
  const mod = (v: number) => `${Math.floor((v - 10) / 2) >= 0 ? '+' : ''}${Math.floor((v - 10) / 2)}`;
  return (
    <details className={`group rounded-lg border p-1.5 ${colors[cat]||colors.neutral} text-[10px]`}>
      <summary className="cursor-pointer select-none list-none">
        <div className="flex items-center justify-between gap-1">
          <div className="flex items-center gap-1 min-w-0">
            {npc.image_path ? <img src={npc.image_path} alt={npc.name} className="w-5 h-5 rounded object-cover border border-gray-200" /> : <span className="w-1.5 h-1.5 rounded-full bg-current opacity-40" />}
            <span className="font-bold text-gray-800 truncate">{npc.name}</span>
            {npc._hidden_fields>0&&<span className="text-[8px] text-indigo-500 bg-indigo-50 px-1 rounded shrink-0">{npc._hidden_fields}隐藏</span>}
          </div>
          <span className="text-[9px] text-gray-400 shrink-0">HP {npc.hp}/{npc.max_hp} · AC {npc.ac} <span className="group-open:hidden">▸</span><span className="hidden group-open:inline">▾</span></span>
        </div>
      </summary>

      {/* D&D 官方 NPC 卡样式 */}
      <div className="mt-1.5 pt-1.5 border-t-2 border-amber-900/60 bg-[#fffdf5] rounded px-2 py-1.5">
        <p className="text-center font-bold text-gray-900">{npc.name}</p>
        <p className="text-center text-[8px] text-gray-500 italic">
          {npc.role||'未知身份'}{npc.race&&npc.race!=='???'?` · ${npc.race}`:''} · {npc.alive===false?'已故':labels[cat]}
        </p>
        <div className="my-1 border-t border-amber-900/60" />
        <div className="flex justify-between gap-1 text-[9px]">
          <span><b className="text-gray-500">护甲等级</b> <b>{npc.ac}</b></span>
          <span><b className="text-gray-500">生命值</b> <b>{npc.hp}/{npc.max_hp}</b></span>
          <span><b className="text-gray-500">等级</b> <b>{npc.level}</b></span>
        </div>
        {npc.location&&<p className="text-[9px] text-gray-500 mt-0.5">位置：{npc.location}</p>}
        {npc.attributes && Object.keys(npc.attributes).length>0 && (
          <>
            <div className="my-1 border-t border-amber-900/60" />
            <div className="grid grid-cols-3 gap-x-1 gap-y-0.5">
              {Object.entries(npc.attributes).map(([k,v])=>(
                <div key={k} className="text-center leading-tight">
                  <p className="text-[7px] uppercase tracking-wide text-gray-400">{attrNames[k]||k}</p>
                  <p className="text-[11px] font-bold">{v}<span className="ml-0.5 text-[8px] text-gray-500">({mod(Number(v))})</span></p>
                </div>
              ))}
            </div>
          </>
        )}
        {npc.skills && npc.skills.length>0 && (
          <><div className="my-1 border-t border-amber-900/60" /><p className="text-[9px]"><span className="font-bold text-gray-500">技能 </span>{npc.skills.join('、')}</p></>
        )}
        {npc.traits && npc.traits.length>0 && (
          <><div className="my-1 border-t border-amber-900/60" /><p className="text-[8px] font-bold text-gray-500">特性 / 动作</p>{npc.traits.map((t,i)=><p key={i} className="text-[9px] text-gray-700">· {t}</p>)}</>
        )}
        <div className="my-1 border-t border-amber-900/60" />
        <Row k="外貌" v={npc.appearance}/>
        <Row k="性格" v={npc.personality} c="text-indigo-600"/>
        <Row k="动机" v={npc.motivation} c="text-amber-600"/>
        <Row k="秘密" v={npc.secret} c="text-red-500"/>
        <Row k="关联" v={npc.relation_to_plot} c="text-blue-600"/>
      </div>
    </details>
  );
}
function Row({k,v,c}:{k:string;v:string;c?:string}){
  if(!v)return null;
  const hidden=v==='???';
  return <div className="flex gap-1"><span className="text-gray-400 shrink-0">{k}:</span><span className={c||(hidden?'text-gray-300 italic':'text-gray-600')}>{hidden?'???' :v}</span></div>;
}

export default function PlayerJournal(){
  const storeJournalData = useGameStore(s => s.journalData);
  const {sessionId,isProcessing}=useGameStore();
  const [j,setJ]=useState<JournalData|null>(null);
  const [tab,setTab]=useState<'npcs'|'plot'|'places'|'notes'>('npcs');

  // P2-12修复：优先使用SSE推送的journalData；fallback到API轮询
  useEffect(() => {
    if (storeJournalData) {
      setJ(storeJournalData as unknown as JournalData);
    }
  }, [storeJournalData]);

  // Fallback: SSE不可用时仍做API轮询
  useEffect(()=>{
    if(sessionId && !storeJournalData){fetch(`/api/game/${sessionId}/journal`).then(r=>r.json()).then(setJ).catch(()=>{});}
  },[sessionId]);
  useEffect(()=>{if(!isProcessing&&sessionId&&!storeJournalData){fetch(`/api/game/${sessionId}/journal`).then(r=>r.json()).then(setJ).catch(()=>{});}},[isProcessing,sessionId]);

  if(!j)return null;
  const {npcs}=j;

  return (
    <div className="w-64 bg-gray-50/80 border-l border-gray-200 flex flex-col overflow-hidden">
      {/* 标题栏 */}
      <div className="p-2.5 border-b border-gray-200">
        <div className="flex items-center gap-1.5 text-[10px]">
          <span className="text-indigo-600 font-bold">冒险笔记</span>
          {j.turn_count>0&&<span className="text-gray-400">第{j.turn_count}轮</span>}
        </div>
        {j.scene?.atmosphere && <p className="text-[9px] text-gray-400 italic mt-0.5">{j.scene.atmosphere}</p>}
      </div>

      {/* Tabs */}
      <div className="flex border-b border-gray-200 text-[10px]">
        {['npcs','plot','places','notes'].map(t=>(
          <button key={t} onClick={()=>setTab(t as typeof tab)} className={`flex-1 py-1.5 text-center ${tab===t?'text-indigo-600 border-b-2 border-indigo-500 bg-indigo-50/50':'text-gray-400 hover:text-gray-600'}`}>
            {{npcs:`角色(${npcs.total})`,plot:'剧情',places:'地点',notes:'笔记'}[t]}
          </button>
        ))}
      </div>

      {/* Content */}
      <div className="flex-1 overflow-y-auto p-2 space-y-1">
        {tab==='npcs'&&(<>
          {npcs.enemies.length>0&&<div><p className="text-[9px] text-red-500 font-medium mb-1">敌人</p>{npcs.enemies.map(n=><NpcCard key={n.name} npc={n} cat="enemy"/>)}</div>}
          {npcs.allies.length>0&&<div><p className="text-[9px] text-emerald-500 font-medium mb-1 mt-2">盟友</p>{npcs.allies.map(n=><NpcCard key={n.name} npc={n} cat="ally"/>)}</div>}
          {npcs.neutrals.length>0&&<div><p className="text-[9px] text-gray-400 font-medium mb-1 mt-2">其他</p>{npcs.neutrals.map(n=><NpcCard key={n.name} npc={n} cat="neutral"/>)}</div>}
        </>)}
        {tab==='plot'&&<div className="space-y-1">{j.plot_flags.map(f=><div key={f.key} className="bg-white rounded-lg p-1.5 border border-gray-100 text-[10px]"><div className="flex items-center gap-1"><span className={f.status==='已完成'?'text-emerald-500':f.status==='进行中'?'text-blue-500':'text-gray-400'}>●</span><span className="text-gray-700 font-medium">{f.key}</span></div>{f.description&&<p className="text-gray-400 mt-0.5 ml-3">{f.description}</p>}</div>)}</div>}
        {tab==='places'&&<div className="space-y-1">{j.locations.map(l=><div key={l.name} className="bg-white rounded-lg p-1.5 border border-gray-100 text-[10px]"><p className="text-gray-700 font-medium">{l.name}</p>{l.description&&<p className="text-gray-400 mt-0.5">{l.description}</p>}</div>)}</div>}
        {tab==='notes'&&(
          <div className="space-y-2">
            {j.character_notes?.quest_clues?.length>0&&<div><p className="text-[9px] text-amber-600 font-medium mb-1">🎯 线索</p>{j.character_notes.quest_clues.map((n,i)=><div key={i} className="bg-amber-50 border border-amber-100 rounded-lg p-1.5 mb-1 text-[10px]"><p className="text-amber-800 font-medium">{n.target}</p>{n.comment&&<p className="text-amber-700/70 mt-0.5 italic">"{n.comment}"</p>}{n.clue&&<p className="text-gray-500 mt-0.5">🔍 {n.clue}</p>}</div>)}</div>}
            {j.character_notes?.npc_notes?.length>0&&<div><p className="text-[9px] text-emerald-600 font-medium mb-1 mt-2">👤 印象</p>{j.character_notes.npc_notes.map((n,i)=><div key={i} className="bg-emerald-50 border border-emerald-100 rounded-lg p-1.5 mb-1 text-[10px]"><p className="text-emerald-800 font-medium">{n.target}</p>{n.comment&&<p className="text-emerald-700/70 mt-0.5 italic">"{n.comment}"</p>}</div>)}</div>}
          </div>
        )}
      </div>
    </div>
  );
}
