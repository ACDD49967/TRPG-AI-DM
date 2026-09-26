/** 弹窗原语的纯计算部分：滚动锁计数、尺寸档位、停靠位置 → 类名。
 *
 * 从 `Modal` 拆出（无 React 依赖，改样式不改组件逻辑）。
 */
export type ModalPlacement = 'center' | 'right' | 'bottom';

/** 多弹窗叠加时，只有最后一个卸载才恢复 body 滚动 */
let scrollLockCount = 0;

export function lockScroll() {
  scrollLockCount += 1;
  if (scrollLockCount === 1) {
    document.body.style.overflow = 'hidden';
  }
}

export function unlockScroll() {
  scrollLockCount = Math.max(0, scrollLockCount - 1);
  if (scrollLockCount === 0) {
    document.body.style.overflow = '';
  }
}

export const SIZE_CLASS: Record<string, string> = {
  sm: 'max-w-sm',
  md: 'max-w-lg',
  lg: 'max-w-2xl',
  xl: 'max-w-4xl',
  '2xl': 'max-w-5xl',
  '3xl': 'max-w-[min(1400px,96vw)]',
};

/** 遮罩容器（placementClass）、卡片（cardClass）与抽屉态内边距（backdropClass）。 */
export function placementClasses(placement: ModalPlacement, size: string) {
  const container =
    placement === 'right'
      ? 'items-stretch justify-end p-0'
      : placement === 'bottom'
        ? 'items-end justify-center p-0'
        : 'items-center justify-center p-3 sm:p-4';

  const card =
    placement === 'right'
      ? 'w-[min(90vw,380px)] h-full max-h-none rounded-none rounded-l-2xl animate-slide-in-right'
      : placement === 'bottom'
        ? 'max-w-none w-full max-h-[88vh] rounded-b-none animate-slide-up'
        : `${SIZE_CLASS[size] || SIZE_CLASS.lg} w-full max-h-[90vh] animate-pop-in`;

  // 抽屉形态不需要内边距，宽度由 cardClass 决定
  const backdrop = placement === 'center' ? '' : 'p-0';
  return { container, card, backdrop };
}
