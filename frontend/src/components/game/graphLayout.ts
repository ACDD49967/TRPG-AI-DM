/** 图谱布局与配色：力导向布局、节点/边类型、画布尺寸。从 GameScreen 拆出。 */
export type GraphNode = { id: string; type: string; label: string; extra?: string };
export type GraphEdge = { source: string; target: string; relation: string; strength?: number; confidence?: number; notes?: string };

export const GRAPH_COLORS: Record<string, string> = {
  npc: '#c7d2fe', location: '#bbf7d0', plot: '#fde68a', creature: '#fecaca', other: '#e5e7eb',
};
export const GRAPH_TYPE_LABELS: Record<string, string> = {
  npc: '角色', location: '地点', plot: '剧情', creature: '生物', other: '其他',
};
/** 机器关系名 → 玩家读得懂的词。
 *  图上直接画 note_link / note_context / co_involved 看起来像故障（实测被当成渲染残片），
 *  这几个 id 是内部标记，不是剧情语言。 */
export const GRAPH_RELATION_LABELS: Record<string, string> = {
  note_link: '笔记关联', note_context: '背景关联', co_involved: '共同卷入',
};
export const graphRelationLabel = (relation: string) =>
  GRAPH_RELATION_LABELS[relation] || relation;
export const GRAPH_W = 1200;
export const GRAPH_H = 800;

/** 简单的力导向布局：限制节点数后自动分散，减少重叠与连线密集感。 */
export function computeGraphLayout(nodes: GraphNode[], edges: GraphEdge[], focusId?: string | null): Map<string, { x: number; y: number }> {
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
  }
  // 边界收敛**始终**做：节点半径 17，标签还要在节点上下各占约 22px，
  // 实测 3 个孤立节点时 y 会跑到 710/748（viewBox 只有 800），标签贴着画布下沿像被裁掉。
  // 留出 110 的上下边距、80 的左右边距后，节点与标签都稳稳在画布内。
  result.forEach((v, id) => result.set(id, {
    x: Math.max(80, Math.min(W - 80, v.x)),
    y: Math.max(110, Math.min(H - 110, v.y)),
  }));
  // 稀疏图谱会被 openGraph 放大（≤6 个节点时 ×1.35、≤12 时 ×1.15，免得大画布上节点太小）。
  // 所以这里先把稀疏布局向中心收一收：放大之后仍然完整落在画布内，
  // 否则"边界收敛"与"自动放大"会互相打架，节点又被推出画布（实测裁掉 3 个节点）。
  const sparseShrink = n <= 6 ? 0.5 : n <= 12 ? 0.72 : 1;
  if (sparseShrink < 1) {
    result.forEach((v, id) => result.set(id, {
      x: cx + (v.x - cx) * sparseShrink,
      y: cy + (v.y - cy) * sparseShrink,
    }));
    // 收缩会把节点拉近：再跑几步"最小间距"分离。
    // 间距按 110 计——标签画在节点下方、宽度可达 80px，间距太小标签会压到下一个节点
    // （实测 5 个节点里两个的标签互相盖住）。放大 1.35 倍后约 170px 屏幕距离，够用。
    const MIN_GAP = 110;
    const ids = [...result.keys()];
    for (let iter = 0; iter < 12; iter++) {
      let moved = false;
      for (let a = 0; a < ids.length; a++) {
        for (let b = a + 1; b < ids.length; b++) {
          const pa = result.get(ids[a])!, pb = result.get(ids[b])!;
          let dx = pb.x - pa.x, dy = pb.y - pa.y;
          let dist = Math.sqrt(dx * dx + dy * dy);
          if (dist >= MIN_GAP) continue;
          if (dist < 0.01) {                    // 完全重合：随便挑个方向推开
            dx = Math.cos(a + b), dy = Math.sin(a + b);
            dist = 1;
          }
          const push = (MIN_GAP - dist) / 2;
          const ux = dx / dist, uy = dy / dist;
          result.set(ids[a], { x: pa.x - ux * push, y: pa.y - uy * push });
          result.set(ids[b], { x: pb.x + ux * push, y: pb.y + uy * push });
          moved = true;
        }
      }
      if (!moved) break;
    }
    // 分离后再夹一次边界，保证不会因为推开而越界
    result.forEach((v, id) => result.set(id, {
      x: Math.max(80, Math.min(W - 80, v.x)),
      y: Math.max(110, Math.min(H - 110, v.y)),
    }));
  }
  return result;
}

