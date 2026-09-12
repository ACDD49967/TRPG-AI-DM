/** 游戏主界面 —— 三栏布局（状态 / 叙事 / 笔记），移动端折叠为抽屉 */

import { useEffect, useMemo, useRef, useState } from 'react';
import { useGameStore } from '../store/gameStore';
import { useToastStore } from '../store/toastStore';
import { useSSE } from '../hooks/useSSE';
import NarrativeStream from './NarrativeStream';
import StatusPanel from './StatusPanel';
import PlayerJournal from './PlayerJournal';
import InputArea from './InputArea';
import Choices from './Choices';
import CombatLogPanel from './CombatLogPanel';
import DiceRollOverlay from './DiceRoll';
import DecisionPanel from './DecisionPanel';
import RulebookModal from './RulebookModal';
import SpellCard from './SpellCard';
import DndCharacterSheet from './DndCharacterSheet';
import CocInvestigatorSheet from './CocInvestigatorSheet';
import Modal from './ui/Modal';
import ProgressBar from './ui/ProgressBar';
import EmptyState from './ui/EmptyState';
import { getXpDisplay } from '../gameSystems';
import { textValue } from '../utils/textValue';

function invName(it: string | { name: string }): string {
  return typeof it === 'string' ? it : it.name || '未知物品';
}

type GraphNode = { id: string; type: string; label: string; extra?: string };
type GraphEdge = { source: string; target: string; relation: string; strength?: number; confidence?: number; notes?: string };

const GRAPH_COLORS: Record<string, string> = {
  npc: '#c7d2fe', location: '#bbf7d0', plot: '#fde68a', creature: '#fecaca', other: '#e5e7eb',
};
const GRAPH_TYPE_LABELS: Record<string, string> = {
  npc: '角色', location: '地点', plot: '剧情', creature: '生物', other: '其他',
};
const GRAPH_W = 1200;
const GRAPH_H = 800;

