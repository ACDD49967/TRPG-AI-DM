/**
 * 关系图谱的状态与交互（打开/搜索/筛选/缩放/平移）。
 *
 * 从 GameScreen 拆出：这组 13 个 state/ref 与约 130 行派生逻辑只服务 GraphModal，
 * 留在页面组件里让主界面同时背着"弹窗编排"和"图谱实现"两件事。
 * 依赖只有会话 id 与用户名。
 */
import { useEffect, useMemo, useRef, useState } from 'react';
import { GRAPH_H, GRAPH_W } from './graphLayout';
import type { GraphEdge, GraphNode } from './graphLayout';
import { buildGraphActive, buildGraphView, clampGraphZoom } from './graphView';

export function useGraphState({ sessionId, username }: { sessionId: string; username: string }) {
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

  const openGraph = async (name?: string, queryOverride?: string) => {
    if (!sessionId) return;
    try {
      const params = new URLSearchParams();
      params.set('username', username || 'default');
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

  const graphView = useMemo(
    () => buildGraphView(graphData, graphFocusId, graphTypeFilter, graphSearchIds),
    [graphData, graphTypeFilter, graphFocusId, graphSearchIds],
  );

  const graphActive = useMemo(
    () => buildGraphActive(graphFocusId, graphHoverId, graphView.visibleEdges),
    [graphFocusId, graphHoverId, graphView.visibleEdges],
  );
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

  return {
    graphActive, graphData, graphDragRef, graphFocusId, graphHoverId, graphPan, graphQuery,
    graphSearchEmpty, graphSearchIds, graphSuppressClickRef, graphSvgRef, graphTypeFilter,
    graphView, graphZoom, openGraph, setGraphHoverId, setGraphPan, setGraphQuery,
    setGraphSearchEmpty, setGraphSearchIds, setGraphTypeFilter, setGraphZoom, setShowGraph,
    showGraph, zoomGraphAt,
  };
}
