/** 顶栏右侧：角色 HP、身份与移动端抽屉入口。 */
import type { GameHeaderHandlers } from '../GameHeader';

export default function HeaderStatus({
  status, hpTone, sessionId, handlers,
}: {
  status: { character_name?: string; race?: string; char_class?: string; hp: number; maxHp: number };
  hpTone: string;
  sessionId: string | null;
  handlers: GameHeaderHandlers;
}) {
  return (
    <>
      <button
        onClick={() => handlers.onCharSheet()}
        className={`inline-flex items-center gap-1.5 text-2xs font-mono font-semibold px-2 py-1 min-h-[44px] rounded-lg border transition-colors ${hpTone}`}
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
      <div className="flex items-center gap-1 md:hidden">
        <button onClick={() => handlers.onMobileStatus()} className="nav-btn" aria-label="角色状态">
          <span aria-hidden>📋</span>
        </button>
        <button onClick={() => handlers.onMobileJournal()} className="nav-btn" aria-label="冒险笔记">
          <span aria-hidden>📓</span>
        </button>
      </div>
    </>
  );
}
