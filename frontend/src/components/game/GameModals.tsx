/** 游戏内全部弹窗的装配：角色卡 / 规则书 / 升级 / 编辑面板 / 地图 / 图鉴 / 法术 / DM 工具 / 图谱。
 *
 * 从 `GameScreen` 拆出——那边只留三栏布局与顶栏导航，弹窗在这里集中接线。
 *
 * **按需加载**：这些弹窗只在玩家点开时才需要，之前一律静态 import，全都进了首屏包
 * （主 chunk 335 kB，构建器一直告警）。现在改成 `lazy` + 打开时才挂载：
 * 只有 `showX` 为真才渲染，Suspense 兜住加载间隙；角色卡/图鉴/法术/地图/编辑面板/
 * 升级/DM 工具/图谱各自成为独立 chunk，跑团页面更快可用。
 */
import { Suspense, lazy } from 'react';
import { useGameStore } from '../../store/gameStore';
import { GRAPH_COLORS, GRAPH_H, GRAPH_TYPE_LABELS, GRAPH_W } from './graphLayout';
import { ATTR_CN, crToXp, translateMonsterDesc } from './monsterFormat';
import { getXpDisplay } from '../../gameSystems';
import { textValue } from '../../utils/textValue';

const CharacterSheetModal = lazy(() => import('./CharacterSheetModal'));
const RulebookModal = lazy(() => import('../RulebookModal'));
const LevelUpModal = lazy(() => import('../LevelUpModal'));
const EditPanel = lazy(() => import('./EditPanel'));
const MapModal = lazy(() => import('./MapModal'));
const BeastModal = lazy(() => import('./BeastModal'));
const SpellModal = lazy(() => import('./SpellModal'));
const DmToolsModal = lazy(() => import('./DmToolsModal'));
const GraphModal = lazy(() => import('./GraphModal'));

function invName(it: string | { name: string }): string {
  return typeof it === 'string' ? it : it.name || '未知物品';
}

export default function GameModals(props: any) {
  const {
    media, graph, status, sessionId, sessionUser,
    showCharSheet, setShowCharSheet, showRulebook, setShowRulebook,
    showEditPanel, setShowEditPanel, showMap, setShowMap,
    showBeast, setShowBeast, showDmTools, setShowDmTools,
  } = props;
  const isDndSheet = status.game_system === 'dnd5e' || status.game_system === 'dnd4e';
  // 升级弹窗自己从 store 取数据；这里只看"有没有待分配升级"来决定要不要加载它
  const pendingLevelUp = useGameStore((s) => s.pendingLevelUp);

  return (
    <Suspense fallback={null}>
      {showCharSheet && (
        <CharacterSheetModal {...{ATTR_CN, getXpDisplay, invName, isDndSheet, setShowCharSheet, showCharSheet, status, textValue}} />
      )}

      {showRulebook && <RulebookModal onClose={() => setShowRulebook(false)} />}
      {pendingLevelUp ? <LevelUpModal /> : null}
      {showEditPanel && sessionId && (
        <EditPanel
          sessionId={sessionId}
          username={sessionUser}
          onClose={() => setShowEditPanel(false)}
          onChanged={() => { try { window.dispatchEvent(new Event('dnd:journal-refresh')); } catch { /* 忽略 */ } }}
        />
      )}

      {/* 注意：地图/生物的开关是 GameScreen 的局部 state，走独立 prop，不在 media 里 */}
      {showMap && <MapModal {...{...media, setShowMap, showMap, status }} />}

      {showBeast && (
        <BeastModal {...{...media, crToXp, setShowBeast, showBeast, status, textValue, translateMonsterDesc }} />
      )}

      {/* 法术图鉴 */}
      {media.showSpells && <SpellModal {...{...media, status }} />}

      {/* DM 工具：新增角色/地点/生物 */}
      {showDmTools && <DmToolsModal {...{...media, setShowDmTools, showDmTools }} />}

      {/* 知识图谱（玩家视角，未暴露信息显示 ???） */}
      {graph.showGraph && (
        <GraphModal {...{...graph, GRAPH_COLORS, GRAPH_H, GRAPH_TYPE_LABELS, GRAPH_W}} />
      )}
    </Suspense>
  );
}
