/**
 * AI 用量卡片：本场累计 token / 调用 / 失败，以及最近一轮的阶段耗时明细。
 *
 * 从 StatusPanel 拆出（面板已 500 行）；阶段名到中文短标签的映射也在这里。
 */
import type { MetricsSnapshot } from '../../store/gameStore';

/** 后端 telemetry 阶段名 → 玩家能看懂的短标签（新阶段名回退为原名）。 */
const PHASE_LABELS: Record<string, string> = {
  opening: '开场白',
  dispatch_retrieval: '检索/分发',
  memory: '记忆装配',
  delegation_context: '委派准备',
  delegation_plan: '子Agent分配',
  delegation_agents: '子Agent执行',
  delegation: '委派（合计）',
  narrative_polish: '剧情补写',
  dm_generation: '主DM叙事',
  post_turn: '回合收尾',
  turn: '回合',
};

function phaseLabel(name: string): string {
  return PHASE_LABELS[name] || name;
}

export function MetricsCard({ metrics }: { metrics: MetricsSnapshot | null }) {
  const lastTurn = metrics?.recent_turns?.[metrics.recent_turns.length - 1];
  if (!metrics) return null;
  return (
          <div className="rounded-xl bg-ink-50 border border-ink-200 p-2.5">
            <p className="text-2xs text-ink-500 font-medium mb-1 flex items-center justify-between">
              <span>AI 用量</span>
              <span className="font-mono text-ink-700">{metrics.totals.total_tokens.toLocaleString()} tokens</span>
            </p>
            <div className="grid grid-cols-2 gap-x-2 gap-y-0.5 text-3xs text-ink-400 font-mono">
              <span>调用 {metrics.totals.model_calls}</span>
              <span>失败 {metrics.totals.failures}</span>
              <span>输入 {metrics.totals.prompt_tokens.toLocaleString()}</span>
              <span>输出 {metrics.totals.completion_tokens.toLocaleString()}</span>
              {(metrics.totals.cache_hit_tokens || 0) > 0 && (
                <span className="col-span-2 text-emerald-600">
                  缓存命中 {metrics.totals.cache_hit_tokens.toLocaleString()}
                </span>
              )}
            </div>
            {lastTurn && (
              <p className="text-3xs text-ink-400 mt-1 font-mono">
                最近一轮 {(lastTurn.duration_ms / 1000).toFixed(1)}s · 调用 {lastTurn.model_calls.length} 次
              </p>
            )}
            {lastTurn && Object.keys(lastTurn.phases_ms || {}).length > 0 && (
              // 各阶段耗时由后端 telemetry 记录；默认折叠，避免平时占地方
              <details className="mt-1">
                <summary className="text-3xs text-ink-500 cursor-pointer select-none">
                  阶段耗时明细
                </summary>
                <div className="mt-0.5 space-y-0.5">
                  {Object.entries(lastTurn.phases_ms)
                    .sort((a, b) => b[1] - a[1])
                    .map(([name, ms]) => (
                      <div key={name} className="flex items-center justify-between text-3xs font-mono text-ink-400">
                        <span>{phaseLabel(name)}</span>
                        <span>{(ms / 1000).toFixed(2)}s</span>
                      </div>
                    ))}
                </div>
              </details>
            )}
            {lastTurn && lastTurn.failures.length > 0 && (
              <p className="text-3xs text-amber-600 mt-0.5 truncate" title={lastTurn.failures.join('\n')}>
                {lastTurn.failures[0]}
              </p>
            )}
          </div>
  );
}
