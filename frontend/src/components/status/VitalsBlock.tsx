/** 生命 / 理智 / 回复力（按规则系统切换显示）（从 StatusPanel 拆出；只做展示，数据由父组件传入）。 */
import { motion } from 'framer-motion';
import type { CharacterStatus } from '../../store/gameStore';

export default function VitalsBlock({ system, status, hpPct, hpTone, sanPct }: {
  system: string;
  status: CharacterStatus;
  hpPct: number;
  hpTone: string;
  sanPct: number;
}) {
  return (
    <>
        {/* 生命 / 理智 / 回复力 */}
        <div className="space-y-2">
          <div>
            <div className="flex justify-between text-2xs mb-1">
              <span className="text-ink-500">生命</span>
              <span className={`font-mono font-semibold ${hpPct < 30 ? 'text-red-600' : 'text-ink-700'}`}>
                {status.hp}/{status.maxHp}
              </span>
            </div>
            <div className="h-2 bg-ink-200/70 rounded-full overflow-hidden">
              <motion.div
                className={`h-full rounded-full bg-gradient-to-r ${hpTone}`}
                initial={false}
                animate={{ width: `${hpPct}%` }}
                transition={{ duration: 0.4, ease: [0.22, 1, 0.36, 1] }}
              />
            </div>
          </div>

          {system === 'coc' && (
            <div>
              <div className="flex justify-between text-2xs mb-1">
                <span className="text-ink-500">理智</span>
                <span className={`font-mono ${sanPct < 30 ? 'text-red-600' : 'text-ink-600'}`}>
                  {status.san}/{status.maxSan}
                </span>
              </div>
              <div className="h-2 bg-ink-200/70 rounded-full overflow-hidden">
                <motion.div
                  className={`h-full rounded-full ${sanPct < 30 ? 'bg-gradient-to-r from-red-800 to-red-500' : 'bg-gradient-to-r from-violet-500 to-violet-400'}`}
                  initial={false}
                  animate={{ width: `${sanPct}%` }}
                  transition={{ duration: 0.4, ease: [0.22, 1, 0.36, 1] }}
                />
              </div>
            </div>
          )}

          {system === 'dnd4e' && (
            <div className="rounded-xl bg-ink-50 border border-ink-200 px-2.5 py-1.5">
              <div className="flex justify-between text-2xs">
                <span className="text-ink-500">回复力</span>
                <span className="font-mono text-ink-700 font-semibold">
                  {status.healing_surges}/{status.max_healing_surges}
                </span>
              </div>
              <p className="text-3xs text-ink-400 mt-0.5">每次恢复 {status.surge_value || 0} HP</p>
            </div>
          )}
        </div>
    </>
  );
}
