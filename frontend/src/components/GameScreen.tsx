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
import DndCharacterSheet from './DndCharacterSheet';
import CocInvestigatorSheet from './CocInvestigatorSheet';

function invName(it: string | { name: string }): string {
  return typeof it === 'string' ? it : it.name || '未知物品';
}

const ATTR_CN: Record<string, string> = {
  str: '力量', dex: '敏捷', con: '体质', int: '智力', wis: '感知', cha: '魅力',
  pow: '意志', siz: '体型', edu: '教育',
};
const SIZE_CN: Record<string, string> = { T: '微型', S: '小型', M: '中型', L: '大型', H: '超大型', G: '巨型' };
const TYPE_CN: Record<string, string> = {
  humanoid: '类人生物', monstrosity: '怪物', dragon: '龙', beast: '野兽', undead: '亡灵',
  fiend: '邪魔', celestial: '天界生物', construct: '构装体', elemental: '元素生物',
  fey: '妖精', giant: '巨人', ooze: '泥怪', plant: '植物', aberration: '异怪',
};
function crToXp(cr: string): string {
  const table: Record<string, number> = {
    '0': 10, '1/8': 25, '1/4': 50, '1/2': 100, '1': 200, '2': 450, '3': 700,
    '4': 1100, '5': 1800, '6': 2300, '7': 2900, '8': 3900, '9': 5000,
    '10': 5900, '11': 7200, '12': 8400, '13': 10000, '14': 11500, '15': 13000,
    '16': 15000, '17': 18000, '18': 20000, '19': 22000, '20': 25000,
  };
  return String(table[String(cr).trim()] ?? '—');
}

function translateMonsterDesc(desc: string): string {
  return desc
    .replace(/\b(T|S|M|L|H|G)\b/g, m => SIZE_CN[m] || m)
    .replace(/\b(humanoid|monstrosity|dragon|beast|undead|fiend|celestial|construct|elemental|fey|giant|ooze|plant|aberration)\b/g, m => TYPE_CN[m] || m);
}

