/** 弹窗标题栏：图标 + 标题 + 副标题 + 右侧附加操作 + 关闭按钮。 */
import type { ReactNode } from 'react';

export default function ModalHeader({
  titleId, title, subtitle, icon, headExtra, paper, onClose,
}: {
  titleId: string;
  title?: ReactNode;
  subtitle?: ReactNode;
  icon?: ReactNode;
  headExtra?: ReactNode;
  paper: boolean;
  onClose: () => void;
}) {
  return (
    <div className={`flex items-start justify-between gap-3 flex-shrink-0 px-4 sm:px-5 py-3.5 ${paper ? 'border-b border-parch-400/50' : 'border-b border-ink-100'}`}>
      <div className="min-w-0">
        {title && (
          <h3
            id={titleId}
            className={`text-base font-bold text-ink-800 flex items-center gap-2 ${paper ? 'paper-title' : ''}`}
          >
            {icon && <span aria-hidden className="text-lg leading-none">{icon}</span>}
            <span className="truncate">{title}</span>
          </h3>
        )}
        {subtitle && <p className="text-2xs text-ink-400 mt-1 leading-relaxed">{subtitle}</p>}
      </div>
      <div className="flex items-center gap-1.5 flex-shrink-0">
        {headExtra}
        <button onClick={onClose} className="modal-close" aria-label="关闭弹窗" title="关闭（Esc）">
          <svg viewBox="0 0 20 20" fill="none" className="w-4 h-4" aria-hidden>
            <path d="M5 5l10 10M15 5L5 15" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" />
          </svg>
        </button>
      </div>
    </div>
  );
}
