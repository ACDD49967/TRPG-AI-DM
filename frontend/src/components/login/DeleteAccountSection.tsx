/** 删除账号入口与确认输入（从 LoginScreen 拆出）；实际请求在 useAccountDeletion。 */
import type { LoginForm as LoginFormState } from './useLoginForm';

export default function DeleteAccountSection({ form }: { form: LoginFormState }) {
  return (
    <div className="mt-5 text-2xs text-ink-400 leading-relaxed">
      <p>忘记密码无法找回；需要的话可以直接删掉这个账号再重新注册。</p>
      <button type="button" onClick={form.toggle}
              className="mt-1 text-2xs text-red-700 underline decoration-dotted">
        {form.deleteOpen ? '收起' : '删除账号…'}
      </button>
      {form.deleteOpen && (
        <div className="mt-2 space-y-1.5">
          <p className="text-red-700">
            会一并清空该账号下的角色卡、存档、剧本、扩展、媒体与知识库条目，无法恢复。
          </p>
          <div className="flex gap-1.5">
            <input type="password" value={form.deletePassword} autoComplete="current-password"
                   onChange={(e) => form.setDeletePassword(e.target.value)}
                   placeholder="输入当前密码确认"
                   className="input-field flex-1 text-xs" />
            <button type="button" disabled={form.deleteBusy || !form.username.trim() || !form.deletePassword}
                    onClick={() => { void form.removeAccount(form.username); }}
                    className="text-2xs px-3 py-1.5 rounded-lg border border-red-200 bg-red-50 text-red-700 disabled:opacity-50 whitespace-nowrap">
              {form.deleteBusy ? '删除中…' : '删除账号'}
            </button>
          </div>
          {form.deleteMessage && <p className="text-2xs text-ink-600">{form.deleteMessage}</p>}
        </div>
      )}
    </div>
  );
}
