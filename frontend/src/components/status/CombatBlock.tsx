/** 战斗中的敌人列表（从 StatusPanel 拆出；只做展示，数据由父组件传入）。 */
import { motion } from 'framer-motion';

type CombatInfo = {
  active?: boolean;
  enemyName?: string;
  enemyHp?: number;
  enemies?: Array<{ name: string; hp: number; pending_regen?: boolean }>;
} | null;

export default function CombatBlock({ combat }: { combat: CombatInfo }) {
  return (
    <>
        {combat?.active && (
          <motion.div
            initial={{ opacity: 0, scale: 0.96 }}
            animate={{ opacity: 1, scale: 1 }}
            className="rounded-xl bg-red-50 border border-red-200 p-2.5"
          >
            <p className="text-2xs text-red-600 font-bold flex items-center gap-1.5 mb-1">
              <span className="w-1.5 h-1.5 rounded-full bg-red-500 animate-pulse-soft" aria-hidden />
              战斗中
            </p>
            <div className="space-y-1">
              {(combat.enemies && combat.enemies.length > 0
                ? combat.enemies
                : [{ name: combat.enemyName, hp: combat.enemyHp, pending_regen: false }]
              ).map((e) => (
                <div key={e.name} className="flex items-center justify-between gap-2">
                  <span className="text-2xs text-red-700 truncate">{e.name}</span>
                  <span className="text-2xs text-ink-500 font-mono shrink-0">
                    {e.pending_regen ? '再生中 · ' : ''}HP {e.hp}
                  </span>
                </div>
              ))}
            </div>
          </motion.div>
        )}
    </>
  );
}
