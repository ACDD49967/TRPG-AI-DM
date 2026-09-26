/**
 * 编辑面板的通用行内控件（数值调整、文本添加、新增 NPC / 通用新增）。
 *
 * 从 EditPanel 拆出：这些小组件各标签页都在用，放在一起便于统一交互。
 */
import { useState } from 'react';
import { ATTITUDES } from './types';

export function DeltaRow({ label, onApply, busy }: {
  label: string; onApply: (value: number) => void; busy: boolean;
}) {
  const [value, setValue] = useState('');
  return (
    <div className="flex items-center gap-2">
      <span className="text-2xs text-ink-500 w-32">{label}</span>
      <input value={value} onChange={(e) => setValue(e.target.value)} placeholder="如 -5 或 2"
             className="text-2xs px-2 py-1 rounded-lg border border-ink-200 w-28" />
      <button disabled={busy || !value.trim()} onClick={() => { onApply(Number(value)); setValue(''); }}
              className="text-2xs px-3 py-1 rounded-lg border border-ink-200">
        应用
      </button>
    </div>
  );
}

export function TextAdder({ placeholder, button, onAdd, busy }: {
  placeholder: string; button: string; onAdd: (value: string) => void; busy: boolean;
}) {
  const [value, setValue] = useState('');
  return (
    <div className="flex items-center gap-2">
      <input value={value} onChange={(e) => setValue(e.target.value)} placeholder={placeholder}
             className="text-2xs px-2 py-1 rounded-lg border border-ink-200 w-48" />
      <button disabled={busy || !value.trim()} onClick={() => { onAdd(value.trim()); setValue(''); }}
              className="text-2xs px-3 py-1 rounded-lg border border-ink-200">
        {button}
      </button>
    </div>
  );
}

export function AddNpcRow({ onAdd, busy }: {
  onAdd: (changes: Record<string, any>) => void; busy: boolean;
}) {
  const [name, setName] = useState('');
  const [role, setRole] = useState('');
  const [attitude, setAttitude] = useState('中立');
  const [hp, setHp] = useState('10');
  return (
    <div className="flex items-center gap-2 flex-wrap border border-dashed border-ink-200 rounded-xl p-2">
      <input value={name} onChange={(e) => setName(e.target.value)} placeholder="NPC 名称"
             className="text-2xs px-2 py-1 rounded-lg border border-ink-200 w-36" />
      <input value={role} onChange={(e) => setRole(e.target.value)} placeholder="身份/职业"
             className="text-2xs px-2 py-1 rounded-lg border border-ink-200 w-32" />
      <select value={attitude} onChange={(e) => setAttitude(e.target.value)}
              className="text-2xs px-2 py-1 rounded-lg border border-ink-200">
        {ATTITUDES.map((a) => <option key={a} value={a}>{a}</option>)}
      </select>
      <input value={hp} onChange={(e) => setHp(e.target.value)} type="number"
             className="text-2xs px-2 py-1 rounded-lg border border-ink-200 w-20" />
      <button disabled={busy || !name.trim()}
              onClick={() => {
                onAdd({ name: name.trim(), role, attitude, hp: Number(hp),
                        max_hp: Number(hp), alive: Number(hp) > 0 });
                setName(''); setRole('');
              }}
              className="text-2xs px-3 py-1 rounded-lg border border-ink-200">
        新增 NPC
      </button>
    </div>
  );
}

export function AddSimpleRow({ fields, onAdd, busy }: {
  fields: Array<[string, string]>; onAdd: (values: Record<string, string>) => void; busy: boolean;
}) {
  const [values, setValues] = useState<Record<string, string>>({});
  const firstKey = fields[0][0];
  return (
    <div className="flex items-center gap-2 flex-wrap border border-dashed border-ink-200 rounded-xl p-2">
      {fields.map(([key, label]) => (
        <input key={key} value={values[key] || ''} placeholder={label}
               onChange={(e) => setValues((prev) => ({ ...prev, [key]: e.target.value }))}
               className="text-2xs px-2 py-1 rounded-lg border border-ink-200 w-36" />
      ))}
      <button disabled={busy || !(values[firstKey] || '').trim()}
              onClick={() => { onAdd(values); setValues({}); }}
              className="text-2xs px-3 py-1 rounded-lg border border-ink-200">
        新增
      </button>
    </div>
  );
}
