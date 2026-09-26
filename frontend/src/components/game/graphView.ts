/** 关系图谱派生：类型/焦点/搜索过滤、度数排序与力导向布局。 */
import { GRAPH_H, GRAPH_W, computeGraphLayout } from './graphLayout';
import type { GraphEdge, GraphNode } from './graphLayout';

export type GraphData = { nodes: GraphNode[]; edges: GraphEdge[] } | null;
export type GraphTypeFilter = 'all' | 'npc' | 'location' | 'plot' | 'creature' | 'other';

export function clampGraphZoom(z: number): number {
  return Math.max(0.35, Math.min(3, +z.toFixed(3)));
}

export function buildGraphView(
  graphData: GraphData,
  graphFocusId: string | null,
  graphTypeFilter: GraphTypeFilter,
  graphSearchIds: string[],
) {
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
      || n.id === graphFocusId,
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
    (degree.get(b.id) || 0) - (degree.get(a.id) || 0) || a.label.localeCompare(b.label),
  );
  const total = nodes.length;
  const visibleNodes = nodes.slice(0, 24);
  const visibleIds = new Set(visibleNodes.map(n => n.id));
  const visibleEdges = allEdges.filter(e => visibleIds.has(e.source) && visibleIds.has(e.target));
  const layout = computeGraphLayout(visibleNodes, visibleEdges, graphFocusId);
  return {
    allNodes, allEdges, visibleNodes, visibleEdges, layout,
    total, truncated: total > 24,
  };
}

export function buildGraphActive(
  graphFocusId: string | null,
  graphHoverId: string | null,
  visibleEdges: GraphEdge[],
) {
  const activeId = graphFocusId || graphHoverId;
  const connected = new Set<string>();
  if (activeId) {
    connected.add(activeId);
    visibleEdges.forEach(e => {
      if (e.source === activeId) connected.add(e.target);
      if (e.target === activeId) connected.add(e.source);
    });
  }
  return { activeId, connected };
}

export { GRAPH_H, GRAPH_W };
