/** 游戏主界面 —— 三栏布局（状态 / 叙事 / 笔记），移动端折叠为抽屉 */
import GameHeader from './game/GameHeader';
import { useMediaLibrary } from './game/useMediaLibrary';
import { useGraphState } from './game/useGraphState';
import GameModals from './game/GameModals';

import { useState } from 'react';
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
import Modal from './ui/Modal';

export default function GameScreen() {
  const { sessionId, goToStart, sceneInfo, status, mediaVersion } = useGameStore();
  // 读档后 status.username 要等首个 SSE 事件才填上；此前若直接用空值查询会落到 default 而 404。
  // 与 useSSE 的兜底保持一致：本地登录名优先。
  const sessionUser = status.username
    || (typeof localStorage !== 'undefined' ? localStorage.getItem('dnd_auth_user') : '')
    || 'default';
  const graph = useGraphState({ sessionId: sessionId || '', username: sessionUser });
  const { openGraph } = graph;
  const media = useMediaLibrary({
    sessionId: sessionId || '', username: sessionUser,
    gameSystem: status.game_system || 'dnd5e', scenarioId: status.scenario_id || '', mediaVersion,
  });
  const { currentSid, setShowSpells } = media;

  useSSE(sessionId);
  const [showMap, setShowMap] = useState(false);
  const [showBeast, setShowBeast] = useState(false);
  const [showRulebook, setShowRulebook] = useState(false);
  const [showCharSheet, setShowCharSheet] = useState(false);
  /** 移动端抽屉：状态 / 笔记（桌面端三栏常驻，不需要抽屉） */
  const [mobilePanel, setMobilePanel] = useState<'status' | 'journal' | null>(null);
  const [showDmTools, setShowDmTools] = useState(false);
  const [showEditPanel, setShowEditPanel] = useState(false);


  const saveGame = async () => {
    if (!sessionId) {
      useToastStore.getState().showToast('还没有进行中的游戏，无法存档', 'error');
      return;
    }
    try {
      // 归属必须带上：后端按 username 查会话，漏了就会落到 default → 非 default 账号一律 404
      const r = await fetch(`/api/game/${sessionId}/save?username=${encodeURIComponent(sessionUser)}`, {
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


  return (
    <div className="h-screen h-[100dvh] flex flex-col bg-white/60">
      {/* 顶栏：品牌 + 场景 + 角色数值 + 导航（实现见 game/GameHeader） */}
      <GameHeader
        sceneInfo={sceneInfo}
        status={status}
        hpTone={hpTone}
        sessionId={sessionId}
        scenarioId={currentSid}
        handlers={{
          onRulebook: () => setShowRulebook(true),
          onCharSheet: () => setShowCharSheet(true),
          onGraph: () => openGraph(undefined, ''),
          onMap: () => setShowMap(true),
          onBeast: () => setShowBeast(true),
          onSpells: () => setShowSpells(true),
          onDmTools: () => setShowDmTools(true),
          onEdit: () => setShowEditPanel(true),
          onSave: saveGame,
          onExit: goToStart,
          onMobileStatus: () => setMobilePanel('status'),
          onMobileJournal: () => setMobilePanel('journal'),
        }}
      />

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

      {/* 其余弹窗（角色卡/规则书/升级/编辑/地图/图鉴/法术/DM 工具/图谱）见 game/GameModals */}
      <GameModals {...{
        media, graph, status, sessionId, sessionUser,
        showCharSheet, setShowCharSheet, showRulebook, setShowRulebook,
        showEditPanel, setShowEditPanel, showMap, setShowMap,
        showBeast, setShowBeast, showDmTools, setShowDmTools,
      }} />
    </div>
  );
}
