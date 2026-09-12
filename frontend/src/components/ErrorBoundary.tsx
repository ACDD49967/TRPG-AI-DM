/**
 * 全局错误边界
 *
 * 页面级崩溃时给出可操作的三条出路：重载 / 复制错误详情 / 清空本地缓存后重载。
 * （前端状态持久化在 localStorage，脏状态导致的崩溃只能靠清缓存恢复。）
 */

import { Component, type ReactNode } from 'react';

interface Props {
  children: ReactNode;
}
interface State {
  error: Error | null;
  copied: boolean;
}

export default class ErrorBoundary extends Component<Props, State> {
  state: State = { error: null, copied: false };

  static getDerivedStateFromError(error: Error): Partial<State> {
    return { error };
  }

  componentDidCatch(error: Error, info: unknown) {
    // 保留控制台线索，方便排查
    console.error('[ErrorBoundary]', error, info);
  }

  private copy = async () => {
    const { error } = this.state;
    if (!error) return;
    try {
      await navigator.clipboard.writeText(`${error.name}: ${error.message}\n\n${error.stack || ''}`);
      this.setState({ copied: true });
      setTimeout(() => this.setState({ copied: false }), 2000);
    } catch {
      /* 剪贴板不可用时忽略 */
    }
  };

  private resetLocalState = () => {
    try {
      localStorage.removeItem('dnd-game-state');
    } catch {}
    location.reload();
  };

  render() {
    if (!this.state.error) return this.props.children;
    const { error, copied } = this.state;

    return (
      <div className="min-h-screen flex items-center justify-center p-4">
        <div className="w-full max-w-lg card p-6 animate-pop-in">
          <div className="flex items-start gap-3 mb-4">
            <span className="shrink-0 w-10 h-10 rounded-2xl bg-red-50 border border-red-200 flex items-center justify-center text-lg" aria-hidden>
              ⚠️
            </span>
            <div>
              <h1 className="text-lg font-bold text-ink-900">前端页面出错了</h1>
              <p className="text-xs text-ink-500 mt-1 leading-relaxed">
                页面没有消失，只是遇到了运行时错误。可以先重载；若反复出现，清空本地进度缓存再试。
              </p>
            </div>
          </div>

          <pre className="bg-ink-50 border border-ink-200 rounded-xl p-3 text-2xs text-ink-600 font-mono whitespace-pre-wrap break-all max-h-40 overflow-y-auto">
            {error.name}: {error.message}
          </pre>

          <div className="flex flex-wrap gap-2 mt-4">
            <button onClick={() => location.reload()} className="btn-primary text-sm px-4 py-2">
              重新加载
            </button>
            <button onClick={this.copy} className="btn-secondary text-sm px-4 py-2">
              {copied ? '已复制 ✓' : '复制错误信息'}
            </button>
            <button
              onClick={this.resetLocalState}
              className="btn-secondary text-sm px-4 py-2 text-red-600 border-red-200 hover:bg-red-50"
              title="清空本地保存的游戏进度与设置后重新加载"
            >
              清空本地缓存并重载
            </button>
          </div>
        </div>
      </div>
    );
  }
}
