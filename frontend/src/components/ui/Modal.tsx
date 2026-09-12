/**
 * 统一弹窗原语
 *
 * 为什么需要它：
 * 早期各页面各自手写 `fixed inset-0 bg-black/40`，导致
 *   1) Esc 关不掉、点遮罩语义不一致；2) 背景还能滚动（移动端尤其明显）；
 *   3) 没有 role="dialog"，屏幕阅读器与键盘 Tab 会跑到弹窗外的按钮上。
 * 这里统一收敛：Esc 关闭 / 遮罩点击 / 滚动锁 / 焦点归还 / 进入动画 / 三种停靠位置。
 */

import { useEffect, useId, useRef, type ReactNode } from 'react';
import { createPortal } from 'react-dom';

export type ModalPlacement = 'center' | 'right' | 'bottom';

/** 多弹窗叠加时，只有最后一个卸载才恢复 body 滚动 */
let scrollLockCount = 0;
function lockScroll() {
  scrollLockCount += 1;
  if (scrollLockCount === 1) {
    document.body.style.overflow = 'hidden';
  }
}
function unlockScroll() {
  scrollLockCount = Math.max(0, scrollLockCount - 1);
  if (scrollLockCount === 0) {
    document.body.style.overflow = '';
  }
}

const SIZE_CLASS: Record<string, string> = {
  sm: 'max-w-sm',
  md: 'max-w-lg',
  lg: 'max-w-2xl',
  xl: 'max-w-4xl',
  '2xl': 'max-w-5xl',
  '3xl': 'max-w-[min(1400px,96vw)]',
};

export interface ModalProps {
  open: boolean;
  onClose: () => void;
  /** 标题与副标题 */
  title?: ReactNode;
  subtitle?: ReactNode;
  /** 标题左侧的 emoji / 图标 */
  icon?: ReactNode;
  /** 标题右侧的额外操作（筛选、翻译、切换等） */
  headExtra?: ReactNode;
  /** 底部固定操作区 */
  footer?: ReactNode;
  children?: ReactNode;
  /** 内容区宽度档位，默认 lg */
  size?: keyof typeof SIZE_CLASS;
  /** 停靠位置：居中弹窗 / 右侧抽屉 / 底部抽屉（移动端） */
  placement?: ModalPlacement;
  /** 纸感皮肤（角色卡、图鉴、规则书） */
  paper?: boolean;
  /** 内容区附加类名（例如自建表单的纵向间距） */
  bodyClassName?: string;
  /** 是否允许点击遮罩关闭，默认允许 */
  closeOnBackdrop?: boolean;
}

export default function Modal({
  open,
  onClose,
  title,
  subtitle,
  icon,
  headExtra,
  footer,
  children,
  size = 'lg',
  placement = 'center',
  paper = false,
  bodyClassName = '',
  closeOnBackdrop = true,
}: ModalProps) {
  const cardRef = useRef<HTMLDivElement>(null);
  const restoreFocusRef = useRef<HTMLElement | null>(null);
  const titleId = useId();

  // 记录打开前的焦点元素，关闭后归还，避免键盘用户丢失位置
  useEffect(() => {
    if (!open) return;
    restoreFocusRef.current = document.activeElement as HTMLElement | null;
    return () => {
      restoreFocusRef.current?.focus?.();
    };
  }, [open]);

  // Esc 关闭 + body 滚动锁
  useEffect(() => {
    if (!open) return;
    const onKeyDown = (e: KeyboardEvent) => {
      if (e.key === 'Escape') {
        e.stopPropagation();
        onClose();
      }
    };
    window.addEventListener('keydown', onKeyDown, true);
    lockScroll();
    return () => {
      window.removeEventListener('keydown', onKeyDown, true);
      unlockScroll();
    };
  }, [open, onClose]);

  // 打开后把焦点移进弹窗，保证 Tab 从弹窗内部开始
  useEffect(() => {
    if (!open) return;
    const t = window.setTimeout(() => cardRef.current?.focus(), 0);
    return () => window.clearTimeout(t);
  }, [open]);

  if (!open) return null;

  const placementClass =
    placement === 'right'
      ? 'items-stretch justify-end p-0'
      : placement === 'bottom'
        ? 'items-end justify-center p-0'
        : 'items-center justify-center p-3 sm:p-4';

  const cardClass =
    placement === 'right'
      ? 'w-[min(90vw,380px)] h-full max-h-none rounded-none rounded-l-2xl animate-slide-in-right'
      : placement === 'bottom'
        ? 'max-w-none w-full max-h-[88vh] rounded-b-none animate-slide-up'
        : `${SIZE_CLASS[size] || SIZE_CLASS.lg} w-full max-h-[90vh] animate-pop-in`;

  // 抽屉形态不需要内边距，宽度由 cardClass 决定
  const backdropClass = placement === 'center' ? '' : 'p-0';

  return createPortal(
    <div
      className={`fixed inset-0 z-[80] flex bg-ink-900/45 backdrop-blur-[3px] animate-fade-in ${placementClass} ${backdropClass}`}
      onMouseDown={(e) => {
        if (closeOnBackdrop && e.target === e.currentTarget) onClose();
      }}
      role="presentation"
    >
      <div
        ref={cardRef}
        tabIndex={-1}
        role="dialog"
        aria-modal="true"
        aria-labelledby={title ? titleId : undefined}
        className={`${paper ? 'paper-card' : 'bg-white border border-ink-200'} shadow-float flex flex-col overflow-hidden ${cardClass}`}
      >
        {(title || headExtra) && (
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
        )}

        <div className={`flex-1 overflow-y-auto px-4 sm:px-5 py-4 ${bodyClassName}`}>{children}</div>

        {footer && (
          <div className={`flex-shrink-0 px-4 sm:px-5 py-3 border-t flex items-center justify-end gap-2 ${paper ? 'border-parch-400/50 bg-parch-100/60' : 'border-ink-100 bg-ink-50/60'}`}>
            {footer}
          </div>
        )}
      </div>
    </div>,
    document.body,
  );
}