/** 简单的力导向布局：限制节点数后自动分散，减少重叠与连线密集感。 */
function computeGraphLayout(nodes: GraphNode[], edges: GraphEdge[], focusId?: string | null): Map<string, { x: number; y: number }> {
  const W = GRAPH_W, H = GRAPH_H, cx = W / 2, cy = H / 2;
  const result = new Map<string, { x: number; y: number }>();
  if (!nodes.length) return result;
  const n = nodes.length;
  const pos = nodes.map((node, i) => {
    if (focusId && node.id === focusId) return { id: node.id, x: cx, y: cy };
    const a = (i / Math.max(1, n)) * Math.PI * 2;
    return { id: node.id, x: cx + Math.cos(a) * 320, y: cy + Math.sin(a) * 250 };
  });
  const index = new Map(pos.map((p, i) => [p.id, i]));
  const area = W * H;
  const k = Math.sqrt(area / Math.max(1, n)) * 0.9;
  for (let iter = 0; iter < 120; iter++) {
    const disp = pos.map(() => ({ x: 0, y: 0 }));
    for (let i = 0; i < n; i++) {
      for (let j = i + 1; j < n; j++) {
        let dx = pos[i].x - pos[j].x;
        let dy = pos[i].y - pos[j].y;
        const dist = Math.sqrt(dx * dx + dy * dy) || 1;
        const force = (k * k) / dist;
        dx /= dist; dy /= dist;
        disp[i].x += dx * force; disp[i].y += dy * force;
        disp[j].x -= dx * force; disp[j].y -= dy * force;
      }
    }
    for (const e of edges) {
      const i = index.get(e.source), j = index.get(e.target);
      if (i === undefined || j === undefined) continue;
      let dx = pos[i].x - pos[j].x;
      let dy = pos[i].y - pos[j].y;
      const dist = Math.sqrt(dx * dx + dy * dy) || 1;
      const force = ((dist * dist) / k) * 0.6;
      dx /= dist; dy /= dist;
      disp[i].x -= dx * force; disp[i].y -= dy * force;
      disp[j].x += dx * force; disp[j].y += dy * force;
    }
    for (let i = 0; i < n; i++) {
      const isFocus = !!focusId && pos[i].id === focusId;
      disp[i].x += (cx - pos[i].x) * (isFocus ? 0.12 : 0.015);
      disp[i].y += (cy - pos[i].y) * (isFocus ? 0.12 : 0.015);
    }
    const temp = Math.max(2, 22 * (1 - iter / 120));
    for (let i = 0; i < n; i++) {
      const d = Math.sqrt(disp[i].x ** 2 + disp[i].y ** 2) || 1;
      pos[i].x += (disp[i].x / d) * Math.min(d, temp);
      pos[i].y += (disp[i].y / d) * Math.min(d, temp);
    }
  }
  const xs = pos.map(p => p.x), ys = pos.map(p => p.y);
  const minX = Math.min(...xs), maxX = Math.max(...xs), minY = Math.min(...ys), maxY = Math.max(...ys);
  const spanX = Math.max(1, maxX - minX), spanY = Math.max(1, maxY - minY);
  const scale = Math.min((W - 180) / spanX, (H - 180) / spanY, 1.15);
  const offsetX = (W - spanX * scale) / 2 - minX * scale;
  const offsetY = (H - spanY * scale) / 2 - minY * scale;
  pos.forEach(p => result.set(p.id, { x: p.x * scale + offsetX, y: p.y * scale + offsetY }));
  const focusPos = focusId ? result.get(focusId) : undefined;
  if (focusPos) {
    const dx = cx - focusPos.x, dy = cy - focusPos.y;
    result.forEach((v, id) => result.set(id, { x: v.x + dx, y: v.y + dy }));
    // 聚焦重定心后做一次边界收敛，避免节点被 viewBox 裁掉。
    result.forEach((v, id) => result.set(id, {
      x: Math.max(50, Math.min(W - 50, v.x)),
      y: Math.max(50, Math.min(H - 50, v.y)),
    }));
  }
  return result;
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
  /** 移动端抽屉：状态 / 笔记（桌面端三栏常驻，不需要抽屉） */
  const [mobilePanel, setMobilePanel] = useState<'status' | 'journal' | null>(null);
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
  const [showDmTools, setShowDmTools] = useState(false);
  const [showGraph, setShowGraph] = useState(false);
  const [graphData, setGraphData] = useState<{ nodes: GraphNode[]; edges: GraphEdge[] } | null>(null);
  const [graphQuery, setGraphQuery] = useState('');
  const [graphTypeFilter, setGraphTypeFilter] = useState<'all' | 'npc' | 'location' | 'plot' | 'creature' | 'other'>('all');
  const [graphFocusId, setGraphFocusId] = useState<string | null>(null);
  const [graphHoverId, setGraphHoverId] = useState<string | null>(null);
  const [graphZoom, setGraphZoom] = useState(1);
  const [graphPan, setGraphPan] = useState({ x: 0, y: 0 });
  const graphSvgRef = useRef<SVGSVGElement | null>(null);
  const graphDragRef = useRef<{ dragging: boolean; startX: number; startY: number; startPanX: number; startPanY: number; moved: boolean } | null>(null);
  const graphSuppressClickRef = useRef(false);
  const [graphSearchIds, setGraphSearchIds] = useState<string[]>([]);
  const [graphSearchEmpty, setGraphSearchEmpty] = useState(false);
  const [dmNpc, setDmNpc] = useState({ name: '', role: '', location: '', hp: 10, ac: 10, level: 1 });
  const [dmMap, setDmMap] = useState({ name: '', description: '', type: '', status: '', culture: '', districts: '', notable_figures: '', dangers: '', secret: '', locationsText: '' });
  const [dmBeast, setDmBeast] = useState({ name: '', description: '', ac: '', hp: '', speed: '', str: '', dex: '', con: '', int: '', wis: '', cha: '', skills: '', traits: '', actions: '', habits: '', habitat: '', lore: '', weakness: '', tags: '' });
  const [dmSpell, setDmSpell] = useState({ name: '', description: '', level: '0', school: '', ritual: false, casting_time: '', range: '', components: '', duration: '', classes: '' });
  const [dmNpcImage, setDmNpcImage] = useState<File | null>(null);
  const [dmMapImage, setDmMapImage] = useState<File | null>(null);
  const [dmBeastImage, setDmBeastImage] = useState<File | null>(null);

  useEffect(() => {
    const u = status.username || 'default';
    const sys = status.game_system || 'dnd5e';
    const sid = status.scenario_id || '';
    fetch(`/api/maps?username=${encodeURIComponent(u)}&scenario_id=${encodeURIComponent(sid)}`).then(r=>r.json()).then(d=>setMaps((d.maps||[]).filter((m: {system?:string})=>m.system===sys || m.system==='custom'))).catch(()=>{});
    fetch(`/api/bestiary?username=${encodeURIComponent(u)}&scenario_id=${encodeURIComponent(sid)}`).then(r=>r.json()).then(d=>setBestiary((d.bestiary||[]).filter((b: {system?:string})=>b.system===sys || b.system==='custom'))).catch(()=>{});
    fetch(`/api/spells?username=${encodeURIComponent(u)}&scenario_id=${encodeURIComponent(sid)}`).then(r=>r.json()).then(d=>setSpells((d.spells||[]).filter((s: {system?:string})=>s.system===sys || s.system==='custom'))).catch(()=>{});
  }, [status.username, status.game_system, status.scenario_id, mediaVersion]);

  const saveGame = async () => {
    if (!sessionId) {
      useToastStore.getState().showToast('还没有进行中的游戏，无法存档', 'error');
      return;
    }
    try {
      const r = await fetch(`/api/game/${sessionId}/save`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ label: '手动存档' }),
      });
      if (r.ok) {
        useToastStore.getState().showToast('已保存到存档列表', 'success');
      } else {
        useToastStore.getState().showToast('存档失败，请稍后再试', 'error');
      }
    } catch {
      useToastStore.getState().showToast('存档失败：网络错误', 'error');
    }
  };

  const openGraph = async (name?: string, queryOverride?: string) => {
    if (!sessionId) return;
    try {
      const params = new URLSearchParams();
      params.set('username', status.username || 'default');
      if (name) params.set('name', name);
      const query = queryOverride !== undefined ? queryOverride : graphQuery;
      if (query) params.set('query', query);
      if (!name && query) setGraphTypeFilter('all');
      const r = await fetch(`/api/game/${sessionId}/graph?${params.toString()}`);
      if (!r.ok) return;
      const d = await r.json();
      const graphNodes = d.graph?.nodes || [];
      setGraphData(d.graph || { nodes: [], edges: [] });
      setGraphFocusId(name || null);
      setGraphHoverId(null);
      // 稀疏图谱自动放大，避免大画布上节点过小；密集图谱保持全景
      const nodeCount = graphNodes.length;
      const initialZoom = nodeCount <= 6 ? 1.35 : nodeCount <= 12 ? 1.15 : nodeCount <= 24 ? 1.0 : 0.9;
      setGraphZoom(initialZoom);
      setGraphPan({ x: (GRAPH_W / 2) * (1 - initialZoom), y: (GRAPH_H / 2) * (1 - initialZoom) });
      if (queryOverride !== undefined) setGraphQuery(queryOverride);
      const results = name ? [] : (d.search || []).map((s: { node?: { id?: string } }) => s.node?.id).filter(Boolean);
      setGraphSearchIds(results);
      setGraphSearchEmpty(!name && !!query && results.length === 0);
      setShowGraph(true);
    } catch {}
  };

  const q = (s: string) => s.toLowerCase();
  const graphView = useMemo(() => {
    const allNodes = graphData?.nodes || [];
    const allEdges = graphData?.edges || [];
    const degree = new Map<string, number>();
    allEdges.forEach(e => {
      degree.set(e.source, (degree.get(e.source) || 0) + 1);
      degree.set(e.target, (degree.get(e.target) || 0) + 1);
    });
    let nodes = allNodes;
    let focusKeep: Set<string> | null = null;
    if (graphFocusId) {
      const focus = allNodes.find(n => n.id === graphFocusId);
      if (focus) {
        focusKeep = new Set<string>([focus.id]);
        allEdges.forEach(e => {
          if (e.source === focus.id) focusKeep!.add(e.target);
          if (e.target === focus.id) focusKeep!.add(e.source);
        });
      }
    }
    if (graphTypeFilter !== 'all') {
      const knownTypes = ['npc', 'location', 'plot', 'creature'];
      nodes = nodes.filter(n =>
        (graphTypeFilter === 'other' ? !knownTypes.includes(n.type) : n.type === graphTypeFilter)
        || n.id === graphFocusId
      );
    }
    if (focusKeep) nodes = nodes.filter(n => focusKeep!.has(n.id));
    if (graphSearchIds.length) {
      const searchKeep = new Set<string>(graphSearchIds);
      allEdges.forEach(e => {
        if (searchKeep.has(e.source)) searchKeep.add(e.target);
        if (searchKeep.has(e.target)) searchKeep.add(e.source);
      });
      nodes = nodes.filter(n => searchKeep.has(n.id));
    }
    nodes = [...nodes].sort((a, b) =>
      (degree.get(b.id) || 0) - (degree.get(a.id) || 0) || a.label.localeCompare(b.label)
    );
    const total = nodes.length;
    const limit = 24;
    const visibleNodes = nodes.slice(0, limit);
    const visibleIds = new Set(visibleNodes.map(n => n.id));
    const visibleEdges = allEdges.filter(e => visibleIds.has(e.source) && visibleIds.has(e.target));
    const layout = computeGraphLayout(visibleNodes, visibleEdges, graphFocusId);
    return { allNodes, allEdges, visibleNodes, visibleEdges, layout, total, truncated: total > limit };
  }, [graphData, graphTypeFilter, graphFocusId, graphSearchIds]);

  const graphActive = useMemo(() => {
    const activeId = graphFocusId || graphHoverId;
    const connected = new Set<string>();
    if (activeId) {
      connected.add(activeId);
      graphView.visibleEdges.forEach(e => {
        if (e.source === activeId) connected.add(e.target);
        if (e.target === activeId) connected.add(e.source);
      });
    }
    return { activeId, connected };
  }, [graphFocusId, graphHoverId, graphView.visibleEdges]);

  const clampGraphZoom = (z: number) => Math.max(0.35, Math.min(3, +z.toFixed(3)));
  const zoomGraphAt = (next: number, cursor: { x: number; y: number }) => {
    const z = clampGraphZoom(next);
    const factor = z / graphZoom;
    setGraphPan(p => ({
      x: cursor.x - (cursor.x - p.x) * factor,
      y: cursor.y - (cursor.y - p.y) * factor,
    }));
    setGraphZoom(z);
  };

  // 原生 wheel 监听：以鼠标位置为中心缩放（React 的 onWheel 默认 passive，无法 preventDefault）
  useEffect(() => {
    const svg = graphSvgRef.current;
    if (!svg || !showGraph) return;
    const onWheel = (e: WheelEvent) => {
      e.preventDefault();
      let cursor = { x: GRAPH_W / 2, y: GRAPH_H / 2 };
      try {
        const pt = svg.createSVGPoint();
        pt.x = e.clientX;
        pt.y = e.clientY;
        const ctm = svg.getScreenCTM();
        if (ctm) {
          const p = pt.matrixTransform(ctm.inverse());
          cursor = { x: p.x, y: p.y };
        }
      } catch { /* 极端情况下回退到中心缩放 */ }
      const next = clampGraphZoom(graphZoom * (e.deltaY > 0 ? 0.9 : 1.1));
      const factor = next / graphZoom;
      setGraphPan(prev => ({
        x: cursor.x - (cursor.x - prev.x) * factor,
        y: cursor.y - (cursor.y - prev.y) * factor,
      }));
      setGraphZoom(next);
    };
    svg.addEventListener('wheel', onWheel, { passive: false });
    return () => svg.removeEventListener('wheel', onWheel);
  }, [showGraph, graphZoom]);
  const currentSid = status.scenario_id || '';
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
      const locations = dmMap.locationsText.split(/[,，\n]/).map(s=>s.trim()).filter(Boolean).map(name=>({ name, x: 0, y: 0 }));
      const details = {
        type: dmMap.type.trim() || undefined,
        status: dmMap.status.trim() || undefined,
        culture: dmMap.culture.trim() || undefined,
        districts: dmMap.districts.split(/[,，]/).map(s=>s.trim()).filter(Boolean),
        notable_figures: dmMap.notable_figures.trim() || undefined,
        dangers: dmMap.dangers.trim() || undefined,
        secret: dmMap.secret.trim() || undefined,
      };
      const payload = {
        username: u, name: dmMap.name.trim(), description: dmMap.description,
        system: sys, scenario_id: sid, locations, details,
      };
      if (dmMapImage) {
        const fd = new FormData();
        fd.append('file', dmMapImage);
        fd.append('username', u);
        fd.append('name', dmMap.name.trim());
        fd.append('description', dmMap.description);
        fd.append('system', sys);
        fd.append('scenario_id', sid);
        await fetch('/api/maps/upload', { method: 'POST', body: fd });
        // 上传后再用 JSON 补充结构化详情（保留已上传图片）
        await fetch('/api/maps', {
          method: 'POST', headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify(payload),
        });
      } else {
        await fetch('/api/maps', {
          method: 'POST', headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify(payload),
        });
      }
      setDmMap({ name: '', description: '', type: '', status: '', culture: '', districts: '', notable_figures: '', dangers: '', secret: '', locationsText: '' });
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
      const stats: Record<string,string> = {};
      const num = (v: string) => v.trim();
      if (dmBeast.ac) stats['AC'] = num(dmBeast.ac);
      if (dmBeast.hp) stats['HP'] = num(dmBeast.hp);
      if (dmBeast.speed) stats['速度'] = num(dmBeast.speed);
      if (dmBeast.str) stats['力量'] = num(dmBeast.str);
      if (dmBeast.dex) stats['敏捷'] = num(dmBeast.dex);
      if (dmBeast.con) stats['体质'] = num(dmBeast.con);
      if (dmBeast.int) stats['智力'] = num(dmBeast.int);
      if (dmBeast.wis) stats['感知'] = num(dmBeast.wis);
      if (dmBeast.cha) stats['魅力'] = num(dmBeast.cha);
      if (dmBeast.skills) stats['技能'] = dmBeast.skills.trim();
      if (dmBeast.traits) stats['特性'] = dmBeast.traits.trim();
      if (dmBeast.actions) stats['动作'] = dmBeast.actions.trim();
      const details = {
        habits: dmBeast.habits.trim() || undefined,
        habitat: dmBeast.habitat.trim() || undefined,
        lore: dmBeast.lore.trim() || undefined,
        weakness: dmBeast.weakness.trim() || undefined,
      };
      const tags = dmBeast.tags.split(/[,，]/).map(s=>s.trim()).filter(Boolean);
      const payload = {
        username: u, name: dmBeast.name.trim(), description: dmBeast.description,
        system: sys, stats, tags, details, scenario_id: sid,
      };
      if (dmBeastImage) {
        const fd = new FormData();
        fd.append('file', dmBeastImage);
        fd.append('username', u);
        fd.append('name', dmBeast.name.trim());
        fd.append('description', dmBeast.description);
        fd.append('system', sys);
        fd.append('stats', JSON.stringify(stats));
        fd.append('tags', tags.join(','));
        fd.append('scenario_id', sid);
        await fetch('/api/bestiary/upload', { method: 'POST', body: fd });
        // 上传后再用 JSON 补充结构化详情（保留已上传图片）
        await fetch('/api/bestiary', {
          method: 'POST', headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify(payload),
        });
      } else {
        await fetch('/api/bestiary', {
          method: 'POST', headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify(payload),
        });
      }
      setDmBeast({ name: '', description: '', ac: '', hp: '', speed: '', str: '', dex: '', con: '', int: '', wis: '', cha: '', skills: '', traits: '', actions: '', habits: '', habitat: '', lore: '', weakness: '', tags: '' });
      setDmBeastImage(null);
      useGameStore.getState().bumpMediaVersion();
    } catch {}
  };

  const addDmSpell = async () => {
    if (!dmSpell.name.trim()) return;
    try {
      const u = status.username || 'default';
      const sid = status.scenario_id || '';
      await fetch('/api/spells', {
        method: 'POST', headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          username: u, name: dmSpell.name, description: dmSpell.description,
          level: dmSpell.level, school: dmSpell.school, ritual: dmSpell.ritual,
          casting_time: dmSpell.casting_time, range: dmSpell.range,
          components: dmSpell.components, duration: dmSpell.duration,
          classes: dmSpell.classes.split(/[,，]/).map(s=>s.trim()).filter(Boolean),
          system: status.game_system || 'custom', scenario_id: sid,
        }),
      });
      setDmSpell({ name: '', description: '', level: '0', school: '', ritual: false, casting_time: '', range: '', components: '', duration: '', classes: '' });
      useGameStore.getState().bumpMediaVersion();
    } catch {}
  };

  const translateSrd = async () => {
    if (!sessionId || srdTranslating) return;
    const untranslated = spells.filter(s => (s.tags || []).includes('SRD') && !s.description_zh);
    if (untranslated.length === 0) {
      alert('没有需要翻译的 SRD 法术');
      return;
    }
    const ids = untranslated.map(s => s.id);
    const total = ids.length;
    setSrdTranslating(true);
    setSrdProgress({ done: 0, total });
    try {
      const batchSize = 15;
      for (let i = 0; i < ids.length; i += batchSize) {
        const batch = ids.slice(i, i + batchSize);
        const r = await fetch(`/api/game/${sessionId}/translate-srd`, {
          method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ spell_ids: batch }),
        });
        if (!r.ok) {
          const e = await r.json().catch(() => ({}));
          alert(e.detail || '翻译失败');
          break;
        }
        setSrdProgress({ done: Math.min(i + batchSize, total), total });
      }
      useGameStore.getState().bumpMediaVersion();
    } catch {
      alert('翻译请求失败');
    } finally {
      setSrdTranslating(false);
      setSrdProgress(null);
    }
  };

  const translateMedia = async (kind: 'locations' | 'bestiary') => {
    if (!sessionId || mediaTranslate) return;
    const source = kind === 'locations' ? scopedMaps : scopedBestiary;
    const untranslated = source.filter(s => !s.description_zh);
    if (untranslated.length === 0) {
      alert('没有需要翻译的条目');
      return;
    }
    const ids = untranslated.map(s => s.id);
    const total = ids.length;
    setMediaTranslate({ kind, done: 0, total });
    try {
      const batchSize = 15;
      for (let i = 0; i < ids.length; i += batchSize) {
        const r = await fetch(`/api/game/${sessionId}/translate-media`, {
          method: 'POST', headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ kind, item_ids: ids.slice(i, i + batchSize) }),
        });
        if (!r.ok) {
          const e = await r.json().catch(() => ({}));
          alert(e.detail || '翻译失败');
          break;
        }
        setMediaTranslate({ kind, done: Math.min(i + batchSize, total), total });
      }
      useGameStore.getState().bumpMediaVersion();
    } catch {
      alert('翻译请求失败');
    } finally {
      setMediaTranslate(null);
    }
  };

  const hpPct = status.maxHp > 0 ? Math.max(0, Math.min(100, (status.hp / status.maxHp) * 100)) : 0;
  const hpTone =
    hpPct < 30
      ? 'text-red-700 border-red-200 bg-red-50 hover:bg-red-100'
      : hpPct < 60
        ? 'text-amber-700 border-amber-200 bg-amber-50 hover:bg-amber-100'
        : 'text-emerald-700 border-emerald-200 bg-emerald-50 hover:bg-emerald-100';

  /**
   * 导航按钮：桌面显示图标+文字；移动端只留图标
   * （9 个按钮在 390px 下横滑会藏掉一半，收成图标后一行放得下，
   *   并保留 aria-label / title 维持可访问性）。
   */
  const navItems = (
    <>
      <button onClick={() => setShowRulebook(true)} className="nav-btn" title="玩家说明书" aria-label="玩家说明书">
        <span aria-hidden>📕</span><span className="hidden sm:inline">说明书</span>
      </button>
      <button onClick={() => setShowCharSheet(true)} className="nav-btn" title="角色卡" aria-label="角色卡">
        <span aria-hidden>🧙</span><span className="hidden sm:inline">角色卡</span>
      </button>
      <button onClick={() => openGraph(undefined, '')} className="nav-btn" title="关系图谱" aria-label="关系图谱">
        <span aria-hidden>🕸️</span><span className="hidden sm:inline">图谱</span>
      </button>
      <button onClick={() => setShowMap(true)} className="nav-btn" title="地点 / 地图图鉴" aria-label="地图图鉴">
        <span aria-hidden>🗺️</span><span className="hidden sm:inline">地图</span>
      </button>
      <button onClick={() => setShowBeast(true)} className="nav-btn" title="生物图鉴" aria-label="生物图鉴">
        <span aria-hidden>🐾</span><span className="hidden sm:inline">图鉴</span>
      </button>
      <button onClick={() => setShowSpells(true)} className="nav-btn" title="法术 / 仪式" aria-label="法术图鉴">
        <span aria-hidden>✨</span><span className="hidden sm:inline">法术</span>
      </button>
      <span className="hidden sm:block w-px h-4 bg-ink-200 mx-0.5" aria-hidden />
      <button onClick={() => setShowDmTools(true)} className="nav-btn text-amber-700 hover:bg-amber-50" title="DM 工具" aria-label="DM 工具">
        <span aria-hidden>🛠️</span><span className="hidden sm:inline">DM</span>
      </button>
      <button onClick={saveGame} className="nav-btn" title="手动存档" aria-label="手动存档">
        <span aria-hidden>💾</span><span className="hidden sm:inline">存档</span>
      </button>
      <button onClick={goToStart} className="nav-btn" title="返回大厅" aria-label="返回大厅">
        <span aria-hidden>🚪</span><span className="hidden sm:inline">大厅</span>
      </button>
    </>
  );

  return (
    <div className="h-screen h-[100dvh] flex flex-col bg-white/60">
      {/* 顶栏：品牌 + 场景 + 角色数值 + 导航 */}
      <header className="flex-shrink-0 bg-white/90 backdrop-blur border-b border-ink-200">
        <div className="h-12 px-4 flex items-center gap-3">
          {/* 左：品牌与剧本标记（窄屏隐藏，避免空容器占用 gap 造成左导轨不齐） */}
          <div className="hidden sm:flex items-center gap-2 shrink-0">
            <span className="w-7 h-7 rounded-xl bg-brand-600 text-white text-2xs font-black hidden sm:flex items-center justify-center shadow-sm" aria-hidden>
              TR
            </span>
            <span className="text-xs font-bold text-ink-800 hidden lg:inline">TRPG 跑团</span>
            {currentSid && <span className="tag-purple hidden sm:inline-flex" title="当前剧本专属内容">剧本</span>}
          </div>

          {/* 中：场景信息 */}
          <div className="flex-1 min-w-0 flex items-center gap-2 sm:gap-3 text-2xs">
            {sceneInfo.location && sceneInfo.location !== '冒险的起点' && sceneInfo.location !== '未知' && (
              <span className="text-ink-700 font-medium truncate" title={sceneInfo.location}>
                <span aria-hidden className="hidden sm:inline">📍 </span>{sceneInfo.location}
              </span>
            )}
            <span className="text-ink-500 shrink-0 font-mono">{sceneInfo.time}</span>
          </div>

          {/* 右：角色数值 + 移动端抽屉入口 + 桌面导航 */}
          <div className="flex items-center gap-1.5 shrink-0">
            <button
              onClick={() => setShowCharSheet(true)}
              className={`inline-flex items-center gap-1.5 text-2xs font-mono font-semibold px-2 py-1 rounded-lg border transition-colors ${hpTone}`}
              title="查看角色卡"
            >
              <span aria-hidden>❤</span>
              {status.hp}/{status.maxHp}
            </button>
            <span className="text-2xs text-ink-600 hidden xl:inline max-w-[10rem] truncate" title={status.character_name}>
              {status.character_name || '冒险者'}
              {status.race && <span className="text-ink-400"> · {status.race}{status.char_class}</span>}
            </span>
            <span className="text-2xs text-ink-400 font-mono hidden 2xl:inline">#{sessionId?.slice(0, 6)}</span>

            {/* 移动端：状态 / 笔记抽屉 */}
            <div className="flex items-center gap-1 md:hidden">
              <button onClick={() => setMobilePanel('status')} className="nav-btn" aria-label="角色状态">
                <span aria-hidden>📋</span>
              </button>
              <button onClick={() => setMobilePanel('journal')} className="nav-btn" aria-label="冒险笔记">
                <span aria-hidden>📓</span>
              </button>
            </div>
          </div>
        </div>

        {/* 第二行：导航工具条（窄屏图标化，不横滑藏内容）+ 场景补充信息（宽屏显示） */}
        <div className="px-4 pb-2 flex items-center gap-2">
          <nav
            className="flex items-center gap-0.5 overflow-x-auto no-scrollbar min-w-0 rounded-xl bg-ink-50/80 ring-1 ring-ink-200/70 p-1"
            aria-label="主要功能"
          >
            {navItems}
          </nav>
          <div className="hidden xl:flex items-center gap-3 ml-auto pl-3 shrink-0 text-2xs text-ink-500">
            {sceneInfo.weather && <span className="shrink-0" title={sceneInfo.weather}>☁ {sceneInfo.weather}</span>}
            {sceneInfo.npcs_here.length > 0 && (
              <span className="truncate max-w-[20rem]" title={sceneInfo.npcs_here.join('、')}>
                👥 在场：{sceneInfo.npcs_here.slice(0, 4).join('、')}
                {sceneInfo.npcs_here.length > 4 ? ` +${sceneInfo.npcs_here.length - 4}` : ''}
              </span>
            )}
          </div>
        </div>
      </header>

      <div className="flex flex-1 min-h-0">
        {/* 桌面三栏：状态面板在 md 以上常驻；移动端走底部抽屉 */}
        <div className="hidden md:flex">
          <StatusPanel onOpenSheet={() => setShowCharSheet(true)} />
        </div>
        <main className="flex-1 flex flex-col min-w-0 md:border-x border-ink-200 bg-white/40">
          <NarrativeStream />
          <DecisionPanel />
          <Choices />
          <CombatLogPanel />
          <InputArea />
        </main>
        <div className="hidden md:flex">
          <PlayerJournal />
        </div>
      </div>

      {/* 移动端抽屉：复用桌面面板组件 */}
      <Modal open={mobilePanel === 'status'} onClose={() => setMobilePanel(null)} placement="bottom" title="角色状态" icon="📋">
        <div className="-mx-4 -my-4">
          <StatusPanel onOpenSheet={() => { setMobilePanel(null); setShowCharSheet(true); }} />
        </div>
      </Modal>
      <Modal open={mobilePanel === 'journal'} onClose={() => setMobilePanel(null)} placement="bottom" title="冒险笔记" icon="📓">
        <div className="-mx-4 -my-4">
          <PlayerJournal />
        </div>
      </Modal>

      <DiceRollOverlay />

      <Modal
        open={showCharSheet}
        onClose={() => setShowCharSheet(false)}
        paper
        size="xl"
        icon="🧙"
        title="角色卡"
        subtitle={`${status.character_name || '冒险者'} · ${status.race || '?'} ${status.char_class || '?'} · ${status.game_system || 'dnd5e'}`}
      >
          {isDndSheet ? (
            <DndCharacterSheet embedded />
          ) : (status.game_system as string) === 'coc' ? (
            <CocInvestigatorSheet embedded />
          ) : (
          <div className="space-y-4">

            {/* 身份 */}
            <div className="flex items-center gap-3 mb-4">
              {status.character_image ? <img src={status.character_image} alt="角色" className="w-20 h-20 object-cover rounded-xl border border-gray-200" /> : <div className="w-20 h-20 bg-gray-100 rounded-xl flex items-center justify-center text-[9px] text-ink-400">暂无头像</div>}
              <div>
                <p className="text-base font-bold">{status.character_name||'冒险者'}</p>
                <p className="text-[10px] text-ink-500">{status.race||'?'} {status.char_class||'?'} · {status.game_system||'dnd5e'}</p>
                {status.hit_die && <p className="text-[10px] text-ink-400">生命骰：{status.hit_die}</p>}
              </div>
            </div>

            {/* 核心数值 */}
            <div className="grid grid-cols-4 gap-2 mb-4">
              <div className="stat-tile"><p className="text-[9px] text-ink-400">HP</p><p className="text-sm font-bold">{status.hp}/{status.maxHp}</p></div>
              <div className="stat-tile"><p className="text-[9px] text-ink-400">AC</p><p className="text-sm font-bold">{status.ac}</p></div>
              <div className="stat-tile"><p className="text-[9px] text-ink-400">等级</p><p className="text-sm font-bold">{status.level}</p></div>
              <div className="stat-tile"><p className="text-[9px] text-ink-400">经验</p><p className="text-sm font-bold">{getXpDisplay(status.game_system as string, status.xp, status.level)}</p></div>
              {status.game_system==='coc' && (
                <>
                  <div className="stat-tile"><p className="text-[9px] text-ink-400">MP</p><p className="text-sm font-bold">{status.mp}/{status.maxMp}</p></div>
                  <div className="stat-tile"><p className="text-[9px] text-ink-400">SAN</p><p className="text-sm font-bold">{status.san}/{status.maxSan}</p></div>
                  <div className="stat-tile"><p className="text-[9px] text-ink-400">幸运</p><p className="text-sm font-bold">{status.luck}</p></div>
                  <div className="stat-tile"><p className="text-[9px] text-ink-400">伤害加值</p><p className="text-sm font-bold">{status.damage_bonus||'0'}</p></div>
                </>
              )}
              {status.game_system==='dnd4e' && (
                <>
                  <div className="stat-tile"><p className="text-[9px] text-ink-400">回复力</p><p className="text-sm font-bold">{status.healing_surges}/{status.max_healing_surges}</p></div>
                  <div className="stat-tile"><p className="text-[9px] text-ink-400">回复量</p><p className="text-sm font-bold">{status.surge_value}</p></div>
                  <div className="stat-tile"><p className="text-[9px] text-ink-400">强韧/反射/意志</p><p className="text-sm font-bold">{status.fortitude}/{status.reflex}/{status.will}</p></div>
                  <div className="stat-tile"><p className="text-[9px] text-ink-400">熟练加值</p><p className="text-sm font-bold">{status.proficiency_bonus||2}</p></div>
                </>
              )}
              {status.game_system==='dnd5e' && (
                <>
                  <div className="stat-tile"><p className="text-[9px] text-ink-400">熟练加值</p><p className="text-sm font-bold">{status.proficiency_bonus||2}</p></div>
                  <div className="stat-tile"><p className="text-[9px] text-ink-400">金币</p><p className="text-sm font-bold">{status.gold}</p></div>
                  <div className="stat-tile"><p className="text-[9px] text-ink-400">法术位</p><p className="text-sm font-bold">{(() => {
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
              <p className="section-label mb-1.5">属性</p>
              <div className="grid grid-cols-2 sm:grid-cols-3 gap-1.5">
                {Object.entries(status.attributes||{})
                  .filter(([k]) => status.game_system === 'coc'
                    ? ['str','con','dex','int','pow','cha','siz','edu'].includes(k)
                    : ['str','dex','con','int','wis','cha'].includes(k))
                  .map(([k,v])=>{
                    const m=Math.floor((Number(v)-10)/2);
                    return (
                      <div key={k} className="bg-white rounded-lg border border-gray-200 px-2 py-1 flex justify-between">
                        <span className="text-[10px] text-ink-400">{ATTR_CN[k]||k.toUpperCase()}</span>
                        <span className="text-xs font-bold">{textValue(v)}{status.game_system!=='coc' && <span className={`ml-1 text-[9px] ${m>=0?'text-emerald-700':'text-red-400'}`}>({m>=0?'+':''}{m})</span>}</span>
                      </div>
                    );
                  })}
              </div>
            </div>

            {/* 技能 / 特长 / 特性 */}
            {((status.skill_proficiencies?.length ?? 0)>0 || (status.feats?.length ?? 0)>0 || (status.race_traits?.length ?? 0)>0 || (status.class_proficiencies?.length ?? 0)>0) && (
              <div className="space-y-2 mb-4">
                {status.skills && Object.keys(status.skills).length>0 && (
                  <div><p className="section-label mb-1.5">技能数值</p><div className="flex flex-wrap gap-1">{Object.entries(status.skills).map(([k,v])=><span key={k} className="text-[10px] bg-indigo-50 text-indigo-700 border border-indigo-100 rounded px-1.5 py-0.5">{k}: {textValue(v)}</span>)}</div></div>
                )}
                {status.skill_proficiencies && status.skill_proficiencies.length>0 && (
                  <div><p className="section-label mb-1.5">技能熟练</p><div className="flex flex-wrap gap-1">{status.skill_proficiencies.map((s,i)=><span key={i} className="text-[10px] bg-indigo-50 text-indigo-700 border border-indigo-100 rounded px-1.5 py-0.5">{s}</span>)}</div></div>
                )}
                {status.feats && status.feats.length>0 && (
                  <div><p className="section-label mb-1.5">特长</p><div className="space-y-1">{status.feats.map((f,i)=><div key={i} className="text-[10px] bg-amber-50 text-amber-800 border border-amber-200 rounded px-2 py-1">{f.name}{f.description?`：${f.description}`:''}</div>)}</div></div>
                )}
                {status.race_traits && status.race_traits.length>0 && (
                  <div><p className="section-label mb-1.5">种族特性</p><div className="flex flex-wrap gap-1">{status.race_traits.map((s,i)=><span key={i} className="text-[10px] bg-gray-100 text-ink-700 border border-gray-200 rounded px-1.5 py-0.5">{s}</span>)}</div></div>
                )}
                {status.class_proficiencies && status.class_proficiencies.length>0 && (
                  <div><p className="section-label mb-1.5">职业熟练</p><div className="flex flex-wrap gap-1">{status.class_proficiencies.map((s,i)=><span key={i} className="text-[10px] bg-gray-100 text-ink-700 border border-gray-200 rounded px-1.5 py-0.5">{s}</span>)}</div></div>
                )}
              </div>
            )}

            {/* 已习得法术 */}
            {((status.known_spells?.length ?? 0) > 0) && (
              <div className="space-y-1 mb-4">
                <p className="section-label mb-1.5">已习得法术</p>
                {status.known_spells!.map(s => <SpellCard key={s.name} spell={s} />)}
              </div>
            )}

            {/* 剧本专属 / 额外属性 */}
            {((status.custom_classes?.length ?? 0)>0 || (status.custom_skills?.length ?? 0)>0 || (status.extra_attributes && Object.keys(status.extra_attributes).length>0)) && (
              <div className="space-y-2 mb-4">
                {status.custom_classes && status.custom_classes.length>0 && (
                  <div><p className="section-label mb-1.5">剧本专属职业/身份</p><div className="flex flex-wrap gap-1">{status.custom_classes.map((s,i)=><span key={i} className="text-[10px] bg-purple-50 text-purple-700 border border-purple-200 rounded px-1.5 py-0.5">{s}</span>)}</div></div>
                )}
                {status.custom_skills && status.custom_skills.length>0 && (
                  <div><p className="section-label mb-1.5">剧本专属技能</p><div className="flex flex-wrap gap-1">{status.custom_skills.map((s,i)=><span key={i} className="text-[10px] bg-purple-50 text-purple-700 border border-purple-200 rounded px-1.5 py-0.5">{s}</span>)}</div></div>
                )}
                {status.extra_attributes && Object.keys(status.extra_attributes).length>0 && (
                  <div><p className="section-label mb-1.5">额外属性</p><div className="flex flex-wrap gap-1">{Object.entries(status.extra_attributes).map(([k,v],i)=><span key={i} className="text-[10px] bg-gray-100 text-ink-700 border border-gray-200 rounded px-1.5 py-0.5">{k}: {textValue(v)}</span>)}</div></div>
                )}
              </div>
            )}

            {/* 背景故事 */}
            {status.backstory && (
              <div className="mb-4">
                <p className="section-label mb-1.5">背景故事</p>
                <p className="text-xs text-ink-700 whitespace-pre-wrap leading-relaxed">{status.backstory}</p>
              </div>
            )}

            {/* 背包 */}
            {status.inventory?.length>0 && (
              <div className="mb-4">
                <p className="section-label mb-1.5">背包</p>
                <div className="flex flex-wrap gap-1">{status.inventory.map((it,i)=><span key={i} className="text-[10px] bg-gray-50 border border-gray-200 rounded px-1.5 py-0.5">{invName(it)}</span>)}</div>
              </div>
            )}
          </div>
          )}
      </Modal>

      {showRulebook && <RulebookModal onClose={()=>setShowRulebook(false)} />}

      <Modal
        open={showMap}
        onClose={() => setShowMap(false)}
        size="lg"
        icon="🗺️"
        title="地点 / 地图图鉴"
        subtitle={currentSid ? '默认仅显示当前剧本条目；可切换显示通用参考' : '通用地点库（所有剧本可用）'}
        headExtra={
          <>
            <button onClick={()=>setShowMapBuilder(v=>!v)} className="btn-xs-paper">
              {showMapBuilder ? '收起自建' : '自建地点'}
            </button>
            <button onClick={()=>translateMedia('locations')} disabled={!!mediaTranslate} className="btn-xs-brand">
              {mediaTranslate?.kind==='locations' ? '机翻中...' : '翻译地点'}
            </button>
            {currentSid && (
              <button onClick={()=>setShowGlobalRefMaps(v=>!v)} className={`btn-xs ${showGlobalRefMaps ? 'border-brand-300 bg-brand-50 text-brand-700' : ''}`}>
                {showGlobalRefMaps ? '仅当前剧本' : '通用参考'}
              </button>
            )}
          </>
        }
      >
            {mediaTranslate?.kind==='locations' && (
              <ProgressBar
                className="mb-3"
                label="机翻地点描述"
                value={mediaTranslate.done}
                max={mediaTranslate.total}
              />
            )}
            <input value={mapQuery} onChange={e=>setMapQuery(e.target.value)} placeholder="搜索地点 / 区域 / 类型 / 人物 / 危险…" className="input-field text-xs mb-3 !py-2" aria-label="搜索地点" />
            {showMapBuilder && (
              <div className="rounded-xl border border-parch-400/50 bg-parch-100/60 p-3 space-y-2.5 mb-3">
                <p className="text-xs font-bold text-ink-700">自建地点 / 地图</p>
                <div className="grid grid-cols-2 gap-2">
                  <input value={dmMap.name} onChange={e=>setDmMap({...dmMap,name:e.target.value})} placeholder="地点名称 *" className="input-field text-xs" />
                  <input value={dmMap.type} onChange={e=>setDmMap({...dmMap,type:e.target.value})} placeholder="类型（城镇/地城/森林...）" className="input-field text-xs" />
                  <input value={dmMap.status} onChange={e=>setDmMap({...dmMap,status:e.target.value})} placeholder="状态（可访问/危险/封闭）" className="input-field text-xs" />
                  <input value={dmMap.culture} onChange={e=>setDmMap({...dmMap,culture:e.target.value})} placeholder="文化/势力" className="input-field text-xs" />
                  <input value={dmMap.districts} onChange={e=>setDmMap({...dmMap,districts:e.target.value})} placeholder="区域（逗号分隔）" className="input-field text-xs" />
                  <input value={dmMap.notable_figures} onChange={e=>setDmMap({...dmMap,notable_figures:e.target.value})} placeholder="知名人物" className="input-field text-xs" />
                  <input value={dmMap.dangers} onChange={e=>setDmMap({...dmMap,dangers:e.target.value})} placeholder="危险/威胁" className="input-field text-xs" />
                  <input value={dmMap.secret} onChange={e=>setDmMap({...dmMap,secret:e.target.value})} placeholder="秘密/隐藏信息" className="input-field text-xs" />
                </div>
                <input value={dmMap.locationsText} onChange={e=>setDmMap({...dmMap,locationsText:e.target.value})} placeholder="子地点（逗号分隔）" className="input-field text-xs w-full" />
                <textarea value={dmMap.description} onChange={e=>setDmMap({...dmMap,description:e.target.value})} placeholder="地点描述" rows={2} className="input-field text-xs resize-none w-full" />
                <input type="file" accept=".png,.jpg,.jpeg,.webp" onChange={e=>setDmMapImage(e.target.files?.[0]||null)} className="block w-full text-[10px] text-ink-500" />
                <button onClick={()=>{addDmMap(); setShowMapBuilder(false);}} className="btn-xs-paper mt-1">保存到当前剧本地点库</button>
              </div>
            )}
            {filteredMaps.length===0&&(
              <EmptyState
                icon="🗺️"
                title="没有找到地图"
                hint={currentSid && !showGlobalRefMaps && scenarioMaps.length===0 ? '当前剧本暂无地点图鉴；点击右上角「通用参考」查看通用库。' : '可以调整搜索，或先导入剧本 / 上传地图图片'}
              />
            )}
            {filteredMaps.map(m=>{
              const relatedCreatures = bestiary.filter(b => q(`${b.description} ${b.details?.habitat||''} ${b.details?.lore||''}`).includes(q(m.name)));
              return (
                <details key={m.id} className="group entry-card mb-3">
                  <summary className="entry-summary">
                    <span className="flex items-center gap-2 min-w-0">
                      <span className="text-sm font-bold truncate">{m.name}</span>
                      <span className={`scope-badge ${m.scenario_id ? 'scope-badge-scenario' : 'scope-badge-global'}`}>{m.scenario_id ? '当前剧本' : '通用参考'}</span>
                    </span>
                    <span className="text-[9px] text-ink-400 shrink-0">
                      {m.details?.type || '地点'} · {m.details?.status || '未知'} · {m.locations.length} 子地点
                      <span className="ml-1 group-open:hidden">▸</span><span className="hidden group-open:inline">▾</span>
                    </span>
                  </summary>
                  <div className="px-3 pb-3 border-t border-gray-100">
                    {m.image_path&&<img src={m.image_path} alt={m.name} className="w-full max-h-80 object-contain bg-gray-100 mb-2" />}
                    <p className="text-[10px] text-ink-500 mb-2">{m.description_zh || m.description}{m.description_zh && m.description ? <span className="text-ink-400 italic">（原文：{m.description.slice(0,60)}...）</span> : null}</p>
                    {m.locations.length>0&&<div className="flex flex-wrap gap-1 mb-2">{m.locations.map((l,i)=><span key={i} className="text-[10px] bg-indigo-50 text-indigo-700 px-2 py-0.5 rounded-full border border-indigo-100">{l.name}</span>)}</div>}
                    {m.details && (
                      <div className="text-[10px] text-ink-600 space-y-1">
                        {m.details.type&&<p>类型：{m.details.type}</p>}
                        {m.details.status&&<p>状态：{m.details.status}</p>}
                        {m.details.culture&&<p>文化/势力：{m.details.culture}</p>}
                        {m.details.districts && m.details.districts.length>0&&<p>区域：{m.details.districts.join('、')}</p>}
                        {m.details.notable_figures&&<p>知名人物：{m.details.notable_figures}</p>}
                        {m.details.dangers&&<p>危险：{m.details.dangers}</p>}
                      </div>
                    )}
                    {relatedCreatures.length>0 && (
                      <div className="mt-2 pt-2 border-t border-gray-100">
                        <p className="text-[9px] text-ink-400 mb-1">可能出现的生物</p>
                        <div className="flex flex-wrap gap-1">{relatedCreatures.map(b=><span key={b.id} className="text-[10px] bg-emerald-50 text-emerald-700 border border-emerald-200 rounded px-1.5 py-0.5">{b.name}</span>)}</div>
                      </div>
                    )}
                  </div>
                </details>
              );
            })}
      </Modal>

      <Modal
        open={showBeast}
        onClose={() => setShowBeast(false)}
        paper
        size="lg"
        icon="🐾"
        title="生物图鉴"
        subtitle="默认仅显示当前剧本条目；通用参考需手动切换，且不会被剧本操作覆盖"
        headExtra={
          <>
            <button onClick={()=>setShowBeastBuilder(v=>!v)} className="btn-xs-paper">
              {showBeastBuilder ? '收起自建' : '自建生物'}
            </button>
            <button onClick={()=>translateMedia('bestiary')} disabled={!!mediaTranslate} className="btn-xs-brand">
              {mediaTranslate?.kind==='bestiary' ? '机翻中...' : '翻译生物'}
            </button>
            {currentSid && (
              <button onClick={()=>setShowGlobalRefBestiary(v=>!v)} className={`btn-xs ${showGlobalRefBestiary ? 'border-brand-300 bg-brand-50 text-brand-700' : ''}`}>
                {showGlobalRefBestiary ? '仅当前剧本' : '通用参考'}
              </button>
            )}
          </>
        }
      >
            {mediaTranslate?.kind==='bestiary' && (
              <ProgressBar className="mb-3" label="机翻生物描述" value={mediaTranslate.done} max={mediaTranslate.total} />
            )}
            <input value={beastQuery} onChange={e=>setBeastQuery(e.target.value)} placeholder="搜索生物 / 属性 / 栖息地 / 传说 / 弱点…" className="input-field text-xs mb-3 !py-2" aria-label="搜索生物" />
            {showBeastBuilder && (
              <div className="rounded-xl border border-parch-400/50 bg-parch-100/60 p-3 space-y-2.5 mb-3">
                <p className="text-xs font-bold text-ink-700">自建生物</p>
                <div className="grid grid-cols-2 gap-2">
                  <input value={dmBeast.name} onChange={e=>setDmBeast({...dmBeast,name:e.target.value})} placeholder="生物名称 *" className="input-field text-xs" />
                  <input value={dmBeast.tags} onChange={e=>setDmBeast({...dmBeast,tags:e.target.value})} placeholder="标签（人形生物/神话...）" className="input-field text-xs" />
                  <input value={dmBeast.ac} onChange={e=>setDmBeast({...dmBeast,ac:e.target.value})} placeholder="AC" className="input-field text-xs" />
                  <input value={dmBeast.hp} onChange={e=>setDmBeast({...dmBeast,hp:e.target.value})} placeholder="HP" className="input-field text-xs" />
                  <input value={dmBeast.speed} onChange={e=>setDmBeast({...dmBeast,speed:e.target.value})} placeholder="速度（30尺）" className="input-field text-xs" />
                  <input value={dmBeast.str} onChange={e=>setDmBeast({...dmBeast,str:e.target.value})} placeholder="力量" className="input-field text-xs" />
                  <input value={dmBeast.dex} onChange={e=>setDmBeast({...dmBeast,dex:e.target.value})} placeholder="敏捷" className="input-field text-xs" />
                  <input value={dmBeast.con} onChange={e=>setDmBeast({...dmBeast,con:e.target.value})} placeholder="体质" className="input-field text-xs" />
                  <input value={dmBeast.int} onChange={e=>setDmBeast({...dmBeast,int:e.target.value})} placeholder="智力" className="input-field text-xs" />
                  <input value={dmBeast.wis} onChange={e=>setDmBeast({...dmBeast,wis:e.target.value})} placeholder="感知" className="input-field text-xs" />
                  <input value={dmBeast.cha} onChange={e=>setDmBeast({...dmBeast,cha:e.target.value})} placeholder="魅力" className="input-field text-xs" />
                  <input value={dmBeast.skills} onChange={e=>setDmBeast({...dmBeast,skills:e.target.value})} placeholder="技能（察觉+4，隐匿+5）" className="input-field text-xs" />
                </div>
                <textarea value={dmBeast.description} onChange={e=>setDmBeast({...dmBeast,description:e.target.value})} placeholder="生物描述" rows={2} className="input-field text-xs resize-none w-full" />
                <textarea value={dmBeast.traits} onChange={e=>setDmBeast({...dmBeast,traits:e.target.value})} placeholder="特性（多行，如：黑暗视觉：...）" rows={2} className="input-field text-xs resize-none w-full" />
                <textarea value={dmBeast.actions} onChange={e=>setDmBeast({...dmBeast,actions:e.target.value})} placeholder="动作（多行，如：啃咬：+5 1d8+3）" rows={2} className="input-field text-xs resize-none w-full" />
                <div className="grid grid-cols-2 gap-2">
                  <input value={dmBeast.habits} onChange={e=>setDmBeast({...dmBeast,habits:e.target.value})} placeholder="习性" className="input-field text-xs" />
                  <input value={dmBeast.habitat} onChange={e=>setDmBeast({...dmBeast,habitat:e.target.value})} placeholder="栖息地" className="input-field text-xs" />
                  <input value={dmBeast.lore} onChange={e=>setDmBeast({...dmBeast,lore:e.target.value})} placeholder="传说/背景" className="input-field text-xs" />
                  <input value={dmBeast.weakness} onChange={e=>setDmBeast({...dmBeast,weakness:e.target.value})} placeholder="弱点" className="input-field text-xs" />
                </div>
                <input type="file" accept=".png,.jpg,.jpeg,.webp" onChange={e=>setDmBeastImage(e.target.files?.[0]||null)} className="block w-full text-[10px] text-ink-500" />
                <button onClick={()=>{addDmBeast(); setShowBeastBuilder(false);}} className="btn-xs-paper mt-1">保存到当前剧本生物库</button>
              </div>
            )}
            {filteredBestiary.length===0&&(
              <EmptyState
                icon="🐾"
                title="没有找到生物"
                hint={currentSid && !showGlobalRefBestiary && scenarioBestiary.length===0 ? '当前剧本暂无生物图鉴；点击右上角「通用参考」查看通用库。' : '可以调整搜索，或先导入怪物库 / 上传生物图片'}
              />
            )}
            {filteredBestiary.map(b=>{
              const relatedMaps = scopedMaps.filter(m => q(`${b.details?.habitat||''} ${b.description} ${b.details?.lore||''}`).includes(q(m.name)) || q(m.description).includes(q(b.name)));
              const s = b.stats || {};
              const get = (...keys: string[]) => {
                const raw = keys.map(k=>s[k]).find(v=>v!==undefined && v!=='');
                return raw === undefined ? '—' : textValue(raw);
              };
              const abilities: Array<[string,string]> = [
                ['力量', get('力量','STR','str')], ['敏捷', get('敏捷','DEX','dex')],
                ['体质', get('体质','CON','con')], ['智力', get('智力','INT','int')],
                ['感知', get('感知','WIS','wis')], ['魅力', get('魅力','CHA','cha')],
              ];
              const baseSaves = abilities.map(([k, v]) => {
                const n = Number(v);
                return [k, Number.isFinite(n) && v !== '—' ? (Math.floor((n - 10) / 2) >= 0 ? `+${Math.floor((n - 10) / 2)}` : `${Math.floor((n - 10) / 2)}`) : '—'] as [string, string];
              });
              const skills = get('技能','Skills','skills');
              const saves = get('豁免','Saves','saves');
              const senses = get('感官','Senses','senses');
              const languages = get('语言','Languages','languages');
              const challenge = get('挑战等级','挑战','CR','cr');
              const xp = crToXp(challenge);
              const dexStat = Number(get('敏捷','DEX','dex'));
              const initiative = Number.isFinite(dexStat) && dexStat !== 0 ? `${Math.floor((dexStat - 10) / 2) >= 0 ? '+' : ''}${Math.floor((dexStat - 10) / 2)}` : '—';
              const traits = get('特性','Traits','traits');
              const actions = get('动作','Actions','actions');
              return (
                <details key={b.id} className="group entry-card p-3 mb-3">
                  <summary className="cursor-pointer select-none list-none">
                    <div className="flex items-center justify-between gap-2">
                      <div className="flex items-center gap-2 min-w-0">
                        {b.image_path && <img src={b.image_path} alt="" loading="lazy" decoding="async" onError={e=>{e.currentTarget.style.display='none';}} className="w-9 h-9 object-cover rounded border border-amber-900/20 shrink-0" />}
                        <span className="paper-title text-base font-bold text-ink-900 truncate">{b.name}</span>
                        <span className={`scope-badge ${b.scenario_id ? 'scope-badge-scenario' : 'scope-badge-global'}`}>{b.scenario_id ? '当前剧本' : '通用参考'}</span>
                      </div>
                      <span className="text-[9px] text-ink-400 shrink-0">{challenge!=='—'?`CR ${challenge}${xp!=='—'?`（XP ${xp}）`:''} · `:''}HP {get('HP','hp','生命')} · AC {get('AC','ac','护甲')}<span className="ml-1 group-open:hidden">▸</span><span className="hidden group-open:inline">▾</span></span>
                    </div>
                  </summary>
                  <div className="mt-2">
                  {b.image_path && (
                    <a href={b.image_path} target="_blank" rel="noreferrer" title="查看原图" className="block mb-3">
                      <img src={b.image_path} alt={b.name} loading="lazy" decoding="async" onError={e=>{e.currentTarget.style.display='none';}} className="w-full max-h-72 object-contain bg-gray-100 rounded-lg border border-amber-900/20" />
                    </a>
                  )}
                  <div className="flex items-start gap-3">
                    <div className="min-w-0 flex-1">
                      <p className="text-[10px] text-ink-500 italic">
                        {b.scenario_id ? <span className="text-emerald-700 font-medium">当前剧本</span> : <span className="text-ink-400 font-medium">通用参考</span>}
                        {' · '}{b.system}{b.tags&&b.tags.length>0?` · ${b.tags.join('、')}`:''}
                      </p>
                      <div className="grid grid-cols-3 gap-1 mt-1.5 text-[10px]">
                        <div className="bg-amber-50 border border-amber-200 rounded px-1.5 py-0.5"><span className="text-ink-500">AC</span> <b>{get('AC','ac','护甲')}</b></div>
                        <div className="bg-amber-50 border border-amber-200 rounded px-1.5 py-0.5"><span className="text-ink-500">HP</span> <b>{get('HP','hp','生命')}</b></div>
                        <div className="bg-amber-50 border border-amber-200 rounded px-1.5 py-0.5"><span className="text-ink-500">速度</span> <b>{get('速度','Speed','speed')}</b></div>
                      </div>
                    </div>
                  </div>

                  {/* D&D4e 关键数值 */}
                  {b.system === 'dnd4e' && (
                    <div className="grid grid-cols-3 gap-1 mt-2 border-t border-amber-900/10 pt-2 text-[10px]">
                      <div className="bg-white border border-amber-900/10 rounded px-1.5 py-0.5"><span className="text-ink-400">强韧</span> <b>{get('强韧','Fortitude','fort')}</b></div>
                      <div className="bg-white border border-amber-900/10 rounded px-1.5 py-0.5"><span className="text-ink-400">反射</span> <b>{get('反射','Reflex','ref')}</b></div>
                      <div className="bg-white border border-amber-900/10 rounded px-1.5 py-0.5"><span className="text-ink-400">意志</span> <b>{get('意志','Will','will')}</b></div>
                      <div className="bg-white border border-amber-900/10 rounded px-1.5 py-0.5"><span className="text-ink-400">等级</span> <b>{get('等级','Level','level')}</b></div>
                      <div className="bg-white border border-amber-900/10 rounded px-1.5 py-0.5"><span className="text-ink-400">XP</span> <b>{get('XP','xp')}</b></div>
                      <div className="bg-white border border-amber-900/10 rounded px-1.5 py-0.5"><span className="text-ink-400">角色</span> <b>{get('角色类型','role')}</b></div>
                    </div>
                  )}

                  {/* 六维 / COC 关键数值 */}
                  {b.system === 'coc' ? (
                    <div className="grid grid-cols-2 gap-1 mt-2 border-t border-amber-900/10 pt-2">
                      <div className="bg-white border border-amber-900/10 rounded px-1.5 py-0.5"><span className="text-[8px] text-ink-400">HP</span> <b className="text-xs">{get('HP','hp','生命')}</b></div>
                      <div className="bg-white border border-amber-900/10 rounded px-1.5 py-0.5"><span className="text-[8px] text-ink-400">MP</span> <b className="text-xs">{get('MP','mp','魔法')}</b></div>
                      <div className="bg-white border border-amber-900/10 rounded px-1.5 py-0.5"><span className="text-[8px] text-ink-400">伤害加值</span> <b className="text-xs">{get('伤害加值','DB','damage_bonus')}</b></div>
                      <div className="bg-white border border-amber-900/10 rounded px-1.5 py-0.5"><span className="text-[8px] text-ink-400">护甲</span> <b className="text-xs">{get('护甲','装甲','armor')}</b></div>
                      <div className="bg-white border border-amber-900/10 rounded px-1.5 py-0.5 col-span-2"><span className="text-[8px] text-ink-400">技能</span> <b className="text-xs">{get('技能','Skills','skills')}</b></div>
                      <div className="bg-white border border-amber-900/10 rounded px-1.5 py-0.5 col-span-2"><span className="text-[8px] text-ink-400">理智损失</span> <b className="text-xs">{get('理智损失','SAN Loss','sanity')}</b></div>
                    </div>
                  ) : (
                    <>
                      <div className="grid grid-cols-3 gap-1 mt-2 border-t border-amber-900/10 pt-2">
                        {abilities.map(([k,v])=>(
                          <div key={k} className="bg-white border border-amber-900/10 rounded px-1.5 py-0.5 text-center">
                            <span className="text-[8px] text-ink-400 font-semibold">{k}</span>
                            <div className="text-xs font-bold">{v}</div>
                          </div>
                        ))}
                      </div>
                      <div className="grid grid-cols-6 gap-1 mt-1.5">
                        {baseSaves.map(([k,v])=>(
                          <div key={k} className="bg-white border border-amber-900/10 rounded px-1 py-0.5 text-center">
                            <span className="text-[7px] text-ink-400">{k}</span>
                            <div className="text-[10px] font-bold">{v}</div>
                          </div>
                        ))}
                      </div>
                    </>
                  )}

                  {/* 标准字段 */}
                  {(skills!=='—'||senses!=='—'||languages!=='—'||challenge!=='—'||xp!=='—'||initiative!=='—'||saves!=='—') && (
                    <div className="mt-2 border-t border-amber-900/10 pt-1.5 space-y-0.5 text-[10px] text-ink-700">
                      {initiative!=='—'&&<p><span className="text-ink-500 font-medium">先攻：</span>{initiative}</p>}
                      {saves!=='—'&&<p><span className="text-ink-500 font-medium">豁免：</span>{saves}</p>}
                      {skills!=='—'&&<p><span className="text-ink-500 font-medium">技能：</span>{skills}</p>}
                      {senses!=='—'&&<p><span className="text-ink-500 font-medium">感官：</span>{senses}</p>}
                      {languages!=='—'&&<p><span className="text-ink-500 font-medium">语言：</span>{languages}</p>}
                      {challenge!=='—'&&<p><span className="text-ink-500 font-medium">挑战等级：</span>{challenge} {xp!=='—'?`（XP ${xp}）`:''}</p>}
                    </div>
                  )}

                  {/* 描述 / 特性 / 动作 */}
                  {(b.description_zh || b.description)&&<p className="mt-2 text-[10px] text-ink-600 italic leading-relaxed">{(b.description_zh || b.description)}{b.description_zh && b.description ? <span className="text-ink-400">（原文：{translateMonsterDesc(b.description).slice(0,60)}...）</span> : null}</p>}
                  {(traits!=='—'||actions!=='—') && (
                    <div className="mt-2 border-t border-amber-900/10 pt-1.5 space-y-1 text-[10px] text-ink-700">
                      {traits!=='—'&&<p><span className="text-ink-500 font-medium">特性：</span>{traits}</p>}
                      {actions!=='—'&&<p><span className="text-ink-500 font-medium">动作：</span>{actions}</p>}
                    </div>
                  )}
                  {b.details && (
                    <div className="mt-2 border-t border-amber-900/10 pt-1.5 space-y-0.5 text-[10px] text-ink-600">
                      {b.details.habits&&<p>习性：{b.details.habits}</p>}
                      {b.details.habitat&&<p>栖息地：{b.details.habitat}</p>}
                      {b.details.lore&&<p>传说：{b.details.lore}</p>}
                    </div>
                  )}
                  {relatedMaps.length>0 && (
                    <div className="mt-2 pt-1.5 border-t border-amber-900/10">
                      <p className="text-[9px] text-ink-400 mb-0.5">关联地点</p>
                      <div className="flex flex-wrap gap-1">{relatedMaps.map(m=><span key={m.id} className="text-[10px] bg-indigo-50 text-indigo-700 border border-indigo-200 rounded px-1.5 py-0.5">{m.name}</span>)}</div>
                    </div>
                  )}
                  </div>
                </details>
              );
            })}
      </Modal>

      {/* 法术图鉴 */}
      <Modal
        open={showSpells}
        onClose={() => setShowSpells(false)}
        paper
        size="lg"
        icon="✨"
        title="法术 / 仪式"
        subtitle={currentSid ? '默认仅显示当前剧本条目；可切换显示通用参考' : '通用法术库（所有剧本可用）'}
        headExtra={
          <>
            <button onClick={()=>setShowSpellBuilder(v=>!v)} className="btn-xs-paper">
              {showSpellBuilder ? '收起自建' : '自建法术'}
            </button>
            <button onClick={translateSrd} disabled={srdTranslating} className="btn-xs-brand">
              {srdTranslating ? '机翻中...' : '翻译 SRD'}
            </button>
            {currentSid && (
              <button onClick={()=>setShowGlobalRefSpells(v=>!v)} className={`btn-xs ${showGlobalRefSpells ? 'border-brand-300 bg-brand-50 text-brand-700' : ''}`}>
                {showGlobalRefSpells ? '仅当前剧本' : '通用参考'}
              </button>
            )}
          </>
        }
      >
            {srdProgress && (
              <ProgressBar className="mb-3" label="批量机翻 SRD 法术" value={srdProgress.done} max={srdProgress.total} />
            )}
            <input value={spellQuery} onChange={e=>setSpellQuery(e.target.value)} placeholder="搜索法术 / 仪式…" className="input-field text-xs mb-3 !py-2" aria-label="搜索法术" />
            {showSpellBuilder && (
              <div className="rounded-xl border border-parch-400/50 bg-parch-100/60 p-3 space-y-2.5 mb-3">
                <p className="text-xs font-bold text-ink-700">自建法术 / 仪式</p>
                <div className="grid grid-cols-2 gap-2">
                  <input value={dmSpell.name} onChange={e=>setDmSpell({...dmSpell,name:e.target.value})} placeholder="法术名称 *" className="input-field text-xs" />
                  <input value={dmSpell.level} onChange={e=>setDmSpell({...dmSpell,level:e.target.value})} placeholder="环位（0=戏法）" className="input-field text-xs" />
                  <input value={dmSpell.school} onChange={e=>setDmSpell({...dmSpell,school:e.target.value})} placeholder="学派（塑能/防护/...）" className="input-field text-xs" />
                  <input value={dmSpell.casting_time} onChange={e=>setDmSpell({...dmSpell,casting_time:e.target.value})} placeholder="施法时间（1 动作）" className="input-field text-xs" />
                  <input value={dmSpell.range} onChange={e=>setDmSpell({...dmSpell,range:e.target.value})} placeholder="施法距离（150 尺/触及/自身）" className="input-field text-xs" />
                  <input value={dmSpell.components} onChange={e=>setDmSpell({...dmSpell,components:e.target.value})} placeholder="成分（V、S、M）" className="input-field text-xs" />
                  <input value={dmSpell.duration} onChange={e=>setDmSpell({...dmSpell,duration:e.target.value})} placeholder="持续时间（立即/专注）" className="input-field text-xs" />
                  <input value={dmSpell.classes} onChange={e=>setDmSpell({...dmSpell,classes:e.target.value})} placeholder="职业（术士、法师）" className="input-field text-xs" />
                </div>
                <label className="flex items-center gap-2 text-[10px] text-ink-500">
                  <input type="checkbox" checked={dmSpell.ritual} onChange={e=>setDmSpell({...dmSpell,ritual:e.target.checked})} /> 仪式法术
                </label>
                <textarea value={dmSpell.description} onChange={e=>setDmSpell({...dmSpell,description:e.target.value})} placeholder="效果描述（含伤害、豁免、升环效应）" rows={3} className="input-field text-xs resize-none w-full" />
                <button onClick={()=>{addDmSpell(); setShowSpellBuilder(false);}} className="btn-xs-paper mt-1">保存到当前剧本法术库</button>
              </div>
            )}
            {scopedSpells.filter(s=>!spellQuery || `${s.name_zh||s.name} ${s.school} ${s.level} ${s.description_zh||s.description} ${s.description}`.toLowerCase().includes(spellQuery.toLowerCase())).length===0 && (
              <EmptyState
                icon="✨"
                title="没有找到法术"
                hint={currentSid && !showGlobalRefSpells && scenarioSpells.length===0 ? '当前剧本暂无法术图鉴；点击右上角「通用参考」查看通用库。' : '可以调整搜索，或先导入法术图鉴 / 自建法术'}
              />
            )}
            {scopedSpells.filter(s=>!spellQuery || `${s.name_zh||s.name} ${s.school} ${s.level} ${s.description_zh||s.description} ${s.description}`.toLowerCase().includes(spellQuery.toLowerCase())).map(s=>(
              <details key={s.id} className="group entry-card p-2.5 mb-2">
                <summary className="cursor-pointer select-none flex items-center justify-between gap-2">
                  <span className="flex items-center gap-2 min-w-0">
                    <span className="paper-title text-sm font-bold truncate">{s.name_zh||s.name}：{Number(s.level)===0?'戏法':`${s.level}环`} {s.school}{s.name_zh&&s.name_zh!==s.name?<span className="text-ink-400 font-normal">（{s.name}）</span>:null}</span>
                    <span className={`scope-badge ${s.scenario_id ? 'scope-badge-scenario' : 'scope-badge-global'}`}>{s.scenario_id ? '当前剧本' : '通用参考'}</span>
                  </span>
                  <span className="text-[9px] text-ink-400 shrink-0">{s.ritual?'仪式 · ':''}{s.classes.length>0?`${s.classes.join('、')} · `:''}<span className="group-open:hidden">▸ 详情</span><span className="hidden group-open:inline">▾</span></span>
                </summary>
                <div className="mt-2 pt-2 border-t border-amber-900/10 text-[10px] text-ink-600 space-y-1">
                  {s.casting_time&&<p><span className="text-ink-400">施法时间：</span>{s.casting_time}</p>}
                  {s.range&&<p><span className="text-ink-400">施法距离：</span>{s.range}</p>}
                  {s.components&&<p><span className="text-ink-400">法术成分：</span>{s.components}</p>}
                  {s.duration&&<p><span className="text-ink-400">持续时间：</span>{s.duration}</p>}
                  {(s.description_zh||s.description)&&<p className="text-ink-700 whitespace-pre-line">{s.description_zh||s.description}</p>}
                  {s.description_zh&&s.description&&<p className="text-ink-400 italic whitespace-pre-line">原文：{s.description}</p>}
                </div>
              </details>
            ))}
      </Modal>

      {/* DM 工具：新增角色/地点/生物 */}
      <Modal
        open={showDmTools}
        onClose={() => setShowDmTools(false)}
        paper
        size="md"
        icon="🛠️"
        title="DM 工具"
        subtitle="手动补充角色 / 地点 / 生物 / 法术，立即写入当前剧本图鉴"
      >

            {/* 低 token 快捷工具说明 */}
            <div className="mb-4 border-b border-amber-900/10 pb-3">
              <p className="text-xs font-bold text-ink-700 mb-1">DM 低 token 快捷工具（Function Calling）</p>
              <p className="text-[10px] text-ink-500 leading-relaxed">
                get_character_state（查状态）· adjust_resource（资源增减）· cast_spell（扣法术位）·
                learn_spell / forget_spell（习得/遗忘法术）· search_npcs（查NPC）· adjust_npc（NPC数值增减）·
                search_bestiary / adjust_bestiary（查/改生物）· search_spells（查法术）
              </p>
            </div>

            {/* 新增角色/NPC */}
            <div className="mb-4 border-b border-amber-900/10 pb-3">
              <p className="text-xs font-bold text-ink-700 mb-2">新增角色 / NPC</p>
              <div className="grid grid-cols-2 gap-2">
                <input value={dmNpc.name} onChange={e=>setDmNpc({...dmNpc,name:e.target.value})} placeholder="名称 *" className="input-field text-xs" />
                <input value={dmNpc.role} onChange={e=>setDmNpc({...dmNpc,role:e.target.value})} placeholder="身份" className="input-field text-xs" />
                <input value={dmNpc.location} onChange={e=>setDmNpc({...dmNpc,location:e.target.value})} placeholder="位置" className="input-field text-xs" />
                <div className="flex gap-2">
                  <input type="number" value={dmNpc.hp} onChange={e=>setDmNpc({...dmNpc,hp:Number(e.target.value)||10})} placeholder="HP" className="input-field text-xs" />
                  <input type="number" value={dmNpc.ac} onChange={e=>setDmNpc({...dmNpc,ac:Number(e.target.value)||10})} placeholder="AC" className="input-field text-xs" />
                </div>
              </div>
              <input type="file" accept=".png,.jpg,.jpeg,.webp" onChange={e=>setDmNpcImage(e.target.files?.[0]||null)} className="block w-full text-[10px] mt-2 text-ink-500" />
              <button onClick={addDmNpc} className="mt-2 text-xs px-3 py-1.5 bg-amber-50 text-amber-700 rounded-lg border border-amber-200 hover:bg-amber-100">新增角色</button>
            </div>

            {/* 新增地点 */}
            <div className="mb-4 border-b border-amber-900/10 pb-3">
              <p className="text-xs font-bold text-ink-700 mb-2">新增地点</p>
              <div className="grid grid-cols-1 gap-2">
                <input value={dmMap.name} onChange={e=>setDmMap({...dmMap,name:e.target.value})} placeholder="地点名称 *" className="input-field text-xs" />
                <textarea value={dmMap.description} onChange={e=>setDmMap({...dmMap,description:e.target.value})} placeholder="描述" rows={2} className="input-field text-xs resize-none" />
              </div>
              <input type="file" accept=".png,.jpg,.jpeg,.webp" onChange={e=>setDmMapImage(e.target.files?.[0]||null)} className="block w-full text-[10px] mt-2 text-ink-500" />
              <button onClick={addDmMap} className="mt-2 text-xs px-3 py-1.5 bg-amber-50 text-amber-700 rounded-lg border border-amber-200 hover:bg-amber-100">新增地点</button>
            </div>

            {/* 新增生物 */}
            <div>
              <p className="text-xs font-bold text-ink-700 mb-2">新增生物（完整字段请在生物图鉴弹窗内填写）</p>
              <div className="grid grid-cols-2 gap-2">
                <input value={dmBeast.name} onChange={e=>setDmBeast({...dmBeast,name:e.target.value})} placeholder="生物名称 *" className="input-field text-xs" />
                <input value={dmBeast.tags} onChange={e=>setDmBeast({...dmBeast,tags:e.target.value})} placeholder="标签" className="input-field text-xs" />
                <input value={dmBeast.ac} onChange={e=>setDmBeast({...dmBeast,ac:e.target.value})} placeholder="AC" className="input-field text-xs" />
                <input value={dmBeast.hp} onChange={e=>setDmBeast({...dmBeast,hp:e.target.value})} placeholder="HP" className="input-field text-xs" />
              </div>
              <textarea value={dmBeast.description} onChange={e=>setDmBeast({...dmBeast,description:e.target.value})} placeholder="描述" rows={2} className="input-field text-xs resize-none mt-2 w-full" />
              <input type="file" accept=".png,.jpg,.jpeg,.webp" onChange={e=>setDmBeastImage(e.target.files?.[0]||null)} className="block w-full text-[10px] mt-2 text-ink-500" />
              <button onClick={addDmBeast} className="mt-2 text-xs px-3 py-1.5 bg-amber-50 text-amber-700 rounded-lg border border-amber-200 hover:bg-amber-100">新增生物</button>
            </div>

            {/* 新增法术/仪式（玩家/DM 自建） */}
            <div className="mt-4 pt-3 border-t border-amber-900/10">
              <p className="text-xs font-bold text-ink-700 mb-2">新增法术 / 仪式（玩家或 DM 自建）</p>
              <div className="grid grid-cols-2 gap-2">
                <input value={dmSpell.name} onChange={e=>setDmSpell({...dmSpell,name:e.target.value})} placeholder="法术名称 *" className="input-field text-xs" />
                <input value={dmSpell.level} onChange={e=>setDmSpell({...dmSpell,level:e.target.value})} placeholder="环位（0=戏法）" className="input-field text-xs" />
                <input value={dmSpell.school} onChange={e=>setDmSpell({...dmSpell,school:e.target.value})} placeholder="学派（塑能/防护/...）" className="input-field text-xs" />
                <input value={dmSpell.casting_time} onChange={e=>setDmSpell({...dmSpell,casting_time:e.target.value})} placeholder="施法时间（1 动作）" className="input-field text-xs" />
                <input value={dmSpell.range} onChange={e=>setDmSpell({...dmSpell,range:e.target.value})} placeholder="施法距离（150 尺/触及/自身）" className="input-field text-xs" />
                <input value={dmSpell.components} onChange={e=>setDmSpell({...dmSpell,components:e.target.value})} placeholder="成分（V、S、M）" className="input-field text-xs" />
                <input value={dmSpell.duration} onChange={e=>setDmSpell({...dmSpell,duration:e.target.value})} placeholder="持续时间（立即/专注）" className="input-field text-xs" />
                <input value={dmSpell.classes} onChange={e=>setDmSpell({...dmSpell,classes:e.target.value})} placeholder="职业（术士、法师）" className="input-field text-xs" />
                <label className="col-span-2 flex items-center gap-2 text-[10px] text-ink-500">
                  <input type="checkbox" checked={dmSpell.ritual} onChange={e=>setDmSpell({...dmSpell,ritual:e.target.checked})} /> 仪式法术
                </label>
                <textarea value={dmSpell.description} onChange={e=>setDmSpell({...dmSpell,description:e.target.value})} placeholder="效果描述（含伤害、豁免、升环效应）" rows={3} className="input-field text-xs resize-none col-span-2" />
              </div>
              <button onClick={addDmSpell} className="mt-2 text-xs px-3 py-1.5 bg-amber-50 text-amber-700 rounded-lg border border-amber-200 hover:bg-amber-100">新增法术</button>
            </div>
      </Modal>

      {/* 知识图谱（玩家视角，未暴露信息显示 ???） */}
      <Modal
        open={showGraph}
        onClose={() => setShowGraph(false)}
        paper
        size="3xl"
        icon="🕸️"
        title="关系图谱（玩家视角）"
        subtitle="拖动平移 · 滚轮缩放 · 双击复位；点击节点查看局部关系"
        headExtra={
          graphFocusId ? (
            <button onClick={()=>openGraph(undefined, '')} className="btn-xs-success">返回全图</button>
          ) : undefined
        }
      >

            <div className="flex gap-2 mb-2">
              <input
                value={graphQuery}
                onChange={e=>setGraphQuery(e.target.value)}
                onKeyDown={e=>{if(e.key==='Enter') openGraph(undefined, graphQuery);}}
                placeholder="搜索节点..."
                className="input-field text-xs flex-1"
              />
              <button onClick={()=>openGraph(undefined, graphQuery)} className="text-xs px-3 py-1.5 bg-emerald-50 text-emerald-700 rounded-lg border border-emerald-200 hover:bg-emerald-100">搜索</button>
              {(graphSearchIds.length > 0 || graphQuery) && (
                <button onClick={()=>{ setGraphSearchIds([]); setGraphSearchEmpty(false); setGraphQuery(''); }} className="text-xs px-2.5 py-1.5 text-ink-400 hover:text-ink-600">清除</button>
              )}
            </div>

            {graphSearchEmpty && (
              <p className="text-[10px] text-ink-400 mb-2">未找到匹配节点，已显示全部节点。</p>
            )}

            <div className="flex flex-wrap items-center gap-1.5 mb-2">
              {([['all','全部'],['npc','角色'],['location','地点'],['plot','剧情'],['creature','生物'],['other','其他']] as const).map(([k,label])=>(
                <button key={k} onClick={()=>setGraphTypeFilter(k)} aria-pressed={graphTypeFilter===k} className={`chip ${graphTypeFilter===k?'chip-active':''}`}>{label}</button>
              ))}
              <span className="ml-auto flex items-center gap-1">
                <button onClick={()=>zoomGraphAt(graphZoom-0.2, { x: GRAPH_W/2, y: GRAPH_H/2 })} className="icon-btn" aria-label="缩小" title="缩小">－</button>
                <button onClick={()=>{ setGraphZoom(1); setGraphPan({ x: 0, y: 0 }); }} className="text-2xs px-2 h-7 rounded-lg border border-ink-200 text-ink-500 hover:bg-ink-50 transition-colors">重置</button>
                <button onClick={()=>zoomGraphAt(graphZoom+0.2, { x: GRAPH_W/2, y: GRAPH_H/2 })} className="icon-btn" aria-label="放大" title="放大">＋</button>
              </span>
            </div>

            {graphView.truncated && (
              <p className="text-[10px] text-amber-700 mb-2">节点较多，已显示关联最多的 {graphView.visibleNodes.length}/{graphView.total} 个；点击节点可查看局部关系。</p>
            )}

            <div className="border border-gray-200 rounded-xl bg-white overflow-hidden">
              {graphView.visibleNodes.length === 0 ? (
                <div className="h-64 flex items-center justify-center">
                  <EmptyState icon="🕸️" title="没有符合条件的节点" hint="可以搜索节点名，或切换上方类型筛选。" />
                </div>
              ) : (
                <svg
                  ref={graphSvgRef}
                  viewBox={`0 0 ${GRAPH_W} ${GRAPH_H}`}
                  className="w-full h-auto touch-none select-none cursor-grab active:cursor-grabbing"
                  style={{ maxHeight: '76vh' }}
                  onPointerDown={(e)=>{
                    if(e.button!==0) return;
                    const svg=graphSvgRef.current;
                    if(!svg) return;
                    graphSuppressClickRef.current=false;
                    graphDragRef.current={dragging:true,startX:e.clientX,startY:e.clientY,startPanX:graphPan.x,startPanY:graphPan.y,moved:false};
                    try{svg.setPointerCapture(e.pointerId);}catch{}
                  }}
                  onPointerMove={(e)=>{
                    const st=graphDragRef.current;
                    if(!st?.dragging) return;
                    const dx=e.clientX-st.startX, dy=e.clientY-st.startY;
                    if(Math.abs(dx)+Math.abs(dy)>4){ st.moved=true; graphSuppressClickRef.current=true; }
                    const svg=graphSvgRef.current;
                    if(!svg) return;
                    const rect=svg.getBoundingClientRect();
                    const sx=GRAPH_W/Math.max(1,rect.width), sy=GRAPH_H/Math.max(1,rect.height);
                    setGraphPan({ x: st.startPanX+dx*sx, y: st.startPanY+dy*sy });
                  }}
                  onPointerUp={(e)=>{
                    const st=graphDragRef.current;
                    if(st) st.dragging=false;
                    try{graphSvgRef.current?.releasePointerCapture(e.pointerId);}catch{}
                  }}
                  onPointerCancel={()=>{ if(graphDragRef.current) graphDragRef.current.dragging=false; }}
                  onDoubleClick={()=>{ setGraphZoom(1); setGraphPan({ x:0, y:0 }); }}
                >
                  <g transform={`translate(${graphPan.x} ${graphPan.y}) scale(${graphZoom})`}>
                    {graphView.visibleEdges.map((e, i) => {
                      const p1 = graphView.layout.get(e.source);
                      const p2 = graphView.layout.get(e.target);
                      if (!p1 || !p2) return null;
                      const mx = (p1.x + p2.x) / 2;
                      const my = (p1.y + p2.y) / 2;
                      const hidden = e.relation === '???';
                      const hasActive = !!graphActive.activeId;
                      const related = !hasActive || e.source === graphActive.activeId || e.target === graphActive.activeId;
                      const showRelation = hasActive || graphView.visibleEdges.length <= 12;
                      return (
                        <g key={i}>
                          <line x1={p1.x} y1={p1.y} x2={p2.x} y2={p2.y}
                            stroke={hidden ? '#e5e7eb' : hasActive && related ? '#818cf8' : '#c7d2fe'}
                            strokeWidth={hasActive && related ? 1.6 : 1}
                            strokeDasharray={hidden ? '4 3' : undefined}
                            opacity={hasActive ? (related ? 1 : 0.12) : 0.45} />
                          {!hidden && related && showRelation && (
                            <text x={mx} y={my - 5} textAnchor="middle" fill="#9ca3af" fontSize="10.5"
                              stroke="#ffffff" strokeWidth="2.5" paintOrder="stroke" strokeLinejoin="round">{e.relation}</text>
                          )}
                          <title>{e.relation}{e.strength ? ` · 亲密度${e.strength}` : ''}{e.confidence ? ` · 置信度${e.confidence}` : ''}</title>
                        </g>
                      );
                    })}
                    {graphView.visibleNodes.map((n) => {
                      const p = graphView.layout.get(n.id);
                      if (!p) return null;
                      const hidden = n.label === '???';
                      const fill = hidden ? '#f3f4f6' : (GRAPH_COLORS[n.type] || GRAPH_COLORS.other);
                      const active = !graphActive.activeId || n.id === graphActive.activeId || graphActive.connected.has(n.id);
                      const focused = n.id === graphFocusId;
                      const matched = graphSearchIds.includes(n.id);
                      const showLabel = graphView.visibleNodes.length <= 16 || active || focused || matched;
                      const r = focused ? 26 : hidden ? 10 : matched ? 20 : 17;
                      return (
                        <g key={n.id}
                          onClick={()=>{
                            if (graphSuppressClickRef.current) { graphSuppressClickRef.current=false; return; }
                            if (!hidden) openGraph(n.id, '');
                          }}
                          onMouseEnter={()=>setGraphHoverId(n.id)}
                          onMouseLeave={()=>setGraphHoverId(null)}
                          className={hidden ? 'cursor-default' : 'cursor-pointer'}
                          opacity={active ? 1 : 0.35}>
                          <title>{n.label}（{GRAPH_TYPE_LABELS[n.type] || n.type}）{n.extra ? ` · ${n.extra}` : ''}</title>
                          {matched && <circle cx={p.x} cy={p.y} r={r + 4} fill="none" stroke="#f59e0b" strokeWidth="1.5" strokeDasharray="3 2" />}
                          <circle cx={p.x} cy={p.y} r={r}
                            fill={fill}
                            stroke={hidden ? '#9ca3af' : focused ? '#4f46e5' : matched ? '#f59e0b' : '#6366f1'}
                            strokeWidth={focused ? 3.5 : hidden ? 1 : matched ? 2.8 : 2} />
                          {showLabel && (
                            <text x={p.x} y={p.y + r + 14} textAnchor="middle" fontSize={focused ? 13 : 11}
                              fill={hidden ? '#9ca3af' : '#1f2937'} fontWeight="bold"
                              stroke="#ffffff" strokeWidth="3" paintOrder="stroke" strokeLinejoin="round">{n.label}</text>
                          )}
                          {focused && n.extra && (
                            <text x={p.x} y={p.y + r + 28} textAnchor="middle" fontSize="9.5" fill="#6b7280">{n.extra.slice(0, 18)}</text>
                          )}
                        </g>
                      );
                    })}
                  </g>
                </svg>
              )}
            </div>

            <div className="flex items-center gap-3 mt-2 text-[10px] text-ink-400">
              <span><span className="inline-block w-2.5 h-2.5 rounded-full align-middle mr-1" style={{background:GRAPH_COLORS.npc}} />角色</span>
              <span><span className="inline-block w-2.5 h-2.5 rounded-full align-middle mr-1" style={{background:GRAPH_COLORS.location}} />地点</span>
              <span><span className="inline-block w-2.5 h-2.5 rounded-full align-middle mr-1" style={{background:GRAPH_COLORS.plot}} />剧情</span>
              <span><span className="inline-block w-2.5 h-2.5 rounded-full align-middle mr-1" style={{background:GRAPH_COLORS.creature}} />生物</span>
              <span className="ml-auto">灰色虚线 = 关联未暴露</span>
            </div>
      </Modal>
    </div>
  );
}
