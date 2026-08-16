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
  const { sessionId, goToStart, sceneInfo, status, mediaVersion } = useGameStore();
  useSSE(sessionId);
  const [showMap, setShowMap] = useState(false);
  const [showBeast, setShowBeast] = useState(false);
  const [showRulebook, setShowRulebook] = useState(false);
  const [showCharSheet, setShowCharSheet] = useState(false);
  const [maps, setMaps] = useState<Array<{id:string;name:string;description:string;image_path:string;locations:Array<{name:string;x:number;y:number}>;details?:{culture?:string;districts?:string[];notable_figures?:string;dangers?:string}}>>([]);
  const [bestiary, setBestiary] = useState<Array<{id:string;name:string;system:string;description:string;stats:Record<string,string>;image_path:string;tags?:string[];details?:{habits?:string;habitat?:string;lore?:string;weakness?:string}}>>([]);
  const [beastQuery, setBeastQuery] = useState('');
  const [mapQuery, setMapQuery] = useState('');

  useEffect(() => {
    const u = status.username || 'default';
    const sys = status.game_system || 'dnd5e';
    const sid = status.scenario_id || '';
    fetch(`/api/maps?username=${encodeURIComponent(u)}&scenario_id=${encodeURIComponent(sid)}`).then(r=>r.json()).then(d=>setMaps((d.maps||[]).filter((m: {system?:string})=>m.system===sys || m.system==='custom'))).catch(()=>{});
    fetch(`/api/bestiary?username=${encodeURIComponent(u)}&scenario_id=${encodeURIComponent(sid)}`).then(r=>r.json()).then(d=>setBestiary((d.bestiary||[]).filter((b: {system?:string})=>b.system===sys || b.system==='custom'))).catch(()=>{});
  }, [status.username, status.game_system, status.scenario_id, mediaVersion]);

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

  const q = (s: string) => s.toLowerCase();
  const filteredMaps = maps.filter(m => !mapQuery || q(`${m.name} ${m.description} ${(m.locations||[]).map(l=>l.name).join(' ')}`).includes(q(mapQuery)));
  const filteredBestiary = bestiary.filter(b => !beastQuery || q(`${b.name} ${b.description} ${(b.tags||[]).join(' ')} ${Object.values(b.stats||{}).join(' ')} ${b.details?.habitat||''} ${b.details?.habits||''}`).includes(q(beastQuery)));

  return (
    <div className="h-screen flex flex-col bg-white">
      {/* 顶栏：标题 + 场景信息 + 角色名 */}
      <header className="h-11 bg-white border-b border-gray-200 flex items-center justify-between px-4 flex-shrink-0 gap-4">
        <div className="flex items-center gap-3">
          <h1 className="text-indigo-600 font-semibold text-xs tracking-wide shrink-0">TRPG 跑团</h1>
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
          <div className="bg-white rounded-2xl max-w-2xl w-full max-h-[85vh] overflow-y-auto p-5" onClick={e=>e.stopPropagation()}>
            <div className="flex items-center justify-between mb-3">
              <h3 className="text-sm font-bold text-gray-900">角色卡</h3>
              <button onClick={()=>setShowCharSheet(false)} className="text-xs text-gray-400 hover:text-gray-600">关闭</button>
            </div>

            {/* 身份 */}
            <div className="flex items-center gap-3 mb-4">
              {status.character_image ? <img src={status.character_image} alt="角色" className="w-20 h-20 object-cover rounded-xl border border-gray-200" /> : <div className="w-20 h-20 bg-gray-100 rounded-xl flex items-center justify-center text-[9px] text-gray-400">暂无头像</div>}
              <div>
                <p className="text-base font-bold">{status.character_name||'冒险者'}</p>
                <p className="text-[10px] text-gray-500">{status.race||'?'} {status.char_class||'?'} · {status.game_system||'dnd5e'}</p>
                {status.hit_die && <p className="text-[10px] text-gray-400">生命骰：{status.hit_die}</p>}
              </div>
            </div>

            {/* 核心数值 */}
            <div className="grid grid-cols-4 gap-2 mb-4">
              <div className="bg-gray-50 rounded-lg p-2 text-center"><p className="text-[9px] text-gray-400">HP</p><p className="text-sm font-bold">{status.hp}/{status.maxHp}</p></div>
              <div className="bg-gray-50 rounded-lg p-2 text-center"><p className="text-[9px] text-gray-400">AC</p><p className="text-sm font-bold">{status.ac}</p></div>
              <div className="bg-gray-50 rounded-lg p-2 text-center"><p className="text-[9px] text-gray-400">等级</p><p className="text-sm font-bold">{status.level}</p></div>
              <div className="bg-gray-50 rounded-lg p-2 text-center"><p className="text-[9px] text-gray-400">经验</p><p className="text-sm font-bold">{status.xp}</p></div>
              {status.game_system==='coc' && (
                <>
                  <div className="bg-gray-50 rounded-lg p-2 text-center"><p className="text-[9px] text-gray-400">MP</p><p className="text-sm font-bold">{status.mp}/{status.maxMp}</p></div>
                  <div className="bg-gray-50 rounded-lg p-2 text-center"><p className="text-[9px] text-gray-400">SAN</p><p className="text-sm font-bold">{status.san}/{status.maxSan}</p></div>
                  <div className="bg-gray-50 rounded-lg p-2 text-center"><p className="text-[9px] text-gray-400">幸运</p><p className="text-sm font-bold">{status.luck}</p></div>
                  <div className="bg-gray-50 rounded-lg p-2 text-center"><p className="text-[9px] text-gray-400">伤害加值</p><p className="text-sm font-bold">{status.damage_bonus||'0'}</p></div>
                </>
              )}
              {status.game_system==='dnd4e' && (
                <>
                  <div className="bg-gray-50 rounded-lg p-2 text-center"><p className="text-[9px] text-gray-400">回复力</p><p className="text-sm font-bold">{status.healing_surges}/{status.max_healing_surges}</p></div>
                  <div className="bg-gray-50 rounded-lg p-2 text-center"><p className="text-[9px] text-gray-400">回复量</p><p className="text-sm font-bold">{status.surge_value}</p></div>
                  <div className="bg-gray-50 rounded-lg p-2 text-center"><p className="text-[9px] text-gray-400">强韧/反射/意志</p><p className="text-sm font-bold">{status.fortitude}/{status.reflex}/{status.will}</p></div>
                  <div className="bg-gray-50 rounded-lg p-2 text-center"><p className="text-[9px] text-gray-400">熟练加值</p><p className="text-sm font-bold">{status.proficiency_bonus||2}</p></div>
                </>
              )}
              {status.game_system==='dnd5e' && (
                <>
                  <div className="bg-gray-50 rounded-lg p-2 text-center"><p className="text-[9px] text-gray-400">MP</p><p className="text-sm font-bold">{status.mp}/{status.maxMp}</p></div>
                  <div className="bg-gray-50 rounded-lg p-2 text-center"><p className="text-[9px] text-gray-400">熟练加值</p><p className="text-sm font-bold">{status.proficiency_bonus||2}</p></div>
                  <div className="bg-gray-50 rounded-lg p-2 text-center"><p className="text-[9px] text-gray-400">金币</p><p className="text-sm font-bold">{status.gold}</p></div>
                  <div className="bg-gray-50 rounded-lg p-2 text-center"><p className="text-[9px] text-gray-400">法术位</p><p className="text-sm font-bold">{(() => {
                    const ss = status.spell_slots;
                    if (Array.isArray(ss)) return ss.join('/');
                    if (ss && typeof ss === 'object') {
                      const arr = (ss as { spell_slots?: number[] }).spell_slots;
                      const pact = (ss as { pact_slots?: number }).pact_slots;
                      const parts: string[] = [];
                      if (Array.isArray(arr)) parts.push(arr.join('/'));
                      if (pact) parts.push(`契约${pact}`);
                      return parts.join(' · ') || '-';
                    }
                    return '-';
                  })()}</p></div>
                </>
              )}
            </div>

            {/* 属性 */}
            <div className="mb-4">
              <p className="text-[10px] text-gray-400 font-medium mb-1">属性</p>
              <div className="grid grid-cols-2 sm:grid-cols-3 gap-1.5">
                {Object.entries(status.attributes||{}).map(([k,v])=>{
                  const m=Math.floor((Number(v)-10)/2);
                  return (
                    <div key={k} className="bg-white rounded-lg border border-gray-200 px-2 py-1 flex justify-between">
                      <span className="text-[10px] text-gray-400 uppercase">{k}</span>
                      <span className="text-xs font-bold">{v}{status.game_system!=='coc' && <span className={`ml-1 text-[9px] ${m>=0?'text-emerald-500':'text-red-400'}`}>({m>=0?'+':''}{m})</span>}</span>
                    </div>
                  );
                })}
              </div>
            </div>

            {/* 技能 / 特长 / 特性 */}
            {((status.skill_proficiencies?.length ?? 0)>0 || (status.feats?.length ?? 0)>0 || (status.race_traits?.length ?? 0)>0 || (status.class_proficiencies?.length ?? 0)>0) && (
              <div className="space-y-2 mb-4">
                {status.skill_proficiencies && status.skill_proficiencies.length>0 && (
                  <div><p className="text-[10px] text-gray-400 font-medium mb-1">技能熟练</p><div className="flex flex-wrap gap-1">{status.skill_proficiencies.map((s,i)=><span key={i} className="text-[10px] bg-indigo-50 text-indigo-700 border border-indigo-100 rounded px-1.5 py-0.5">{s}</span>)}</div></div>
                )}
                {status.feats && status.feats.length>0 && (
                  <div><p className="text-[10px] text-gray-400 font-medium mb-1">特长</p><div className="space-y-1">{status.feats.map((f,i)=><div key={i} className="text-[10px] bg-amber-50 text-amber-800 border border-amber-200 rounded px-2 py-1">{f.name}{f.description?`：${f.description}`:''}</div>)}</div></div>
                )}
                {status.race_traits && status.race_traits.length>0 && (
                  <div><p className="text-[10px] text-gray-400 font-medium mb-1">种族特性</p><div className="flex flex-wrap gap-1">{status.race_traits.map((s,i)=><span key={i} className="text-[10px] bg-gray-100 text-gray-700 border border-gray-200 rounded px-1.5 py-0.5">{s}</span>)}</div></div>
                )}
                {status.class_proficiencies && status.class_proficiencies.length>0 && (
                  <div><p className="text-[10px] text-gray-400 font-medium mb-1">职业熟练</p><div className="flex flex-wrap gap-1">{status.class_proficiencies.map((s,i)=><span key={i} className="text-[10px] bg-gray-100 text-gray-700 border border-gray-200 rounded px-1.5 py-0.5">{s}</span>)}</div></div>
                )}
              </div>
            )}

            {/* 剧本专属 / 额外属性 */}
            {((status.custom_classes?.length ?? 0)>0 || (status.custom_skills?.length ?? 0)>0 || (status.extra_attributes && Object.keys(status.extra_attributes).length>0)) && (
              <div className="space-y-2 mb-4">
                {status.custom_classes && status.custom_classes.length>0 && (
                  <div><p className="text-[10px] text-gray-400 font-medium mb-1">剧本专属职业/身份</p><div className="flex flex-wrap gap-1">{status.custom_classes.map((s,i)=><span key={i} className="text-[10px] bg-purple-50 text-purple-700 border border-purple-200 rounded px-1.5 py-0.5">{s}</span>)}</div></div>
                )}
                {status.custom_skills && status.custom_skills.length>0 && (
                  <div><p className="text-[10px] text-gray-400 font-medium mb-1">剧本专属技能</p><div className="flex flex-wrap gap-1">{status.custom_skills.map((s,i)=><span key={i} className="text-[10px] bg-purple-50 text-purple-700 border border-purple-200 rounded px-1.5 py-0.5">{s}</span>)}</div></div>
                )}
                {status.extra_attributes && Object.keys(status.extra_attributes).length>0 && (
                  <div><p className="text-[10px] text-gray-400 font-medium mb-1">额外属性</p><div className="flex flex-wrap gap-1">{Object.entries(status.extra_attributes).map(([k,v],i)=><span key={i} className="text-[10px] bg-gray-100 text-gray-700 border border-gray-200 rounded px-1.5 py-0.5">{k}: {v}</span>)}</div></div>
                )}
              </div>
            )}

            {/* 背景故事 */}
            {status.backstory && (
              <div className="mb-4">
                <p className="text-[10px] text-gray-400 font-medium mb-1">背景故事</p>
                <p className="text-xs text-gray-700 whitespace-pre-wrap leading-relaxed">{status.backstory}</p>
              </div>
            )}

            {/* 背包 */}
            {status.inventory?.length>0 && (
              <div className="mb-4">
                <p className="text-[10px] text-gray-400 font-medium mb-1">背包</p>
                <div className="flex flex-wrap gap-1">{status.inventory.map((it,i)=><span key={i} className="text-[10px] bg-gray-50 border border-gray-200 rounded px-1.5 py-0.5">{it}</span>)}</div>
              </div>
            )}
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
            <input value={mapQuery} onChange={e=>setMapQuery(e.target.value)} placeholder="搜索地点/区域..." className="input-field text-xs mb-3" />
            {filteredMaps.length===0&&<p className="text-xs text-gray-400">暂无匹配地图。</p>}
            {filteredMaps.map(m=>{
              const relatedCreatures = bestiary.filter(b => q(`${b.description} ${b.details?.habitat||''} ${b.details?.lore||''}`).includes(q(m.name)));
              return (
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
                    {relatedCreatures.length>0 && (
                      <div className="mt-2 pt-2 border-t border-gray-100">
                        <p className="text-[9px] text-gray-400 mb-1">可能出现的生物</p>
                        <div className="flex flex-wrap gap-1">{relatedCreatures.map(b=><span key={b.id} className="text-[10px] bg-emerald-50 text-emerald-700 border border-emerald-200 rounded px-1.5 py-0.5">{b.name}</span>)}</div>
                      </div>
                    )}
                  </div>
                </div>
              );
            })}
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
            <input value={beastQuery} onChange={e=>setBeastQuery(e.target.value)} placeholder="搜索生物/属性/栖息地..." className="input-field text-xs mb-3" />
            {filteredBestiary.length===0&&<p className="text-xs text-gray-400">暂无匹配生物。</p>}
            {filteredBestiary.map(b=>{
              const relatedMaps = maps.filter(m => q(`${b.details?.habitat||''} ${b.description} ${b.details?.lore||''}`).includes(q(m.name)) || q(m.description).includes(q(b.name)));
              return (
                <div key={b.id} className="flex gap-3 mb-3 border border-gray-200 rounded-lg p-2">
                  {b.image_path&&<img src={b.image_path} alt={b.name} className="w-16 h-16 object-cover rounded-lg border" />}
                  <div className="min-w-0 flex-1">
                    <p className="text-sm font-bold">{b.name}</p>
                    <p className="text-[10px] text-gray-500">{b.system}{b.tags&&b.tags.length>0?` · ${b.tags.join('、')}`:''}</p>
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
                    {relatedMaps.length>0 && (
                      <div className="mt-1 pt-1 border-t border-gray-100">
                        <p className="text-[9px] text-gray-400 mb-0.5">关联地点</p>
                        <div className="flex flex-wrap gap-1">{relatedMaps.map(m=><span key={m.id} className="text-[10px] bg-indigo-50 text-indigo-700 border border-indigo-200 rounded px-1.5 py-0.5">{m.name}</span>)}</div>
                      </div>
                    )}
                  </div>
                </div>
              );
            })}
          </div>
        </div>
      )}
    </div>
  );
}
