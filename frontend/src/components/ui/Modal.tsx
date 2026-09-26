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

import ModalHeader from './ModalHeader';
import { SIZE_CLASS, lockScroll, placementClasses, unlockScroll } from './modalChrome';
import type { ModalPlacement } from './modalChrome';

export type { ModalPlacement } from './modalChrome';

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

  const { container: placementClass, card: cardClass, backdrop: backdropClass } =
    placementClasses(placement, size);

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
          <ModalHeader
            titleId={titleId} title={title} subtitle={subtitle} icon={icon}
            headExtra={headExtra} paper={paper} onClose={onClose}
          />
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
