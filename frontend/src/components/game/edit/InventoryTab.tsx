/** 物品标签页：背包的增删改与装备切换（走 update_state 的 inventory_* 变更）。 */
import { useState } from 'react';
import type { CharacterState, SendState } from './types';

interface InvRow {
  name: string;
  description?: string;
  quantity?: number;
  type?: string;
  equipped?: boolean;
}

/** 兼容两种历史形状：inventory:[...] 与 inventory:{items:[...]}。 */
function readItems(character: CharacterState | null): InvRow[] {
  const raw = (character?.character_info || {}).inventory as unknown;
  const list: unknown[] = Array.isArray(raw)
    ? raw
    : (raw && typeof raw === 'object' && Array.isArray((raw as { items?: unknown[] }).items)
      ? (raw as { items: unknown[] }).items
      : []);
  return list.map((entry) => {
    if (typeof entry === 'string') return { name: entry };
    const obj = (entry || {}) as Record<string, unknown>;
    return {
      name: String(obj.name || '未命名物品'),
      description: obj.description ? String(obj.description) : '',
      quantity: Number(obj.quantity || 1),
      type: obj.type ? String(obj.type) : '',
      equipped: Boolean(obj.equipped),
    };
  });
}

export default function InventoryTab({ character, busy, onSend }: {
  character: CharacterState | null; busy: boolean; onSend: SendState;
}) {
  const items = readItems(character);
  const [name, setName] = useState('');
  const [desc, setDesc] = useState('');
  const [qty, setQty] = useState(1);

  const add = () => {
    const trimmed = name.trim();
    if (!trimmed) return;
    onSend({ inventory_add: { name: trimmed, description: desc.trim(), quantity: qty } });
    setName(''); setDesc(''); setQty(1);
  };

  return (
    <div className="space-y-2">
      <div className="border border-ink-200 rounded-xl p-2 space-y-1.5">
        <p className="text-2xs text-ink-500">添加物品</p>
        <div className="flex gap-1.5 flex-wrap">
          <input value={name} onChange={(e) => setName(e.target.value)}
                 placeholder="物品名（如 治疗药水）"
                 className="text-2xs px-2 py-1 rounded-lg border border-ink-200 w-40" />
          <input value={desc} onChange={(e) => setDesc(e.target.value)} placeholder="描述（可选）"
                 className="text-2xs px-2 py-1 rounded-lg border border-ink-200 flex-1 min-w-[8rem]" />
          <input type="number" min={1} value={qty}
                 onChange={(e) => setQty(Math.max(1, Number(e.target.value) || 1))}
                 className="text-2xs px-2 py-1 rounded-lg border border-ink-200 w-16" />
          <button disabled={busy || !name.trim()} onClick={add}
                  className="text-2xs px-3 py-1 rounded-lg bg-brand-50 border border-brand-200 text-brand-700 disabled:opacity-50">
            添加
          </button>
        </div>
      </div>

      {items.map((item) => (
        <div key={item.name} data-inventory-item={item.name}
             className="border border-ink-200 rounded-xl p-2 flex items-center gap-2 flex-wrap">
          <span className="text-xs text-ink-800 w-32 truncate">
            {item.name}{item.quantity && item.quantity > 1 ? ` ×${item.quantity}` : ''}
          </span>
          <input defaultValue={item.description || ''} placeholder="描述"
                 onBlur={(e) => onSend({ inventory_update: { name: item.name, description: e.target.value } })}
                 className="text-2xs px-2 py-1 rounded-lg border border-ink-200 flex-1 min-w-[8rem]" />
          <input type="number" min={1} defaultValue={item.quantity ?? 1}
                 onBlur={(e) => onSend({
                   inventory_update: { name: item.name, quantity: Math.max(1, Number(e.target.value) || 1) },
                 })}
                 className="text-2xs px-2 py-1 rounded-lg border border-ink-200 w-16" />
          <button disabled={busy}
                  onClick={() => onSend({
                    [item.equipped ? 'inventory_unequip' : 'inventory_equip']: item.name,
                  })}
                  className="text-2xs px-2 py-1 rounded-lg border border-ink-200">
            {item.equipped ? '卸下' : '装备'}
          </button>
          <button disabled={busy} onClick={() => onSend({ inventory_remove: item.name })}
                  className="text-2xs text-red-700 px-2 py-1">删除</button>
        </div>
      ))}
      {items.length === 0 && <p className="text-2xs text-ink-400">背包为空，可在上方添加物品。</p>}
    </div>
  );
}
