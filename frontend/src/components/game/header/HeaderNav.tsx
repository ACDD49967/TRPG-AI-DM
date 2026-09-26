/** 顶栏导航工具条：窄屏图标化，保留 aria-label/title。 */
import type { GameHeaderHandlers } from '../GameHeader';

export default function HeaderNav({ handlers }: { handlers: GameHeaderHandlers }) {
  return (
    <>
      <button onClick={() => handlers.onRulebook()} className="nav-btn" title="玩家说明书" aria-label="玩家说明书">
        <span aria-hidden>📕</span><span className="hidden sm:inline">说明书</span>
      </button>
      <button onClick={() => handlers.onCharSheet()} className="nav-btn" title="角色卡" aria-label="角色卡">
        <span aria-hidden>🧙</span><span className="hidden sm:inline">角色卡</span>
      </button>
      <button onClick={() => handlers.onGraph()} className="nav-btn" title="关系图谱" aria-label="关系图谱">
        <span aria-hidden>🕸️</span><span className="hidden sm:inline">图谱</span>
      </button>
      <button onClick={() => handlers.onMap()} className="nav-btn" title="地点 / 地图图鉴" aria-label="地图图鉴">
        <span aria-hidden>🗺️</span><span className="hidden sm:inline">地图</span>
      </button>
      <button onClick={() => handlers.onBeast()} className="nav-btn" title="生物图鉴" aria-label="生物图鉴">
        <span aria-hidden>🐾</span><span className="hidden sm:inline">图鉴</span>
      </button>
      <button onClick={() => handlers.onSpells()} className="nav-btn" title="法术 / 仪式" aria-label="法术图鉴">
        <span aria-hidden>✨</span><span className="hidden sm:inline">法术</span>
      </button>
      <span className="hidden sm:block w-px h-4 bg-ink-200 mx-0.5" aria-hidden />
      <button onClick={() => handlers.onDmTools()} className="nav-btn text-amber-700 hover:bg-amber-50" title="DM 工具" aria-label="DM 工具">
        <span aria-hidden>🛠️</span><span className="hidden sm:inline">DM</span>
      </button>
      <button onClick={() => handlers.onEdit()} className="nav-btn" title="编辑与调整" aria-label="编辑与调整">
        <span aria-hidden>✏️</span><span className="hidden sm:inline">编辑</span>
      </button>
      <button onClick={handlers.onSave} className="nav-btn" title="手动存档" aria-label="手动存档">
        <span aria-hidden>💾</span><span className="hidden sm:inline">存档</span>
      </button>
      <button onClick={handlers.onExit} className="nav-btn" title="返回大厅" aria-label="返回大厅">
        <span aria-hidden>🚪</span><span className="hidden sm:inline">大厅</span>
      </button>
    </>
  );
}
