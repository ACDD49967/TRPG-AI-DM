/** 游戏主界面 —— 白色简洁布局 · 顶栏场景信息 */

import { useEffect, useState } from 'react';
import { useGameStore } from '../store/gameStore';
import { useSSE } from '../hooks/useSSE';
import NarrativeStream from './NarrativeStream';
import StatusPanel from './StatusPanel';
import PlayerJournal from './PlayerJournal';
import InputArea from './InputArea';
import Choices from './Choices';
import DiceRollOverlay from './DiceRoll';
import DecisionPanel from './DecisionPanel';
import RulebookModal from './RulebookModal';

export default function GameScreen() {
  const { sessionId, goToStart, sceneInfo, status } = useGameStore();
  useSSE(sessionId);
  const [showMap, setShowMap] = useState(false);
  const [showBeast, setShowBeast] = useState(false);
  const [showRulebook, setShowRulebook] = useState(false);
  const [showCharSheet, setShowCharSheet] = useState(false);
  const [maps, setMaps] = useState<Array<{id:string;name:string;description:string;image_path:string;locations:Array<{name:string;x:number;y:number}>;details?:{culture?:string;districts?:string[];notable_figures?:string;dangers?:string}}>>([]);
  const [bestiary, setBestiary] = useState<Array<{id:string;name:string;system:string;description:string;stats:Record<string,string>;image_path:string;details?:{habits?:string;habitat?:string;lore?:string;weakness?:string}}>>([]);

  useEffect(() => {
    const u = status.username || 'default';
    const sys = status.game_system || 'dnd5e';
    fetch(`/api/maps?username=${encodeURIComponent(u)}`).then(r=>r.json()).then(d=>setMaps((d.maps||[]).filter((m: {system?:string})=>m.system===sys || m.system==='custom'))).catch(()=>{});
    fetch(`/api/bestiary?username=${encodeURIComponent(u)}`).then(r=>r.json()).then(d=>setBestiary((d.bestiary||[]).filter((b: {system?:string})=>b.system===sys || b.system==='custom'))).catch(()=>{});
  }, [status.username, status.game_system]);

  const saveGame = async () => {
    if (!sessionId) return;
    try {
      await fetch(`/api/game/${sessionId}/save`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ label: '手动存档' }),
      });
    } catch {}
  };

  return (
    <div className="h-screen flex flex-col bg-white">
      {/* 顶栏：标题 + 场景信息 + 角色名 */}
      <header className="h-11 bg-white border-b border-gray-200 flex items-center justify-between px-4 flex-shrink-0 gap-4">
        <div className="flex items-center gap-3">
          <h1 className="text-indigo-600 font-semibold text-xs tracking-wide shrink-0">D&D 跑团</h1>
        </div>

        {/* 场景信息 */}
        <div className="flex items-center gap-4 text-[10px] flex-1 justify-center min-w-0">
          {sceneInfo.location !== '冒险的起点' && sceneInfo.location !== '未知' && (
            <span className="text-gray-700 font-medium truncate" title={sceneInfo.location}>
              地点：{sceneInfo.location}
            </span>
          )}
          <span className="text-gray-500 shrink-0">时间：{sceneInfo.time}</span>
          {sceneInfo.weather && (
            <span className="text-gray-400 truncate hidden sm:inline" title={sceneInfo.weather}>天气：{sceneInfo.weather}</span>
          )}
          {sceneInfo.npcs_here.length > 0 && (
            <span className="text-gray-500 truncate hidden md:inline">
              在场：{sceneInfo.npcs_here.slice(0, 3).join(', ')}{sceneInfo.npcs_here.length > 3 ? ` +${sceneInfo.npcs_here.length - 3}` : ''}
            </span>
          )}
        </div>

        {/* 角色信息 + 返回 */}
        <div className="flex items-center gap-3 shrink-0">
          <span className="text-[10px] text-gray-600 hidden sm:inline">
            {status.character_name || '冒险者'}
            {status.race && <span className="text-gray-400"> · {status.race} {status.char_class}</span>}
          </span>
          <span className="text-[10px] text-gray-700 font-medium">
            HP {status.hp}/{status.maxHp}
          </span>
          <span className="text-[10px] text-gray-400 font-mono hidden sm:inline">#{sessionId?.slice(0, 6)}</span>
          <button onClick={()=>setShowRulebook(true)} className="text-xs text-indigo-500 hover:text-indigo-700 transition-colors">说明书</button>
          <button onClick={()=>setShowCharSheet(true)} className="text-xs text-gray-500 hover:text-gray-700 transition-colors">角色卡</button>
          <button onClick={()=>setShowMap(true)} className="text-xs text-gray-500 hover:text-gray-700 transition-colors">地图</button>
          <button onClick={()=>setShowBeast(true)} className="text-xs text-gray-500 hover:text-gray-700 transition-colors">图鉴</button>
          <button onClick={saveGame} className="text-xs text-gray-500 hover:text-gray-700 transition-colors">存档</button>
          <button onClick={goToStart} className="text-xs text-gray-500 hover:text-gray-700 transition-colors">载入</button>
          <button onClick={goToStart} className="text-xs text-gray-500 hover:text-gray-700 transition-colors">新游戏</button>
          <button onClick={goToStart} className="text-xs text-gray-400 hover:text-gray-600 transition-colors">大厅</button>
        </div>
      </header>

      <div className="flex flex-1 min-h-0">
        <StatusPanel />
        <div className="flex-1 flex flex-col min-w-0 border-x border-gray-200">
          <NarrativeStream />
          <DecisionPanel />
          <Choices />
          <InputArea />
        </div>
        <PlayerJournal />
      </div>
      <DiceRollOverlay />

      {showCharSheet && (
        <div className="fixed inset-0 z-[60] bg-black/40 flex items-center justify-center p-4" onClick={()=>setShowCharSheet(false)}>
          <div className="bg-white rounded-2xl max-w-md w-full max-h-[85vh] overflow-y-auto p-5" onClick={e=>e.stopPropagation()}>
            <div className="flex items-center justify-between mb-3">
              <h3 className="text-sm font-bold text-gray-900">角色卡</h3>
              <button onClick={()=>setShowCharSheet(false)} className="text-xs text-gray-400 hover:text-gray-600">关闭</button>
            </div>
            <div className="flex items-center gap-3 mb-3">
              {status.character_image ? <img src={status.character_image} alt="角色" className="w-20 h-20 object-cover rounded-xl border border-gray-200" /> : <div className="w-20 h-20 bg-gray-100 rounded-xl flex items-center justify-center text-[9px] text-gray-400">暂无头像</div>}
              <div>
                <p className="text-base font-bold">{status.character_name||'冒险者'}</p>
                <p className="text-[10px] text-gray-500">{status.race||'?'} {status.char_class||'?'} · {status.game_system||'dnd5e'}</p>
              </div>
            </div>
            <div className="grid grid-cols-3 gap-2 mb-3">
              <div className="bg-gray-50 rounded-lg p-2 text-center"><p className="text-[9px] text-gray-400">HP</p><p className="text-sm font-bold">{status.hp}/{status.maxHp}</p></div>
              <div className="bg-gray-50 rounded-lg p-2 text-center"><p className="text-[9px] text-gray-400">AC</p><p className="text-sm font-bold">{status.ac}</p></div>
              <div className="bg-gray-50 rounded-lg p-2 text-center"><p className="text-[9px] text-gray-400">等级</p><p className="text-sm font-bold">{status.level}</p></div>
            </div>
            <div className="grid grid-cols-2 gap-1.5">
              {Object.entries(status.attributes||{}).map(([k,v])=>(
                <div key={k} className="bg-white rounded-lg border border-gray-200 px-2 py-1 flex justify-between"><span className="text-[10px] text-gray-400 uppercase">{k}</span><span className="text-xs font-bold">{v}</span></div>
              ))}
            </div>
            {status.inventory?.length>0&&<div className="mt-3"><p className="text-[10px] text-gray-400 mb-1">背包</p><div className="flex flex-wrap gap-1">{status.inventory.map((it,i)=><span key={i} className="text-[10px] bg-gray-50 border border-gray-200 rounded px-1.5 py-0.5">{it}</span>)}</div></div>}
          </div>
        </div>
      )}

      {showRulebook && <RulebookModal onClose={()=>setShowRulebook(false)} />}

      {showMap && (
        <div className="fixed inset-0 z-50 bg-black/40 flex items-center justify-center p-4" onClick={()=>setShowMap(false)}>
          <div className="bg-white rounded-xl max-w-2xl w-full max-h-[85vh] overflow-y-auto p-4" onClick={e=>e.stopPropagation()}>
            <div className="flex items-center justify-between mb-3">
              <h3 className="text-sm font-bold text-gray-900">地区地图</h3>
              <button onClick={()=>setShowMap(false)} className="text-xs text-gray-400 hover:text-gray-600">关闭</button>
            </div>
            {maps.length===0&&<p className="text-xs text-gray-400">暂无地图，可在大厅知识库页上传。</p>}
            {maps.map(m=>(
              <div key={m.id} className="mb-4 border border-gray-200 rounded-lg overflow-hidden">
                {m.image_path&&<img src={m.image_path} alt={m.name} className="w-full max-h-80 object-contain bg-gray-100" />}
                <div className="p-3">
                  <p className="text-sm font-bold">{m.name}</p>
                  <p className="text-[10px] text-gray-500 mb-2">{m.description}</p>
                  {m.locations.length>0&&<div className="flex flex-wrap gap-1">{m.locations.map((l,i)=><span key={i} className="text-[10px] bg-indigo-50 text-indigo-700 px-2 py-0.5 rounded-full border border-indigo-100">{l.name}</span>)}</div>}
                  {m.details && (
                    <div className="mt-2 text-[10px] text-gray-600 space-y-1">
                      {m.details.culture&&<p>文化：{m.details.culture}</p>}
                      {m.details.districts && m.details.districts.length>0&&<p>区域：{m.details.districts.join('、')}</p>}
                      {m.details.notable_figures&&<p>知名人物：{m.details.notable_figures}</p>}
                      {m.details.dangers&&<p>危险：{m.details.dangers}</p>}
                    </div>
                  )}
                </div>
              </div>
            ))}
          </div>
        </div>
      )}

      {showBeast && (
        <div className="fixed inset-0 z-50 bg-black/40 flex items-center justify-center p-4" onClick={()=>setShowBeast(false)}>
          <div className="bg-white rounded-xl max-w-2xl w-full max-h-[85vh] overflow-y-auto p-4" onClick={e=>e.stopPropagation()}>
            <div className="flex items-center justify-between mb-3">
              <h3 className="text-sm font-bold text-gray-900">生物图鉴</h3>
              <button onClick={()=>setShowBeast(false)} className="text-xs text-gray-400 hover:text-gray-600">关闭</button>
            </div>
            {bestiary.length===0&&<p className="text-xs text-gray-400">暂无生物，可在大厅知识库页上传。</p>}
            {bestiary.map(b=>(
              <div key={b.id} className="flex gap-3 mb-3 border border-gray-200 rounded-lg p-2">
                {b.image_path&&<img src={b.image_path} alt={b.name} className="w-16 h-16 object-cover rounded-lg border" />}
                <div className="min-w-0">
                  <p className="text-sm font-bold">{b.name}</p>
                  <p className="text-[10px] text-gray-500">{b.system}</p>
                  <p className="text-[10px] text-gray-600 mt-0.5">{b.description}</p>
                  {Object.keys(b.stats||{}).length>0&&<p className="text-[10px] text-gray-500 mt-1">{Object.entries(b.stats||{}).map(([k,v])=>`${k}:${v}`).join(' · ')}</p>}
                  {b.details && (
                    <div className="text-[10px] text-gray-600 mt-1 space-y-0.5">
                      {b.details.habits&&<p>习性：{b.details.habits}</p>}
                      {b.details.habitat&&<p>栖息地：{b.details.habitat}</p>}
                      {b.details.lore&&<p>传说：{b.details.lore}</p>}
                      {b.details.weakness&&<p>弱点：{b.details.weakness}</p>}
                    </div>
                  )}
                </div>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}
