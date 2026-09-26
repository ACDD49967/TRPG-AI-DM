/**
 * 内容库：地图 / 生物图鉴 / 法术的列表、检索、筛选、录入与批量机翻。
 *
 * 从 GameScreen 拆出：这组 24 个 state 与约 230 行 handler 只服务
 * MapModal / BeastModal / SpellModal / DmToolsModal 四个弹窗，留在主界面里
 * 会让"弹窗编排"和"内容库实现"混在一个组件。依赖只有会话信息与会话级设置。
 */
import { useEffect, useState } from 'react';
import { useMediaLibraryActions } from './useMediaLibraryActions';

type MediaItem = Record<string, any>;

export function useMediaLibrary({ sessionId, username, gameSystem, scenarioId, mediaVersion }: {
  sessionId: string;
  username: string;
  gameSystem: string;
  scenarioId: string;
  mediaVersion: number;
}) {
  /** 列表过滤用的统一小写化 */
  const q = (s: string) => s.toLowerCase();

  const [maps, setMaps] = useState<Array<{id:string;name:string;description:string;description_zh?:string;image_path:string;locations:Array<{name:string;x:number;y:number}>;system?:string;scenario_id?:string;details?:{type?:string;status?:string;culture?:string;districts?:string[];notable_figures?:string;dangers?:string;secret?:string;related_creatures?:string[];population?:string}}>>([]);
  const [bestiary, setBestiary] = useState<Array<{id:string;name:string;system:string;description:string;description_zh?:string;stats:Record<string,string>;image_path:string;tags?:string[];scenario_id?:string;details?:{habits?:string;habitat?:string;lore?:string;weakness?:string}}>>([]);
  const [beastQuery, setBeastQuery] = useState('');
  const [mapQuery, setMapQuery] = useState('');
  const [showGlobalRefMaps, setShowGlobalRefMaps] = useState(false);
  const [showGlobalRefBestiary, setShowGlobalRefBestiary] = useState(false);
  const [showGlobalRefSpells, setShowGlobalRefSpells] = useState(false);
  const [showMapBuilder, setShowMapBuilder] = useState(false);
  const [showBeastBuilder, setShowBeastBuilder] = useState(false);
  const [showSpells, setShowSpells] = useState(false);
  const [spells, setSpells] = useState<Array<{id:string;name:string;system:string;description:string;description_zh?:string;name_zh?:string;level:string;school:string;ritual:boolean;casting_time:string;range:string;components:string;duration:string;classes:string[];tags?:string[];scenario_id?:string}>>([]);
  const [spellQuery, setSpellQuery] = useState('');
  const [srdTranslating, setSrdTranslating] = useState(false);
  const [srdProgress, setSrdProgress] = useState<{done:number; total:number} | null>(null);
  const [mediaTranslate, setMediaTranslate] = useState<{kind:'locations'|'bestiary'; done:number; total:number} | null>(null);
  const [showSpellBuilder, setShowSpellBuilder] = useState(false);

  const [dmNpc, setDmNpc] = useState({ name: '', role: '', location: '', hp: 10, ac: 10, level: 1 });
  const [dmMap, setDmMap] = useState({ name: '', description: '', type: '', status: '', culture: '', districts: '', notable_figures: '', dangers: '', secret: '', locationsText: '' });
  const [dmBeast, setDmBeast] = useState({ name: '', description: '', ac: '', hp: '', speed: '', str: '', dex: '', con: '', int: '', wis: '', cha: '', skills: '', traits: '', actions: '', habits: '', habitat: '', lore: '', weakness: '', tags: '' });
  const [dmSpell, setDmSpell] = useState({ name: '', description: '', level: '0', school: '', ritual: false, casting_time: '', range: '', components: '', duration: '', classes: '' });
  const [dmNpcImage, setDmNpcImage] = useState<File | null>(null);
  const [dmMapImage, setDmMapImage] = useState<File | null>(null);
  const [dmBeastImage, setDmBeastImage] = useState<File | null>(null);

  useEffect(() => {
    const u = username;
    const sys = gameSystem || 'dnd5e';
    const sid = scenarioId || '';
    fetch(`/api/maps?username=${encodeURIComponent(u)}&scenario_id=${encodeURIComponent(sid)}`).then(r=>r.json()).then(d=>setMaps((d.maps||[]).filter((m: {system?:string})=>m.system===sys || m.system==='custom'))).catch(()=>{});
    fetch(`/api/bestiary?username=${encodeURIComponent(u)}&scenario_id=${encodeURIComponent(sid)}`).then(r=>r.json()).then(d=>setBestiary((d.bestiary||[]).filter((b: {system?:string})=>b.system===sys || b.system==='custom'))).catch(()=>{});
    fetch(`/api/spells?username=${encodeURIComponent(u)}&scenario_id=${encodeURIComponent(sid)}`).then(r=>r.json()).then(d=>setSpells((d.spells||[]).filter((s: {system?:string})=>s.system===sys || s.system==='custom'))).catch(()=>{});
  }, [username, gameSystem, scenarioId, mediaVersion]);

  const currentSid = scenarioId || '';
  const scenarioMaps = maps.filter(m => m.scenario_id === currentSid);
  const globalMaps = maps.filter(m => !m.scenario_id);
  const scenarioBestiary = bestiary.filter(b => b.scenario_id === currentSid);
  const globalBestiary = bestiary.filter(b => !b.scenario_id);
  const scenarioSpells = spells.filter(s => s.scenario_id === currentSid);
  const globalSpells = spells.filter(s => !s.scenario_id);
  // 图鉴隔离：有当前剧本时默认只看当前剧本，切换后才合并通用参考。
  const scopedMaps = currentSid
    ? (showGlobalRefMaps ? maps : scenarioMaps)
    : globalMaps;
  const scopedBestiary = currentSid
    ? (showGlobalRefBestiary ? bestiary : scenarioBestiary)
    : globalBestiary;
  const scopedSpells = currentSid
    ? (showGlobalRefSpells ? spells : scenarioSpells)
    : globalSpells;
  const filteredMaps = scopedMaps.filter(m => !mapQuery || q(`${m.name} ${m.description_zh||''} ${m.description} ${(m.locations||[]).map(l=>l.name).join(' ')} ${m.details?.type||''} ${m.details?.status||''} ${m.details?.culture||''} ${m.details?.notable_figures||''} ${m.details?.dangers||''}`).includes(q(mapQuery)));
  const filteredBestiary = scopedBestiary
    .filter(b => !beastQuery || q(`${b.name} ${b.description_zh||''} ${b.description} ${(b.tags||[]).join(' ')} ${Object.values(b.stats||{}).join(' ')} ${b.details?.habitat||''} ${b.details?.habits||''} ${b.details?.lore||''}`).includes(q(beastQuery)))
    .sort((a, b) => Number(!!b.scenario_id) - Number(!!a.scenario_id));

  // 写入动作已拆到 useMediaLibraryActions（状态与筛选留在本文件）
  const { addDmNpc, addDmMap, addDmBeast, addDmSpell, translateSrd, translateMedia } =
    useMediaLibraryActions({
      bestiary,
      dmBeast,
      dmBeastImage,
      dmMap,
      dmMapImage,
      dmNpc,
      dmNpcImage,
      dmSpell,
      maps,
      mediaTranslate,
      spells,
      srdTranslating,
      scopedMaps,
      scopedBestiary,
      gameSystem,
      scenarioId,
      sessionId,
      username,
      setDmBeast,
      setDmBeastImage,
      setDmMap,
      setDmMapImage,
      setDmNpc,
      setDmNpcImage,
      setDmSpell,
      setMediaTranslate,
      setSrdProgress,
      setSrdTranslating,
    });

  return {
    maps, setMaps, bestiary, setBestiary,
    beastQuery, setBeastQuery, mapQuery, setMapQuery,
    showGlobalRefMaps, setShowGlobalRefMaps, showGlobalRefBestiary, setShowGlobalRefBestiary,
    showGlobalRefSpells, setShowGlobalRefSpells, showMapBuilder, setShowMapBuilder,
    showBeastBuilder, setShowBeastBuilder, showSpells, setShowSpells,
    spells, setSpells, spellQuery, setSpellQuery,
    srdTranslating, srdProgress, mediaTranslate, showSpellBuilder,
    setShowSpellBuilder, dmNpc, setDmNpc, dmMap,
    setDmMap, dmBeast, setDmBeast, dmSpell,
    setDmSpell, dmNpcImage, setDmNpcImage, dmMapImage,
    setDmMapImage, dmBeastImage, setDmBeastImage, currentSid,
    scenarioMaps, globalMaps, scenarioBestiary, globalBestiary,
    scenarioSpells, globalSpells, scopedMaps, scopedBestiary,
    scopedSpells, filteredMaps, filteredBestiary, addDmNpc,
    addDmMap, addDmBeast, addDmSpell, translateSrd,
    translateMedia, q,
  };
}
