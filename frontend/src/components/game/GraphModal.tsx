/** 知识图谱弹窗：力导向布局、搜索、类型筛选、缩放拖动。
 *
 * 从 GameScreen 拆出：依赖经 props 显式传入，行为与拆分前一致。
 */
import Modal from '../ui/Modal';
import { GRAPH_COLORS, GRAPH_H, GRAPH_TYPE_LABELS, GRAPH_W } from './graphLayout';
import GraphCanvas from './GraphCanvas';

export interface GraphModalProps {
  [key: string]: any;
}

export default function GraphModal(props: GraphModalProps) {
  const {
    GRAPH_COLORS,
    GRAPH_H,
    GRAPH_TYPE_LABELS,
    GRAPH_W,
    graphActive,
    graphDragRef,
    graphFocusId,
    graphPan,
    graphQuery,
    graphSearchEmpty,
    graphSearchIds,
    graphSuppressClickRef,
    graphSvgRef,
    graphTypeFilter,
    graphView,
    graphZoom,
    openGraph,
    setGraphHoverId,
    setGraphPan,
    setGraphQuery,
    setGraphSearchEmpty,
    setGraphSearchIds,
    setGraphTypeFilter,
    setGraphZoom,
    setShowGraph,
    showGraph,
    zoomGraphAt,
  } = props;

  return (
    <>
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
                    onChange={(e: any) =>setGraphQuery(e.target.value)}
                    onKeyDown={(e: any) =>{if(e.key==='Enter') openGraph(undefined, graphQuery);}}
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

                <GraphCanvas
                  graphView={graphView}
                  graphActive={graphActive}
                  graphFocusId={graphFocusId}
                  graphSearchIds={graphSearchIds}
                  graphSvgRef={graphSvgRef}
                  graphDragRef={graphDragRef}
                  graphSuppressClickRef={graphSuppressClickRef}
                  graphPan={graphPan}
                  graphZoom={graphZoom}
                  setGraphPan={setGraphPan}
                  setGraphZoom={setGraphZoom}
                  setGraphHoverId={setGraphHoverId}
                  openGraph={openGraph}
                />

                <div className="flex items-center gap-3 mt-2 text-[10px] text-ink-400">
                  <span><span className="inline-block w-2.5 h-2.5 rounded-full align-middle mr-1" style={{background:GRAPH_COLORS.npc}} />角色</span>
                  <span><span className="inline-block w-2.5 h-2.5 rounded-full align-middle mr-1" style={{background:GRAPH_COLORS.location}} />地点</span>
                  <span><span className="inline-block w-2.5 h-2.5 rounded-full align-middle mr-1" style={{background:GRAPH_COLORS.plot}} />剧情</span>
                  <span><span className="inline-block w-2.5 h-2.5 rounded-full align-middle mr-1" style={{background:GRAPH_COLORS.creature}} />生物</span>
                  <span className="ml-auto">灰色虚线 = 关联未暴露</span>
                </div>
          </Modal>
    </>
  );
}
