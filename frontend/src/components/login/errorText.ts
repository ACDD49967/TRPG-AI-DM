/** 把后端返回的 detail 归一成一句能给玩家看的中文错误（登录/注册/删号共用）。 */
export function errorText(value: unknown, fallback: string): string {
  if (typeof value === 'string' && value.trim()) return value;
  if (Array.isArray(value)) return '输入格式不正确，请检查用户名和密码';
  return fallback;
}
