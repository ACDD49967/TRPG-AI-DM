/**
 * 行内编辑：点铅笔 → 就地出输入框 → 保存/取消。
 *
 * 内容库（图鉴/地图/法术/存档）此前只有"新增/删除"，改一个字都要删了重建；
 * 后端已经补上 PUT，这里给一个统一的前端入口，避免每个面板各写一套表单。
 */

import { useState, type ReactNode } from 'react';

export interface InlineField {
  key: string;
  label: string;
  value: string;
  type?: 'text' | 'textarea' | 'number';
  placeholder?: string;
}

export default function InlineEdit({ fields, onSave, label = '编辑', saving = false, children }: {
  fields: InlineField[];
  onSave: (values: Record<string, string>) => void | Promise<void>;
  label?: string;
  saving?: boolean;
  children?: ReactNode;
}) {
  const [editing, setEditing] = useState(false);
  const [values, setValues] = useState<Record<string, string>>({});
  const [busy, setBusy] = useState(false);

  const start = () => {
    const initial: Record<string, string> = {};
    for (const field of fields) initial[field.key] = field.value ?? '';
    setValues(initial);
    setEditing(true);
  };

  const stop = (event: { preventDefault: () => void; stopPropagation: () => void }) => {
    // 行内编辑常放在 <details><summary> 里：别让点击连带折叠面板
    event.preventDefault();
    event.stopPropagation();
  };

  const submit = async () => {
    setBusy(true);
    try {
      await onSave(values);
      setEditing(false);
    } finally {
      setBusy(false);
    }
  };

  if (!editing) {
    return (
      <span className="inline-flex items-start gap-1" data-inline-edit="view">
        {children}
        <button type="button" onClick={(e) => { stop(e); start(); }} title={label} aria-label={label}
                className="inline-flex items-center justify-center text-3xs px-2 py-1 min-h-[28px] min-w-[28px]
                           rounded border border-ink-200 text-ink-500 hover:border-ink-300 shrink-0">
          ✏️
        </button>
      </span>
    );
  }

  return (
    <div className="w-full space-y-1.5" data-inline-edit="edit">
      {fields.map((field) => (
        <label key={field.key} className="block">
          <span className="text-3xs text-ink-500">{field.label}</span>
          {field.type === 'textarea' ? (
            <textarea
              value={values[field.key] ?? ''} placeholder={field.placeholder}
              onChange={(e) => setValues((prev) => ({ ...prev, [field.key]: e.target.value }))}
              rows={2}
              className="w-full mt-0.5 text-2xs px-2 py-1 rounded-lg border border-ink-200"
            />
          ) : (
            <input
              type={field.type === 'number' ? 'number' : 'text'}
              value={values[field.key] ?? ''} placeholder={field.placeholder}
              onChange={(e) => setValues((prev) => ({ ...prev, [field.key]: e.target.value }))}
              className="w-full mt-0.5 text-2xs px-2 py-1 rounded-lg border border-ink-200"
            />
          )}
        </label>
      ))}
      <div className="flex items-center gap-1.5">
        <button type="button" disabled={busy || saving} onClick={submit}
                className="text-2xs px-2.5 py-1 rounded-lg border border-brand-300 bg-brand-50 text-brand-700">
          {busy ? '保存中…' : '保存'}
        </button>
        <button type="button" onClick={() => setEditing(false)}
                className="text-2xs px-2.5 py-1 rounded-lg border border-ink-200 text-ink-600">
          取消
        </button>
      </div>
    </div>
  );
}
