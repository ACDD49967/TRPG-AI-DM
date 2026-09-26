/** 角色卡顶部：姓名/种族职业等级/护甲等级 + 核心数值 + 被动感知与生命骰。 */
import type { CharacterStatus } from '../../store/gameTypes';
import { mod } from './helpers';

export default function SheetHeader({ status, attrs, prof, speed, onClose, embedded }: {
  status: CharacterStatus;
  attrs: Record<string, number>;
  prof: number;
  speed: string;
  onClose?: () => void;
  embedded: boolean;
}) {
  return (
    <>
      {/* 顶部信息 */}
      <div className="flex items-start justify-between border-b-2 border-amber-900/30 pb-3">
        <div>
          <h3 className="paper-title text-2xl font-black tracking-wide">{status.character_name || '冒险者'}</h3>
          <p className="text-xs text-ink-600 mt-1">
            {status.race || '?'} · {status.char_class || '?'} · Lv.{status.level} · {status.game_system === 'dnd4e' ? 'D&D 4e' : 'D&D 5e'}
          </p>
        </div>
        <div className="flex items-start gap-3">
          <div className="text-right">
            <div className="paper-title text-4xl font-black text-amber-900/80">{status.ac ?? 10}</div>
            <p className="text-[10px] uppercase tracking-widest text-ink-500">护甲等级</p>
          </div>
          {onClose && !embedded && <button onClick={onClose} className="text-xs text-ink-400 hover:text-ink-600">关闭</button>}
        </div>
      </div>

      {/* 核心数值 */}
      <div className="grid grid-cols-4 gap-2 mt-3">
        <div className="bg-amber-50/70 border border-amber-900/20 rounded-lg p-2 text-center">
          <p className="text-[10px] uppercase tracking-widest text-ink-500">生命值</p>
          <p className="paper-title text-xl font-bold">{status.hp}/{status.maxHp}</p>
        </div>
        <div className="bg-amber-50/70 border border-amber-900/20 rounded-lg p-2 text-center">
          <p className="text-[10px] uppercase tracking-widest text-ink-500">先攻</p>
          <p className="paper-title text-xl font-bold">{mod(Number(attrs.dex ?? 10))}</p>
        </div>
        <div className="bg-amber-50/70 border border-amber-900/20 rounded-lg p-2 text-center">
          <p className="text-[10px] uppercase tracking-widest text-ink-500">速度</p>
          <p className="paper-title text-xl font-bold">{speed}</p>
        </div>
        <div className="bg-amber-50/70 border border-amber-900/20 rounded-lg p-2 text-center">
          <p className="text-[10px] uppercase tracking-widest text-ink-500">熟练加值</p>
          <p className="paper-title text-xl font-bold">+{prof}</p>
        </div>
      </div>

      {/* 被动感知 */}
      <div className="mt-2 grid grid-cols-2 gap-2">
        <div className="bg-white/70 border border-amber-900/20 rounded-lg p-2 text-center">
          <p className="text-[10px] uppercase tracking-widest text-ink-500">被动感知</p>
          <p className="paper-title text-lg font-bold">{status.passive_perception ?? (10 + mod(Number(attrs.wis ?? 10)).replace('+',''))}</p>
        </div>
        <div className="bg-white/70 border border-amber-900/20 rounded-lg p-2 text-center">
          <p className="text-[10px] uppercase tracking-widest text-ink-500">生命骰</p>
          <p className="paper-title text-lg font-bold">{status.hit_die || '1d8'}</p>
        </div>
      </div>
    </>
  );
}
