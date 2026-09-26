/** 关系图谱画布：力导向 SVG、拖动平移、滚轮缩放与节点点击。 */
import EmptyState from '../ui/EmptyState';
import { GRAPH_COLORS, GRAPH_H, GRAPH_TYPE_LABELS, GRAPH_W, graphRelationLabel } from './graphLayout';

export default function GraphCanvas({
  graphView, graphActive, graphFocusId, graphSearchIds,
  graphSvgRef, graphDragRef, graphSuppressClickRef,
  graphPan, graphZoom, setGraphPan, setGraphZoom, setGraphHoverId, openGraph,
}: {
  [key: string]: any;
}) {
  // 节点"圆 + 下方标签"的占位盒：关系文字与它相交就不画，避免两段文字压在一起。
  // 标签居中画在节点下方，宽度按 11px/字 估算。
  const nodeZones: { x: number; y: number; w: number; r: number }[] = graphView.visibleNodes
    .map((n: any) => {
      const p = graphView.layout?.get?.(n.id);
      if (!p) return null;
      return { x: p.x, y: p.y, w: Math.max(36, String(n.label || '').length * 11), r: 17 };
    })
    .filter(Boolean);
  const relationLabelFits = (x: number, y: number, text: string) => {
    const half = Math.max(30, text.length * 11) / 2;
    return !nodeZones.some((z) =>
      Math.abs(x - z.x) < half + z.w / 2 && y > z.y - z.r - 10 && y < z.y + z.r + 30);
  };

  return (
    // 画布高度定在弹窗可视区内：以前用 aspect-[3/2]，在 1400px 宽的弹窗里会算出 892px 高，
    // 超出正文可用高度（约 700px）——底部节点被下沿裁掉，还要滚动才看得到图例。
    // 现在盒子高度确定，viewBox 交给 preserveAspectRatio 等比内缩，节点永远完整。
    <div className="border border-gray-200 rounded-xl bg-white overflow-hidden h-[min(58vh,600px)] min-h-[300px]">
      {graphView.visibleNodes.length === 0 ? (
        <div className="h-full flex items-center justify-center">
          <EmptyState icon="🕸️" title="没有符合条件的节点" hint="可以搜索节点名，或切换上方类型筛选。" />
        </div>
      ) : (
        <svg
          ref={graphSvgRef}
          viewBox={`0 0 ${GRAPH_W} ${GRAPH_H}`}
          // 盒子比例由父级高度决定（可能比 viewBox 的 3:2 更宽），交给 meet 等比内缩、左右留白，
          // 比"强制盒子 3:2 + 溢出裁切"稳：任何时候都不会有节点被切掉。
          preserveAspectRatio="xMidYMid meet"
          className="w-full h-full touch-none select-none cursor-grab active:cursor-grabbing"
          onPointerDown={(e: any) => {
            if (e.button !== 0) return;
            const svg = graphSvgRef.current;
            if (!svg) return;
            graphSuppressClickRef.current = false;
            graphDragRef.current = {
              dragging: true, startX: e.clientX, startY: e.clientY,
              startPanX: graphPan.x, startPanY: graphPan.y, moved: false,
            };
            try { svg.setPointerCapture(e.pointerId); } catch { /* 指针捕获失败不影响点击 */ }
          }}
          onPointerMove={(e: any) => {
            const st = graphDragRef.current;
            if (!st?.dragging) return;
            const dx = e.clientX - st.startX, dy = e.clientY - st.startY;
            if (Math.abs(dx) + Math.abs(dy) > 4) {
              st.moved = true;
              graphSuppressClickRef.current = true;
            }
            const svg = graphSvgRef.current;
            if (!svg) return;
            const rect = svg.getBoundingClientRect();
            // meet 是等比内缩：屏幕位移除以同一个比例才是 viewBox 位移
            const scale = Math.min(rect.width / GRAPH_W, rect.height / GRAPH_H) || 1;
            setGraphPan({ x: st.startPanX + dx / scale, y: st.startPanY + dy / scale });
          }}
          onPointerUp={(e: any) => {
            const st = graphDragRef.current;
            if (st) st.dragging = false;
            try { graphSvgRef.current?.releasePointerCapture(e.pointerId); } catch { /* 指针已释放 */ }
          }}
          onPointerCancel={() => { if (graphDragRef.current) graphDragRef.current.dragging = false; }}
          onDoubleClick={() => { setGraphZoom(1); setGraphPan({ x: 0, y: 0 }); }}
        >
          <g transform={`translate(${graphPan.x} ${graphPan.y}) scale(${graphZoom})`}>
            {graphView.visibleEdges.map((e: any, i: any) => {
              const p1 = graphView.layout.get(e.source);
              const p2 = graphView.layout.get(e.target);
              if (!p1 || !p2) return null;
              const hidden = e.relation === '???';
              const hasActive = !!graphActive.activeId;
              const related = !hasActive || e.source === graphActive.activeId || e.target === graphActive.activeId;
              const showRelation = hasActive || graphView.visibleEdges.length <= 12;
              const relationText = graphRelationLabel(String(e.relation || ''));
              // 关系文字优先放中点；中点被节点/标签压住就沿连线左右挪一挪，实在放不下才不画
              // （完整关系始终在连线 <title> 里）。实测"直接画在中点"会压出 "note_c…" 这种残片。
              const labelPos = hidden || !related || !showRelation ? null
                : [0.5, 0.38, 0.62, 0.28, 0.72]
                    .map((t) => ({ x: p1.x + (p2.x - p1.x) * t, y: p1.y + (p2.y - p1.y) * t - 5 }))
                    .find((pt) => relationLabelFits(pt.x, pt.y, relationText)) || null;
              return (
                <g key={i}>
                  <line x1={p1.x} y1={p1.y} x2={p2.x} y2={p2.y}
                    stroke={hidden ? '#e5e7eb' : hasActive && related ? '#818cf8' : '#c7d2fe'}
                    strokeWidth={hasActive && related ? 1.6 : 1}
                    strokeDasharray={hidden ? '4 3' : undefined}
                    opacity={hasActive ? (related ? 1 : 0.12) : 0.45} />
                  {labelPos && (
                    <text x={labelPos.x} y={labelPos.y} textAnchor="middle" fill="#9ca3af" fontSize="10.5"
                      stroke="#ffffff" strokeWidth="2.5" paintOrder="stroke" strokeLinejoin="round">{relationText}</text>
                  )}
                  <title>{relationText}{e.strength ? ` · 亲密度${e.strength}` : ''}{e.confidence ? ` · 置信度${e.confidence}` : ''}</title>
                </g>
              );
            })}
            {graphView.visibleNodes.map((n: any) => {
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
                  onClick={() => {
                    if (graphSuppressClickRef.current) { graphSuppressClickRef.current = false; return; }
                    if (!hidden) openGraph(n.id, '');
                  }}
                  onMouseEnter={() => setGraphHoverId(n.id)}
                  onMouseLeave={() => setGraphHoverId(null)}
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
                  {/* 节点附注不再画在画布上：18 字截断会留下 "note_c…" 这种残片，看起来像故障。
                      完整信息在节点 <title> 悬停提示里（label · 类型 · extra）。 */}
                </g>
              );
            })}
          </g>
        </svg>
      )}
    </div>
  );
}
