/** 统一空状态：图鉴 / 地图 / 法术 / 背包 / 图谱共用同一套视觉 */

import type { ReactNode } from 'react';

interface EmptyStateProps {
  /** 顶部 emoji 或简单图形 */
  icon?: ReactNode;
  title: string;
  /** 补充说明：怎么才能有内容 / 可以尝试什么 */
  hint?: ReactNode;
  /** 可选操作按钮 */
  action?: ReactNode;
  className?: string;
}

export default function EmptyState({ icon, title, hint, action, className = '' }: EmptyStateProps) {
  return (
    <div className={`empty-state ${className}`}>
      {icon && <div className="empty-state-icon" aria-hidden>{icon}</div>}
      <p className="text-xs font-medium text-ink-500">{title}</p>
      {hint && <p className="text-2xs text-ink-400 leading-relaxed max-w-md mx-auto">{hint}</p>}
      {action && <div className="pt-2">{action}</div>}
    </div>
  );
}
