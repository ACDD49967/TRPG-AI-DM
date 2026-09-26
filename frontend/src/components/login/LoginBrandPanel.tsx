/** 登录页左侧品牌区：纸感面板，延续角色卡/规则书的视觉语言（从 LoginScreen 拆出）。 */
export default function LoginBrandPanel() {
  return (
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
  );
}
