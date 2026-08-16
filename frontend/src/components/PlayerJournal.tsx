/** 玩家笔记 —— 白色简洁 · 场景/NPC/剧情/角色笔记 */

import { useEffect, useState } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import { useGameStore } from '../store/gameStore';

interface CharNote { target:string;comment:string;clue?:string;turn:number; }
interface NpcView { name:string;race:string;role:string;attitude:string;alive:boolean|null;appearance:string;personality:string;motivation:string;secret:string;relation_to_plot:string;location:string;_hidden_fields:number;_fully_revealed:boolean; }
interface JournalData {
  scene:{location:string;time:string;weather:string;atmosphere:string;npcs_here:string[]};
  npcs:{allies:NpcView[];enemies:NpcView[];neutrals:NpcView[];total:number};
  plot_flags:{key:string;status:string;description:string}[];
  locations:{name:string;description:string;status:string}[];
  character_notes:{npc_notes:CharNote[];event_notes:CharNote[];quest_clues:CharNote[];location_notes:CharNote[]};
  turn_count:number;
}

function NpcCard({npc,cat}:{npc:NpcView;cat:string}){
  const [exp,setExp]=useState(false);
  const colors:Record<string,string>={ally:'border-emerald-200 bg-emerald-50/50',enemy:'border-red-200 bg-red-50/50',neutral:'border-gray-200 bg-gray-50/50'};
  const icons:Record<string,string>={ally:'🟢',enemy:'🔴',neutral:'⚪'};
  const labels:Record<string,string>={ally:'友善',enemy:'敌对',neutral:'中立'};
  return (
    <motion.div initial={{opacity:0,y:2}} animate={{opacity:1,y:0}} className={`rounded-lg border p-1.5 ${colors[cat]||colors.neutral} text-[10px]`}>
      <div className="flex items-center justify-between cursor-pointer" onClick={()=>setExp(!exp)}>
        <div className="flex items-center gap-1 min-w-0">
          <span className="text-[9px]">{icons[cat]||'⚪'}</span>
          <span className="font-medium text-gray-700 truncate">{npc.name}</span>
          {npc._hidden_fields>0&&!exp&&<span className="text-[8px] text-indigo-500 bg-indigo-50 px-1 rounded">{npc._hidden_fields}隐藏</span>}
        </div>
        <span className="text-[9px] text-gray-400">{exp?'▾':'▸'}</span>
      </div>
      <AnimatePresence>
        {exp&&<motion.div initial={{height:0}} animate={{height:'auto'}} exit={{height:0}} className="overflow-hidden">
          <div className="mt-1.5 pt-1.5 border-t border-gray-100 space-y-0.5">
            <Row k="身份" v={npc.role}/><Row k="种族" v={npc.race}/><Row k="位置" v={npc.location}/>
            <Row k="状态" v={npc.alive===false?'☠ 已故':labels[cat]}/>
            {npc.appearance&&<Row k="外貌" v={npc.appearance}/>}
            {npc.personality&&<Row k="性格" v={npc.personality} c="text-indigo-600"/>}
            {npc.motivation&&<Row k="动机" v={npc.motivation} c="text-amber-600"/>}
            {npc.secret&&<Row k="秘密" v={npc.secret} c="text-red-500"/>}
            {npc.relation_to_plot&&<Row k="关联" v={npc.relation_to_plot} c="text-blue-600"/>}
          </div>
        </motion.div>}
      </AnimatePresence>
    </motion.div>
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
          {npcs.enemies.length>0&&<div><p className="text-[9px] text-red-500 font-medium mb-1">⚔ 敌人</p>{npcs.enemies.map(n=><NpcCard key={n.name} npc={n} cat="enemy"/>)}</div>}
          {npcs.allies.length>0&&<div><p className="text-[9px] text-emerald-500 font-medium mb-1 mt-2">🤝 盟友</p>{npcs.allies.map(n=><NpcCard key={n.name} npc={n} cat="ally"/>)}</div>}
          {npcs.neutrals.length>0&&<div><p className="text-[9px] text-gray-400 font-medium mb-1 mt-2">👤 其他</p>{npcs.neutrals.map(n=><NpcCard key={n.name} npc={n} cat="neutral"/>)}</div>}
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
