/**
 * 登录 / 注册表单：校验、请求、记住账号与自动回填（从 LoginScreen 拆出）。
 *
 * 删号流程在本 hook 里组合（useAccountDeletion），因为它要顺带清掉表单里的明文密码；
 * 组件层因此只消费一个对象，不出现跨组件传 14 个 props 的情况。
 */
import { useEffect, useRef, useState } from 'react';
import type { Dispatch, FormEvent, RefObject, SetStateAction } from 'react';

import { errorText } from './errorText';
import { useAccountDeletion, type AccountDeletion } from './useAccountDeletion';

export type Mode = 'login' | 'register';
export const USERNAME_PATTERN = /^[0-9A-Za-z_\-\u4e00-\u9fff]{2,32}$/;

export interface UseLoginFormOptions {
  onLogin: (username: string, remember: boolean) => void;
}

export interface LoginForm extends AccountDeletion {
  mode: Mode;
  username: string;
  setUsername: Dispatch<SetStateAction<string>>;
  password: string;
  setPassword: Dispatch<SetStateAction<string>>;
  confirm: string;
  setConfirm: Dispatch<SetStateAction<string>>;
  remember: boolean;
  setRemember: Dispatch<SetStateAction<boolean>>;
  showPassword: boolean;
  setShowPassword: Dispatch<SetStateAction<boolean>>;
  busy: boolean;
  error: string;
  notice: string;
  passwordRef: RefObject<HTMLInputElement>;
  switchMode: (next: Mode) => void;
  submit: (event: FormEvent) => Promise<void>;
}

export function useLoginForm({ onLogin }: UseLoginFormOptions): LoginForm {
  const [mode, setMode] = useState<Mode>('login');
  const [username, setUsername] = useState('');
  const [password, setPassword] = useState('');
  const [confirm, setConfirm] = useState('');
  const [remember, setRemember] = useState(true);
  const [showPassword, setShowPassword] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');
  const [notice, setNotice] = useState('');
  const passwordRef = useRef<HTMLInputElement>(null);

  // 删号成功：清掉表单里的明文密码（局部状态留在本 hook，删号逻辑本身在 useAccountDeletion）
  const deletion = useAccountDeletion(() => {
    setPassword('');
    setConfirm('');
  });

  // 自动记住上次登录账号：回填用户名并聚焦密码
  useEffect(() => {
    let last = '';
    try { last = localStorage.getItem('dnd_last_user') || ''; } catch { last = ''; }
    if (last) {
      setUsername(last);
      setTimeout(() => passwordRef.current?.focus(), 80);
    }
  }, []);

  const switchMode = (next: Mode) => {
    setMode(next);
    setError('');
    setNotice('');
    setPassword('');
    setConfirm('');
  };

  const submit = async (event: FormEvent) => {
    event.preventDefault();
    const name = username.trim();
    if (!name) { setError('请输入用户名'); return; }
    if (!USERNAME_PATTERN.test(name)) {
      setError('用户名需为 2-32 位，仅支持中文、字母、数字、下划线、连字符');
      return;
    }
    if (password.length < 6) { setError('密码至少 6 位'); return; }
    if (mode === 'register' && password !== confirm) { setError('两次输入的密码不一致'); return; }

    setBusy(true);
    setError('');
    setNotice('');
    try {
      const url = mode === 'login' ? '/api/auth/login' : '/api/auth/register';
      const response = await fetch(url, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ username: name, password }),
      });
      const data = await response.json().catch(() => ({}));
      if (!response.ok) throw new Error(errorText((data as { detail?: unknown }).detail, '操作失败'));

      if (mode === 'register') {
        const login = await fetch('/api/auth/login', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ username: name, password }),
        });
        const loginData = await login.json().catch(() => ({}));
        if (!login.ok) {
          throw new Error(errorText((loginData as { detail?: unknown }).detail, '注册成功，请登录'));
        }
        setNotice('注册成功，已自动登录');
      }

      try {
        localStorage.setItem('dnd_last_user', name);
        if (remember) localStorage.setItem('dnd_auth_user', name);
        else localStorage.removeItem('dnd_auth_user');
      } catch { /* localStorage 不可用时只影响“记住”能力 */ }
      onLogin(name, remember);
    } catch (err) {
      setError(err instanceof Error ? err.message : '操作失败，请稍后重试');
    } finally {
      setBusy(false);
    }
  };

  // 删号前清掉表单级提示（与拆出前一致）
  const removeAccount = async (name: string) => {
    setError('');
    setNotice('');
    await deletion.removeAccount(name);
  };

  return {
    ...deletion,
    removeAccount,
    mode, username, setUsername, password, setPassword, confirm, setConfirm,
    remember, setRemember, showPassword, setShowPassword, busy, error, notice,
    passwordRef, switchMode, submit,
  };
}
