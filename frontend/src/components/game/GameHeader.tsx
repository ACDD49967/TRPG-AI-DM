/** 顶栏：品牌 + 场景 + 角色数值 + 导航（从 GameScreen 拆出）。
 *
 * 九个导航按钮在 390px 下横滑会藏掉一半，收成图标后一行放得下，并保留 aria-label/title。
 * 所有动作经 `handlers` 传入，组件本身不碰 store，便于单独测/改样式。
 */
import HeaderNav from './header/HeaderNav';
import HeaderStatus from './header/HeaderStatus';

export interface GameHeaderHandlers {
  onRulebook: () => void;
  onCharSheet: () => void;
  onGraph: () => void;
  onMap: () => void;
  onBeast: () => void;
  onSpells: () => void;
  onDmTools: () => void;
  onEdit: () => void;
  onSave: () => void;
  onExit: () => void;
  onMobileStatus: () => void;
  onMobileJournal: () => void;
}

/** 光照 → 图标：后端给的是归一后的中文，这里只在显示层做视觉强化。 */
function lightIcon(light?: string): string {
  const text = (light || '').trim();
  if (/明亮|bright|日|阳光|火把|光明/.test(text)) return '☀';
  if (/微光|dim|黄昏|黎明|月光|昏暗/.test(text)) return '🌤';
  if (/黑暗|dark|夜|漆黑|无光/.test(text)) return '🌑';
  return '💡';
}

export default function GameHeader({ sceneInfo, status, hpTone, sessionId, scenarioId, handlers }: {
  sceneInfo: {
    location: string; time?: string; weather?: string; npcs_here: string[];
    light?: string; light_source?: string;
  };
  status: { character_name?: string; race?: string; char_class?: string; level?: number; hp: number; maxHp: number };
  hpTone: string;
  sessionId: string | null;
  scenarioId: string;
  handlers: GameHeaderHandlers;
}) {
  return (
    <>
        {/* 顶栏：品牌 + 场景 + 角色数值 + 导航 */}
        <header className="flex-shrink-0 bg-white/90 backdrop-blur border-b border-ink-200">
          <div className="h-12 px-4 flex items-center gap-3">
            {/* 左：品牌与剧本标记（窄屏隐藏，避免空容器占用 gap 造成左导轨不齐） */}
            <div className="hidden sm:flex items-center gap-2 shrink-0">
              <span className="w-7 h-7 rounded-xl bg-brand-600 text-white text-2xs font-black hidden sm:flex items-center justify-center shadow-sm" aria-hidden>
                TR
              </span>
              <span className="text-xs font-bold text-ink-800 hidden lg:inline">TRPG 跑团</span>
              {scenarioId && <span className="tag-purple hidden sm:inline-flex" title="当前剧本专属内容">剧本</span>}
            </div>

            {/* 中：场景信息 */}
            <div className="flex-1 min-w-0 flex items-center gap-2 sm:gap-3 text-2xs">
              {sceneInfo.location && sceneInfo.location !== '冒险的起点' && sceneInfo.location !== '未知' && (
                <span className="text-ink-700 font-medium truncate" title={sceneInfo.location}>
                  <span aria-hidden className="hidden sm:inline">📍 </span>{sceneInfo.location}
                </span>
              )}
              <span className="text-ink-500 shrink-0 font-mono">{sceneInfo.time}</span>
              {/* 光照是战斗机制（黑暗里看不见 → 攻守优劣势），放第一行，窄屏也看得见 */}
              {sceneInfo.light && (
                <span className="text-ink-500 shrink-0" title={sceneInfo.light_source || sceneInfo.light}>
                  <span aria-hidden>{lightIcon(sceneInfo.light)} </span>{sceneInfo.light}
                </span>
              )}
            </div>

            {/* 右：角色数值 + 移动端抽屉入口 + 桌面导航 */}
            <div className="flex items-center gap-1.5 shrink-0">
              <HeaderStatus status={status} hpTone={hpTone} sessionId={sessionId} handlers={handlers} />
            </div>
          </div>

          {/* 第二行：导航工具条（窄屏图标化，不横滑藏内容）+ 场景补充信息（宽屏显示） */}
          <div className="px-4 pb-2 flex items-center gap-2">
            <nav
              className="flex items-center gap-0.5 overflow-x-auto no-scrollbar min-w-0 rounded-xl bg-ink-50/80 ring-1 ring-ink-200/70 p-1"
              aria-label="主要功能"
            >
              <HeaderNav handlers={handlers} />
            </nav>
            <div className="hidden xl:flex items-center gap-3 ml-auto pl-3 shrink-0 text-2xs text-ink-500">
              {sceneInfo.weather && <span className="shrink-0" title={sceneInfo.weather}>☁ {sceneInfo.weather}</span>}
              {sceneInfo.light && sceneInfo.light_source && (
                <span className="shrink-0" title={sceneInfo.light_source}>💡 {sceneInfo.light_source}</span>
              )}
              {sceneInfo.npcs_here.length > 0 && (
                <span className="truncate max-w-[20rem]" title={sceneInfo.npcs_here.join('、')}>
                  👥 在场：{sceneInfo.npcs_here.slice(0, 4).join('、')}
                  {sceneInfo.npcs_here.length > 4 ? ` +${sceneInfo.npcs_here.length - 4}` : ''}
                </span>
              )}
            </div>
          </div>
        </header>
    </>
  );
}
