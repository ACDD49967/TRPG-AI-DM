/**
 * 删除账号：连同该账号下的角色卡、存档、剧本、扩展、媒体与知识库条目一起清空。
 *
 * 从 LoginScreen 拆出：删号只在这里读要确认的密码、发 DELETE、把清理结果写回提示，
 * 清除登录表单里的明文密码由调用方通过 onDeleted 回调处理（职责不跨层）。
 */
import { useState } from 'react';

import { errorText } from './errorText';

export function useAccountDeletion(onDeleted?: () => void) {
  // 变量统一带 delete 前缀：登录表单里也有 password/busy，
  // 两者合并成一个对象返回时若重名，删号区会绑到登录口令上。
  const [deleteOpen, setDeleteOpen] = useState(false);
  const [deletePassword, setDeletePassword] = useState('');
  const [deleteBusy, setDeleteBusy] = useState(false);
  const [deleteMessage, setDeleteMessage] = useState('');

  const toggle = () => {
    setDeleteOpen((value) => !value);
    setDeleteMessage('');
  };

  /** 需要当前密码确认；成功后会清空本地登录痕迹并回调 onDeleted。 */
  const removeAccount = async (username: string) => {
    const name = username.trim();
    if (!name || !deletePassword) return;
    if (!window.confirm(
      `确定删除账号「${name}」？该账号下的角色卡、存档、剧本、扩展、媒体与知识库条目会一并清空，无法恢复。`)) {
      return;
    }
    setDeleteBusy(true);
    setDeleteMessage('');
    try {
      const response = await fetch('/api/auth/user', {
        method: 'DELETE',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ username: name, password: deletePassword }),
      });
      const data = await response.json().catch(() => ({}));
      if (!response.ok) {
        throw new Error(errorText((data as { detail?: unknown }).detail, '删除失败'));
      }
      const cleanup = (data as { cleanup?: { dirs?: string[]; knowledge_docs?: number } }).cleanup || {};
      try {
        localStorage.removeItem('dnd_auth_user');
        localStorage.removeItem('dnd_last_user');
      } catch { /* localStorage 不可用时忽略 */ }
      setDeletePassword('');
      onDeleted?.();
      setDeleteMessage(`账号已删除：清理内容目录 ${cleanup.dirs?.length ?? 0} 个、知识条目 ${cleanup.knowledge_docs ?? 0} 条。`);
    } catch (err) {
      setDeleteMessage(err instanceof Error ? err.message : '删除失败，请稍后重试');
    } finally {
      setDeleteBusy(false);
    }
  };

  return {
    deleteOpen, setDeleteOpen, toggle,
    deletePassword, setDeletePassword,
    deleteBusy, deleteMessage, setDeleteMessage,
    removeAccount,
  };
}

export type AccountDeletion = ReturnType<typeof useAccountDeletion>;
