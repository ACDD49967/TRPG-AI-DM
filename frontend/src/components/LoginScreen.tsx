/** 登录 / 注册页 —— 与整体羊皮纸 + 墨色 UI 保持一致。 */
import { useEffect, useRef, useState } from 'react';
import type { FormEvent } from 'react';

interface LoginScreenProps {
  onLogin: (username: string, remember: boolean) => void;
}

type Mode = 'login' | 'register';

function errorText(value: unknown, fallback: string): string {
  if (typeof value === 'string' && value.trim()) return value;
  if (Array.isArray(value)) return '输入格式不正确，请检查用户名和密码';
  return fallback;
}

export default function LoginScreen({ onLogin }: LoginScreenProps) {
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

  const submit = async (e: FormEvent) => {
    e.preventDefault();
    const name = username.trim();
    if (!name) { setError('请输入用户名'); return; }
    if (!/^[0-9A-Za-z_\-\u4e00-\u9fff]{2,32}$/.test(name)) {
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
      const r = await fetch(url, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ username: name, password }),
      });
      const data = await r.json().catch(() => ({}));
      if (!r.ok) throw new Error(errorText((data as { detail?: unknown }).detail, '操作失败'));

      if (mode === 'register') {
        const r2 = await fetch('/api/auth/login', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ username: name, password }),
        });
        const data2 = await r2.json().catch(() => ({}));
        if (!r2.ok) throw new Error(errorText((data2 as { detail?: unknown }).detail, '注册成功，请登录'));
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

  return (
    <div className="min-h-screen flex items-center justify-center p-3 sm:p-6">
      <div className="w-full max-w-4xl card overflow-hidden animate-fade-in grid md:grid-cols-[1.05fr_1fr]">

        {/* 品牌区：纸感面板，延续角色卡/规则书的视觉语言 */}
        <aside className="relative hidden md:flex flex-col justify-between p-8 lg:p-10 paper-card border-0 border-r border-ink-200">
          <div>
            <span className="tag-purple mb-4 inline-flex">
              <span aria-hidden>🎲</span> 本地账号 · 离线可用
            </span>
            <h1 className="font-display text-3xl lg:text-4xl font-black text-ink-900 leading-tight">
              TRPG 跑团
            </h1>
            <p className="mt-3 text-sm text-ink-600 leading-relaxed">
              登录后继续你的冒险。剧本、存档、角色卡、图鉴与知识库按账号隔离，数据只保存在本机。
            </p>
          </div>
          <div className="my-6">
            <div className="paper-rule mb-5" />
            <p className="font-display text-sm text-ink-700 italic leading-relaxed">
              “骰子已经掷下。你的故事，从登录这一刻继续。”
            </p>
          </div>
          <div className="space-y-3 text-xs text-ink-500">
            <p className="flex items-center gap-2">
              <span className="w-1.5 h-1.5 rounded-full bg-brand-500 shrink-0" />
              登录后再显示剧本与存档列表
            </p>
            <p className="flex items-center gap-2">
              <span className="w-1.5 h-1.5 rounded-full bg-brand-500 shrink-0" />
              自动记住上次登录的用户名
            </p>
            <p className="flex items-center gap-2">
              <span className="w-1.5 h-1.5 rounded-full bg-brand-500 shrink-0" />
              同一台电脑可创建多个本地账号
            </p>
          </div>
        </aside>

        {/* 表单区 */}
        <section className="bg-white/98 p-6 sm:p-8 lg:p-10">
          <div className="flex items-start justify-between gap-3 mb-6">
            <div>
              <p className="section-label mb-1">本地账号</p>
              <h2 className="font-display text-2xl font-black text-ink-900">
                {mode === 'login' ? '登录' : '注册新账号'}
              </h2>
              <p className="text-2xs text-ink-400 mt-1">登录后才进入剧本与存档大厅</p>
            </div>
            <span className="tag-gray shrink-0">v0.2.8</span>
          </div>

          {/* 登录 / 注册切换：使用全站统一 seg 分段控件 */}
          <div className="flex gap-2 mb-5">
            <button
              type="button"
              aria-pressed={mode === 'login'}
              onClick={() => switchMode('login')}
              className={`seg flex-1 ${mode === 'login' ? 'seg-active' : ''}`}
            >登录</button>
            <button
              type="button"
              aria-pressed={mode === 'register'}
              onClick={() => switchMode('register')}
              className={`seg flex-1 ${mode === 'register' ? 'seg-active' : ''}`}
            >注册</button>
          </div>

          <form onSubmit={submit} className="space-y-4">
            {mode === 'register' && (
              <p className="text-2xs leading-relaxed text-parch-700 bg-parch-100 border border-parch-300 rounded-xl px-3 py-2">
                如果你之前已有本地存档、剧本或角色卡，请用<strong>原来的用户名</strong>注册；登录后会自动识别同一账号下的数据。
              </p>
            )}

            <div>
              <label className="section-label block mb-1.5">用户名</label>
              <input
                value={username}
                onChange={(e) => setUsername(e.target.value)}
                placeholder="中文 / 字母 / 数字 / _ -"
                autoComplete="username"
                className="input-field w-full"
              />
              <p className="text-2xs text-ink-400 mt-1">2-32 位；将作为存档与剧本的隔离标识</p>
            </div>

            <div>
              <label className="section-label block mb-1.5">密码</label>
              <div className="flex gap-2">
                <input
                  ref={passwordRef}
                  type={showPassword ? 'text' : 'password'}
                  value={password}
                  onChange={(e) => setPassword(e.target.value)}
                  placeholder={mode === 'register' ? '至少 6 位' : '输入密码'}
                  autoComplete={mode === 'login' ? 'current-password' : 'new-password'}
                  className="input-field flex-1"
                />
                <button type="button" onClick={() => setShowPassword(v => !v)} className="btn-secondary text-xs px-3 whitespace-nowrap">
                  {showPassword ? '隐藏' : '显示'}
                </button>
              </div>
            </div>

            {mode === 'register' && (
              <div>
                <label className="section-label block mb-1.5">确认密码</label>
                <input
                  type={showPassword ? 'text' : 'password'}
                  value={confirm}
                  onChange={(e) => setConfirm(e.target.value)}
                  placeholder="再次输入密码"
                  autoComplete="new-password"
                  className="input-field w-full"
                />
              </div>
            )}

            <label className="flex items-center gap-2 text-xs text-ink-600 select-none">
              <input
                type="checkbox"
                checked={remember}
                onChange={(e) => setRemember(e.target.checked)}
                className="accent-brand-600"
              />
              记住账号（下次自动填入用户名）
            </label>

            {error && (
              <p className="text-xs text-red-600 bg-red-50 border border-red-100 rounded-xl px-3 py-2">{error}</p>
            )}
            {notice && (
              <p className="text-xs text-emerald-700 bg-emerald-50 border border-emerald-100 rounded-xl px-3 py-2">{notice}</p>
            )}

            <button type="submit" disabled={busy} className="btn-primary w-full py-2.5 text-sm disabled:opacity-60">
              {busy ? '处理中...' : mode === 'login' ? '登录并继续' : '注册并进入'}
            </button>
          </form>

          <p className="text-2xs text-ink-400 mt-5 leading-relaxed">
            忘记密码无法找回，请删除 <code className="px-1 bg-ink-100 rounded">dndgame.db</code> 中的本地账号记录后重新注册。
          </p>
        </section>
      </div>
    </div>
  );
}
