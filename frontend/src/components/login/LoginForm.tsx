/** 登录 / 注册表单区：切换、输入、校验反馈与提交（从 LoginScreen 拆出）。 */
import type { LoginForm as LoginFormState } from './useLoginForm';

export default function LoginForm({ form }: { form: LoginFormState }) {
  const { mode, switchMode } = form;
  return (
    <>
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

      <form onSubmit={form.submit} className="space-y-4">
        {mode === 'register' && (
          <p className="text-2xs leading-relaxed text-parch-700 bg-parch-100 border border-parch-300 rounded-xl px-3 py-2">
            如果你之前已有本地存档、剧本或角色卡，请用<strong>原来的用户名</strong>注册；登录后会自动识别同一账号下的数据。
          </p>
        )}

        <div>
          <label className="section-label block mb-1.5">用户名</label>
          <input
            value={form.username}
            onChange={(e) => form.setUsername(e.target.value)}
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
              ref={form.passwordRef}
              type={form.showPassword ? 'text' : 'password'}
              value={form.password}
              onChange={(e) => form.setPassword(e.target.value)}
              placeholder={mode === 'register' ? '至少 6 位' : '输入密码'}
              autoComplete={mode === 'login' ? 'current-password' : 'new-password'}
              className="input-field flex-1"
            />
            <button type="button" onClick={() => form.setShowPassword((v) => !v)}
                    className="btn-secondary text-xs px-3 whitespace-nowrap">
              {form.showPassword ? '隐藏' : '显示'}
            </button>
          </div>
        </div>

        {mode === 'register' && (
          <div>
            <label className="section-label block mb-1.5">确认密码</label>
            <input
              type={form.showPassword ? 'text' : 'password'}
              value={form.confirm}
              onChange={(e) => form.setConfirm(e.target.value)}
              placeholder="再次输入密码"
              autoComplete="new-password"
              className="input-field w-full"
            />
          </div>
        )}

        <label className="flex items-center gap-2 text-xs text-ink-600 select-none">
          <input
            type="checkbox"
            checked={form.remember}
            onChange={(e) => form.setRemember(e.target.checked)}
            className="accent-brand-600"
          />
          记住账号（下次自动填入用户名）
        </label>

        {form.error && (
          <p className="text-xs text-red-600 bg-red-50 border border-red-100 rounded-xl px-3 py-2">{form.error}</p>
        )}
        {form.notice && (
          <p className="text-xs text-emerald-700 bg-emerald-50 border border-emerald-100 rounded-xl px-3 py-2">{form.notice}</p>
        )}

        <button type="submit" disabled={form.busy} className="btn-primary w-full py-2.5 text-sm disabled:opacity-60">
          {form.busy ? '处理中...' : mode === 'login' ? '登录并继续' : '注册并进入'}
        </button>
      </form>
    </>
  );
}
