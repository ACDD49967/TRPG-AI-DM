/**
 * 物品详情弹窗：装备态标签、数量、描述与「装备/卸下」操作。
 *
 * 从 StatusPanel 拆出：弹窗与面板的列表渲染是两件事，且弹窗只依赖物品本身与两个回调。
 */
import Modal from '../ui/Modal';
import { isEquipped, itemDesc, itemName, type InvItem } from './inventory';

export function ItemDetailModal({ item, onClose, onToggleEquip }: {
  item: InvItem | null;
  onClose: () => void;
  onToggleEquip: (it: InvItem) => void;
}) {
  return (
      <Modal
        open={!!item}
        onClose={() => onClose()}
        size="sm"
        icon="🎒"
        title={item ? itemName(item) : ''}
        footer={
          <>
            <button onClick={() => onClose()} className="btn-secondary text-xs px-3 py-1.5">
              关闭
            </button>
            <button
              onClick={() => item && onToggleEquip(item)}
              className={item && isEquipped(item) ? 'btn-secondary text-xs px-3 py-1.5' : 'btn-primary text-xs px-3 py-1.5'}
            >
              {item && isEquipped(item) ? '卸下装备' : '装备此物品'}
            </button>
          </>
        }
      >
        {item && (
          <div className="space-y-2">
            <div className="flex flex-wrap gap-1.5">
              {isEquipped(item) && <span className="tag-purple">已装备</span>}
              {typeof item === 'object' && item.type && <span className="tag-gray">{item.type}</span>}
              {typeof item === 'object' && item.quantity ? (
                <span className="tag-gray">数量 {item.quantity}</span>
              ) : null}
            </div>
            <p className="text-sm text-ink-600 leading-relaxed">{itemDesc(item)}</p>
          </div>
        )}
      </Modal>
  );
}
