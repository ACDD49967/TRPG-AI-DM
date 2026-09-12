/** 统一进度条：知识库切分、SRD 机翻、媒体机翻等长时间任务共用 */

interface ProgressBarProps {
  /** 已完成数量 */
  value: number;
  /** 总数；为 0 时显示为不确定进度 */
  max: number;
  /** 左侧说明文字 */
  label?: string;
  /** 右侧文字，默认显示 value/max */
  trailing?: string;
  /** 颜色语义 */
  tone?: 'brand' | 'amber' | 'emerald';
  className?: string;
}

const TONE_CLASS = {
  brand: 'bg-brand-500',
  amber: 'bg-amber-500',
  emerald: 'bg-emerald-500',
};

export default function ProgressBar({
  value,
  max,
  label,
  trailing,
  tone = 'brand',
  className = '',
}: ProgressBarProps) {
  const pct = max > 0 ? Math.min(100, Math.max(0, Math.round((value / max) * 100))) : 0;
  return (
    <div className={className}>
      {(label || trailing !== undefined) && (
        <div className="flex items-center justify-between gap-2 text-2xs text-ink-500 mb-1.5">
          <span className="truncate">{label}</span>
          <span className="font-mono tabular-nums shrink-0">{trailing ?? `${value}/${max}`}</span>
        </div>
      )}
      <div className="progress-track" role="progressbar" aria-valuemin={0} aria-valuemax={max} aria-valuenow={value}>
        <div
          className={`progress-fill ${TONE_CLASS[tone]}`}
          style={{ width: `${max > 0 ? pct : 35}%` }}
        />
      </div>
    </div>
  );
}
