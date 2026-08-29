import { Component, type ReactNode } from 'react';

interface Props {
  children: ReactNode;
}
interface State {
  error: Error | null;
}

export default class ErrorBoundary extends Component<Props, State> {
  state: State = { error: null };

  static getDerivedStateFromError(error: Error): State {
    return { error };
  }

  render() {
    if (this.state.error) {
      return (
        <div style={{
          minHeight: '100vh',
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'center',
          background: '#f8fafc',
          padding: 24,
          fontFamily: 'system-ui, sans-serif',
        }}>
          <div style={{
            background: '#fff',
            border: '1px solid #e2e8f0',
            borderRadius: 16,
            padding: 24,
            maxWidth: 560,
            width: '100%',
            boxShadow: '0 10px 30px rgba(0,0,0,0.08)',
          }}>
            <h1 style={{ fontSize: 18, fontWeight: 700, color: '#b91c1c', marginBottom: 8 }}>前端页面出错了</h1>
            <p style={{ fontSize: 13, color: '#475569', marginBottom: 12 }}>
              页面没有消失，只是遇到了运行时错误。请把下面的信息发给开发者。
            </p>
            <pre style={{
              background: '#f1f5f9',
              borderRadius: 8,
              padding: 12,
              fontSize: 12,
              color: '#334155',
              whiteSpace: 'pre-wrap',
              wordBreak: 'break-all',
              marginBottom: 16,
            }}>{this.state.error.message}</pre>
            <button
              onClick={() => location.reload()}
              style={{
                background: '#4f46e5',
                color: '#fff',
                border: 'none',
                borderRadius: 8,
                padding: '10px 18px',
                fontSize: 14,
                fontWeight: 600,
                cursor: 'pointer',
              }}
            >
              重新加载
            </button>
          </div>
        </div>
      );
    }
    return this.props.children;
  }
}