export default function GameScreen() {
  const { sessionId, goToStart, sceneInfo, status, mediaVersion } = useGameStore();
  const isDndSheet = status.game_system === 'dnd5e' || status.game_system === 'dnd4e';
  useSSE(sessionId);
  const [showMap, setShowMap] = useState(false);
  const [showBeast, setShowBeast] = useState(false);
  const [showRulebook, setShowRulebook] = useState(false);
  const [showCharSheet, setShowCharSheet] = useState(false);
  const [maps, setMaps] = useState<Array<{id:string;name:string;description:string;image_path:string;locations:Array<{name:string;x:number;y:number}>;details?:{culture?:string;districts?:string[];notable_figures?:string;dangers?:string}}>>([]);
  const [bestiary, setBestiary] = useState<Array<{id:string;name:string;system:string;description:string;stats:Record<string,string>;image_path:string;tags?:string[];details?:{habits?:string;habitat?:string;lore?:string;weakness?:string}}>>([]);
  const [beastQuery, setBeastQuery] = useState('');
  const [mapQuery, setMapQuery] = useState('');
  const [showDmTools, setShowDmTools] = useState(false);
  const [dmNpc, setDmNpc] = useState({ name: '', role: '', location: '', hp: 10, ac: 10, level: 1 });
  const [dmMap, setDmMap] = useState({ name: '', description: '' });
  const [dmBeast, setDmBeast] = useState({ name: '', description: '', stats: '' });
  const [dmNpcImage, setDmNpcImage] = useState<File | null>(null);
  const [dmMapImage, setDmMapImage] = useState<File | null>(null);
  const [dmBeastImage, setDmBeastImage] = useState<File | null>(null);

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

  const addDmNpc = async () => {
    if (!sessionId || !dmNpc.name.trim()) return;
    try {
      const r = await fetch(`/api/game/${sessionId}/npc`, {
        method: 'POST', headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(dmNpc),
      });
      if (!r.ok) return;
      if (dmNpcImage) {
        const fd = new FormData();
        fd.append('npc_name', dmNpc.name.trim());
        fd.append('file', dmNpcImage);
        await fetch(`/api/game/${sessionId}/npc/image`, { method: 'POST', body: fd });
      }
      setDmNpc({ name: '', role: '', location: '', hp: 10, ac: 10, level: 1 });
      setDmNpcImage(null);
    } catch {}
  };
  const addDmMap = async () => {
    if (!dmMap.name.trim()) return;
    try {
      const u = status.username || 'default';
      const sid = status.scenario_id || '';
      const sys = status.game_system || 'custom';
      if (dmMapImage) {
        const fd = new FormData();
        fd.append('file', dmMapImage);
        fd.append('username', u);
        fd.append('name', dmMap.name.trim());
        fd.append('description', dmMap.description);
        fd.append('system', sys);
        fd.append('scenario_id', sid);
        await fetch('/api/maps/upload', { method: 'POST', body: fd });
      } else {
        await fetch('/api/maps', {
          method: 'POST', headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ username: u, name: dmMap.name, description: dmMap.description, system: sys, scenario_id: sid }),
        });
      }
      setDmMap({ name: '', description: '' });
      setDmMapImage(null);
      useGameStore.getState().bumpMediaVersion();
    } catch {}
  };
  const addDmBeast = async () => {
    if (!dmBeast.name.trim()) return;
    try {
      const u = status.username || 'default';
      const sid = status.scenario_id || '';
      const sys = status.game_system || 'custom';
      let stats: Record<string,string> = {};
      try { stats = dmBeast.stats ? JSON.parse(dmBeast.stats) : {}; } catch {}
      if (dmBeastImage) {
        const fd = new FormData();
        fd.append('file', dmBeastImage);
        fd.append('username', u);
        fd.append('name', dmBeast.name.trim());
        fd.append('description', dmBeast.description);
        fd.append('system', sys);
        fd.append('stats', JSON.stringify(stats));
        fd.append('scenario_id', sid);
        await fetch('/api/bestiary/upload', { method: 'POST', body: fd });
      } else {
        await fetch('/api/bestiary', {
          method: 'POST', headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ username: u, name: dmBeast.name, description: dmBeast.description, system: sys, stats, scenario_id: sid }),
        });
      }
      setDmBeast({ name: '', description: '', stats: '' });
      setDmBeastImage(null);
      useGameStore.getState().bumpMediaVersion();
    } catch {}
  };

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
          <button onClick={()=>setShowDmTools(true)} className="text-xs text-amber-600 hover:text-amber-800 transition-colors">DM</button>
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
          {isDndSheet ? (
            <DndCharacterSheet onClose={()=>setShowCharSheet(false)} />
          ) : (status.game_system as string) === 'coc' ? (
            <CocInvestigatorSheet onClose={()=>setShowCharSheet(false)} />
          ) : (
          <div className="paper-card rounded-2xl max-w-2xl w-full max-h-[85vh] overflow-y-auto p-5" onClick={e=>e.stopPropagation()}>
            <div className="flex items-center justify-between mb-3">
              <h3 className="paper-title text-lg font-bold text-gray-900">角色卡</h3>
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
                {Object.entries(status.attributes||{})
                  .filter(([k]) => status.game_system === 'coc'
                    ? ['str','con','dex','int','pow','cha','siz','edu'].includes(k)
                    : ['str','dex','con','int','wis','cha'].includes(k))
                  .map(([k,v])=>{
                    const m=Math.floor((Number(v)-10)/2);
                    return (
                      <div key={k} className="bg-white rounded-lg border border-gray-200 px-2 py-1 flex justify-between">
                        <span className="text-[10px] text-gray-400">{ATTR_CN[k]||k.toUpperCase()}</span>
                        <span className="text-xs font-bold">{v}{status.game_system!=='coc' && <span className={`ml-1 text-[9px] ${m>=0?'text-emerald-500':'text-red-400'}`}>({m>=0?'+':''}{m})</span>}</span>
                      </div>
                    );
                  })}
              </div>
            </div>

            {/* 技能 / 特长 / 特性 */}
            {((status.skill_proficiencies?.length ?? 0)>0 || (status.feats?.length ?? 0)>0 || (status.race_traits?.length ?? 0)>0 || (status.class_proficiencies?.length ?? 0)>0) && (
              <div className="space-y-2 mb-4">
                {status.skills && Object.keys(status.skills).length>0 && (
                  <div><p className="text-[10px] text-gray-400 font-medium mb-1">技能数值</p><div className="flex flex-wrap gap-1">{Object.entries(status.skills).map(([k,v])=><span key={k} className="text-[10px] bg-indigo-50 text-indigo-700 border border-indigo-100 rounded px-1.5 py-0.5">{k}: {v}</span>)}</div></div>
                )}
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
                <div className="flex flex-wrap gap-1">{status.inventory.map((it,i)=><span key={i} className="text-[10px] bg-gray-50 border border-gray-200 rounded px-1.5 py-0.5">{invName(it)}</span>)}</div>
              </div>
            )}
          </div>
          )}
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
          <div className="paper-card rounded-xl max-w-2xl w-full max-h-[85vh] overflow-y-auto p-4" onClick={e=>e.stopPropagation()}>
            <div className="flex items-center justify-between mb-3">
              <h3 className="text-sm font-bold text-gray-900">生物图鉴</h3>
              <button onClick={()=>setShowBeast(false)} className="text-xs text-gray-400 hover:text-gray-600">关闭</button>
            </div>
            <input value={beastQuery} onChange={e=>setBeastQuery(e.target.value)} placeholder="搜索生物/属性/栖息地..." className="input-field text-xs mb-3" />
            {filteredBestiary.length===0&&<p className="text-xs text-gray-400">暂无匹配生物。</p>}
            {filteredBestiary.map(b=>{
              const relatedMaps = maps.filter(m => q(`${b.details?.habitat||''} ${b.description} ${b.details?.lore||''}`).includes(q(m.name)) || q(m.description).includes(q(b.name)));
              const s = b.stats || {};
              const get = (...keys: string[]) => keys.map(k=>s[k]).find(v=>v!==undefined && v!=='') ?? '—';
              const abilities: Array<[string,string]> = [
                ['力量', get('力量','STR','str')], ['敏捷', get('敏捷','DEX','dex')],
                ['体质', get('体质','CON','con')], ['智力', get('智力','INT','int')],
                ['感知', get('感知','WIS','wis')], ['魅力', get('魅力','CHA','cha')],
              ];
              const skills = get('技能','Skills','skills');
              const senses = get('感官','Senses','senses');
              const languages = get('语言','Languages','languages');
              const challenge = get('挑战等级','挑战','CR','cr');
              const xp = crToXp(challenge);
              const dexStat = Number(get('敏捷','DEX','dex'));
              const initiative = Number.isFinite(dexStat) && dexStat !== 0 ? `${Math.floor((dexStat - 10) / 2) >= 0 ? '+' : ''}${Math.floor((dexStat - 10) / 2)}` : '—';
              const traits = get('特性','Traits','traits');
              const actions = get('动作','Actions','actions');
              return (
                <div key={b.id} className="mb-4 border-2 border-amber-900/30 rounded-lg p-3 bg-[#fffdf5] shadow-sm">
                  <div className="flex items-start gap-3">
                    {b.image_path&&<img src={b.image_path} alt={b.name} className="w-20 h-20 object-cover rounded-lg border border-amber-900/20" />}
                    <div className="min-w-0 flex-1">
                      <p className="paper-title text-base font-bold text-gray-900">{b.name}</p>
                      <p className="text-[10px] text-gray-500 italic">{b.system}{b.tags&&b.tags.length>0?` · ${b.tags.join('、')}`:''}</p>
                      <div className="grid grid-cols-3 gap-1 mt-1.5 text-[10px]">
                        <div className="bg-amber-50 border border-amber-200 rounded px-1.5 py-0.5"><span className="text-gray-500">AC</span> <b>{get('AC','ac','护甲')}</b></div>
                        <div className="bg-amber-50 border border-amber-200 rounded px-1.5 py-0.5"><span className="text-gray-500">HP</span> <b>{get('HP','hp','生命')}</b></div>
                        <div className="bg-amber-50 border border-amber-200 rounded px-1.5 py-0.5"><span className="text-gray-500">速度</span> <b>{get('速度','Speed','speed')}</b></div>
                      </div>
                    </div>
                  </div>

                  {/* D&D4e 关键数值 */}
                  {b.system === 'dnd4e' && (
                    <div className="grid grid-cols-3 gap-1 mt-2 border-t border-amber-900/10 pt-2 text-[10px]">
                      <div className="bg-white border border-amber-900/10 rounded px-1.5 py-0.5"><span className="text-gray-400">强韧</span> <b>{get('强韧','Fortitude','fort')}</b></div>
                      <div className="bg-white border border-amber-900/10 rounded px-1.5 py-0.5"><span className="text-gray-400">反射</span> <b>{get('反射','Reflex','ref')}</b></div>
                      <div className="bg-white border border-amber-900/10 rounded px-1.5 py-0.5"><span className="text-gray-400">意志</span> <b>{get('意志','Will','will')}</b></div>
                      <div className="bg-white border border-amber-900/10 rounded px-1.5 py-0.5"><span className="text-gray-400">等级</span> <b>{get('等级','Level','level')}</b></div>
                      <div className="bg-white border border-amber-900/10 rounded px-1.5 py-0.5"><span className="text-gray-400">XP</span> <b>{get('XP','xp')}</b></div>
                      <div className="bg-white border border-amber-900/10 rounded px-1.5 py-0.5"><span className="text-gray-400">角色</span> <b>{get('角色类型','role')}</b></div>
                    </div>
                  )}

                  {/* 六维 / COC 关键数值 */}
                  {b.system === 'coc' ? (
                    <div className="grid grid-cols-2 gap-1 mt-2 border-t border-amber-900/10 pt-2">
                      <div className="bg-white border border-amber-900/10 rounded px-1.5 py-0.5"><span className="text-[8px] text-gray-400">HP</span> <b className="text-xs">{get('HP','hp','生命')}</b></div>
                      <div className="bg-white border border-amber-900/10 rounded px-1.5 py-0.5"><span className="text-[8px] text-gray-400">MP</span> <b className="text-xs">{get('MP','mp','魔法')}</b></div>
                      <div className="bg-white border border-amber-900/10 rounded px-1.5 py-0.5"><span className="text-[8px] text-gray-400">伤害加值</span> <b className="text-xs">{get('伤害加值','DB','damage_bonus')}</b></div>
                      <div className="bg-white border border-amber-900/10 rounded px-1.5 py-0.5"><span className="text-[8px] text-gray-400">护甲</span> <b className="text-xs">{get('护甲','装甲','armor')}</b></div>
                      <div className="bg-white border border-amber-900/10 rounded px-1.5 py-0.5 col-span-2"><span className="text-[8px] text-gray-400">技能</span> <b className="text-xs">{get('技能','Skills','skills')}</b></div>
                      <div className="bg-white border border-amber-900/10 rounded px-1.5 py-0.5 col-span-2"><span className="text-[8px] text-gray-400">理智损失</span> <b className="text-xs">{get('理智损失','SAN Loss','sanity')}</b></div>
                    </div>
                  ) : (
                    <div className="grid grid-cols-3 gap-1 mt-2 border-t border-amber-900/10 pt-2">
                      {abilities.map(([k,v])=>(
                        <div key={k} className="bg-white border border-amber-900/10 rounded px-1.5 py-0.5 text-center">
                          <span className="text-[8px] text-gray-400 font-semibold">{k}</span>
                          <div className="text-xs font-bold">{v}</div>
                        </div>
                      ))}
                    </div>
                  )}

                  {/* 标准字段 */}
                  {(skills!=='—'||senses!=='—'||languages!=='—'||challenge!=='—'||xp!=='—'||initiative!=='—') && (
                    <div className="mt-2 border-t border-amber-900/10 pt-1.5 space-y-0.5 text-[10px] text-gray-700">
                      {initiative!=='—'&&<p><span className="text-gray-500 font-medium">先攻：</span>{initiative}</p>}
                      {skills!=='—'&&<p><span className="text-gray-500 font-medium">技能：</span>{skills}</p>}
                      {senses!=='—'&&<p><span className="text-gray-500 font-medium">感官：</span>{senses}</p>}
                      {languages!=='—'&&<p><span className="text-gray-500 font-medium">语言：</span>{languages}</p>}
                      {challenge!=='—'&&<p><span className="text-gray-500 font-medium">挑战等级：</span>{challenge} {xp!=='—'?`（XP ${xp}）`:''}</p>}
                    </div>
                  )}

                  {/* 描述 / 特性 / 动作 */}
                  {b.description&&<p className="mt-2 text-[10px] text-gray-600 italic leading-relaxed">{translateMonsterDesc(b.description)}</p>}
                  {(traits!=='—'||actions!=='—') && (
                    <div className="mt-2 border-t border-amber-900/10 pt-1.5 space-y-1 text-[10px] text-gray-700">
                      {traits!=='—'&&<p><span className="text-gray-500 font-medium">特性：</span>{traits}</p>}
                      {actions!=='—'&&<p><span className="text-gray-500 font-medium">动作：</span>{actions}</p>}
                    </div>
                  )}
                  {b.details && (
                    <div className="mt-2 border-t border-amber-900/10 pt-1.5 space-y-0.5 text-[10px] text-gray-600">
                      {b.details.habits&&<p>习性：{b.details.habits}</p>}
                      {b.details.habitat&&<p>栖息地：{b.details.habitat}</p>}
                      {b.details.lore&&<p>传说：{b.details.lore}</p>}
                      {b.details.weakness&&<p>弱点：{b.details.weakness}</p>}
                    </div>
                  )}
                  {relatedMaps.length>0 && (
                    <div className="mt-2 pt-1.5 border-t border-amber-900/10">
                      <p className="text-[9px] text-gray-400 mb-0.5">关联地点</p>
                      <div className="flex flex-wrap gap-1">{relatedMaps.map(m=><span key={m.id} className="text-[10px] bg-indigo-50 text-indigo-700 border border-indigo-200 rounded px-1.5 py-0.5">{m.name}</span>)}</div>
                    </div>
                  )}
                </div>
              );
            })}
          </div>
        </div>
      )}

      {/* DM 工具：新增角色/地点/生物 */}
      {showDmTools && (
        <div className="fixed inset-0 z-[70] bg-black/40 flex items-center justify-center p-4" onClick={()=>setShowDmTools(false)}>
          <div className="paper-card rounded-2xl max-w-lg w-full max-h-[85vh] overflow-y-auto p-5" onClick={e=>e.stopPropagation()}>
            <div className="flex items-center justify-between mb-3">
              <h3 className="paper-title text-lg font-bold">DM 工具</h3>
              <button onClick={()=>setShowDmTools(false)} className="text-xs text-gray-400 hover:text-gray-600">关闭</button>
            </div>

            {/* 新增角色/NPC */}
            <div className="mb-4 border-b border-amber-900/10 pb-3">
              <p className="text-xs font-bold text-gray-700 mb-2">新增角色 / NPC</p>
              <div className="grid grid-cols-2 gap-2">
                <input value={dmNpc.name} onChange={e=>setDmNpc({...dmNpc,name:e.target.value})} placeholder="名称 *" className="input-field text-xs" />
                <input value={dmNpc.role} onChange={e=>setDmNpc({...dmNpc,role:e.target.value})} placeholder="身份" className="input-field text-xs" />
                <input value={dmNpc.location} onChange={e=>setDmNpc({...dmNpc,location:e.target.value})} placeholder="位置" className="input-field text-xs" />
                <div className="flex gap-2">
                  <input type="number" value={dmNpc.hp} onChange={e=>setDmNpc({...dmNpc,hp:Number(e.target.value)||10})} placeholder="HP" className="input-field text-xs" />
                  <input type="number" value={dmNpc.ac} onChange={e=>setDmNpc({...dmNpc,ac:Number(e.target.value)||10})} placeholder="AC" className="input-field text-xs" />
                </div>
              </div>
              <input type="file" accept=".png,.jpg,.jpeg,.webp" onChange={e=>setDmNpcImage(e.target.files?.[0]||null)} className="block w-full text-[10px] mt-2 text-gray-500" />
              <button onClick={addDmNpc} className="mt-2 text-xs px-3 py-1.5 bg-amber-50 text-amber-700 rounded-lg border border-amber-200 hover:bg-amber-100">新增角色</button>
            </div>

            {/* 新增地点 */}
            <div className="mb-4 border-b border-amber-900/10 pb-3">
              <p className="text-xs font-bold text-gray-700 mb-2">新增地点</p>
              <div className="grid grid-cols-1 gap-2">
                <input value={dmMap.name} onChange={e=>setDmMap({...dmMap,name:e.target.value})} placeholder="地点名称 *" className="input-field text-xs" />
                <textarea value={dmMap.description} onChange={e=>setDmMap({...dmMap,description:e.target.value})} placeholder="描述" rows={2} className="input-field text-xs resize-none" />
              </div>
              <input type="file" accept=".png,.jpg,.jpeg,.webp" onChange={e=>setDmMapImage(e.target.files?.[0]||null)} className="block w-full text-[10px] mt-2 text-gray-500" />
              <button onClick={addDmMap} className="mt-2 text-xs px-3 py-1.5 bg-amber-50 text-amber-700 rounded-lg border border-amber-200 hover:bg-amber-100">新增地点</button>
            </div>

            {/* 新增生物 */}
            <div>
              <p className="text-xs font-bold text-gray-700 mb-2">新增生物</p>
              <div className="grid grid-cols-1 gap-2">
                <input value={dmBeast.name} onChange={e=>setDmBeast({...dmBeast,name:e.target.value})} placeholder="生物名称 *" className="input-field text-xs" />
                <textarea value={dmBeast.description} onChange={e=>setDmBeast({...dmBeast,description:e.target.value})} placeholder="描述" rows={2} className="input-field text-xs resize-none" />
                <textarea value={dmBeast.stats} onChange={e=>setDmBeast({...dmBeast,stats:e.target.value})} placeholder='数值 JSON，如 {"HP":"30","AC":"15","力量":"16"}' rows={2} className="input-field text-xs resize-none font-mono" />
              </div>
              <input type="file" accept=".png,.jpg,.jpeg,.webp" onChange={e=>setDmBeastImage(e.target.files?.[0]||null)} className="block w-full text-[10px] mt-2 text-gray-500" />
              <button onClick={addDmBeast} className="mt-2 text-xs px-3 py-1.5 bg-amber-50 text-amber-700 rounded-lg border border-amber-200 hover:bg-amber-100">新增生物</button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
