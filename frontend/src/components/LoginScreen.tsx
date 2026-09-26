/** 登录 / 注册页 —— 与整体羊皮纸 + 墨色 UI 保持一致。
 *
 * 状态与请求 → `login/useLoginForm`（内部再组合 `useAccountDeletion`）；
 * 品牌区 / 表单区 / 删号区各在 `login/` 下，这里只留布局与分区标题。
 */
import DeleteAccountSection from './login/DeleteAccountSection';
import LoginBrandPanel from './login/LoginBrandPanel';
import LoginForm from './login/LoginForm';
import { useLoginForm } from './login/useLoginForm';

interface LoginScreenProps {
  onLogin: (username: string, remember: boolean) => void;
}

export default function LoginScreen({ onLogin }: LoginScreenProps) {
  const form = useLoginForm({ onLogin });

  return (
    <div className="min-h-screen flex items-center justify-center p-3 sm:p-6">
      <div className="w-full max-w-4xl card overflow-hidden animate-fade-in grid md:grid-cols-[1.05fr_1fr]">

        {/* 品牌区：纸感面板，延续角色卡/规则书的视觉语言 */}
        <LoginBrandPanel />

        {/* 表单区 */}
        <section className="bg-white/98 p-6 sm:p-8 lg:p-10">
          <div className="flex items-start justify-between gap-3 mb-6">
            <div>
              <p className="section-label mb-1">本地账号</p>
              <h2 className="font-display text-2xl font-black text-ink-900">
                {form.mode === 'login' ? '登录' : '注册新账号'}
              </h2>
              <p className="text-2xs text-ink-400 mt-1">登录后才进入剧本与存档大厅</p>
            </div>
            <span className="tag-gray shrink-0">v{__APP_VERSION__}</span>
          </div>

          <LoginForm form={form} />
          <DeleteAccountSection form={form} />
        </section>
      </div>
    </div>
  );
}
