/** 将任意值安全地转换为可渲染文本，避免 React 渲染对象导致崩溃。 */
export function textValue(value: unknown): string {
  if (value === null || value === undefined) return '';
  if (Array.isArray(value)) return value.map(textValue).filter(Boolean).join('、');
  if (typeof value === 'object') {
    return Object.entries(value as Record<string, unknown>)
      .map(([k, v]) => {
        const text = textValue(v);
        return text ? `${k}:${text}` : k;
      })
      .filter(Boolean)
      .join('、');
  }
  return String(value);
}
