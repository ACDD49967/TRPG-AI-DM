/** 应用入口 —— 登录门禁 + StartScreen / GameScreen 切换 */

import { useState } from 'react';
import { useGameStore } from './store/gameStore';
import LoginScreen from './components/LoginScreen';
import StartScreen from './components/StartScreen';
import GameScreen from './components/GameScreen';
import ToastContainer from './components/ToastContainer';
import ErrorBoundary from './components/ErrorBoundary';

const AUTH_KEY = 'dnd_auth_user';

function readAuthUser(): string {
  try { return localStorage.getItem(AUTH_KEY) || ''; } catch { return ''; }
}

export default function App() {
  const screen = useGameStore((s) => s.screen);
  const [authUser, setAuthUser] = useState<string>(() => readAuthUser());

  const handleLogin = (username: string) => {
    // 切换账号或首次登录时回到大厅，避免沿用上一个账号的运行时状态。
    try { useGameStore.getState().goToStart(); } catch { /* ignore */ }
    setAuthUser(username);
  };

  const handleLogout = () => {
    try { localStorage.removeItem(AUTH_KEY); } catch { /* ignore */ }
    try { useGameStore.getState().goToStart(); } catch { /* ignore */ }
    setAuthUser('');
  };

  return (
    <ErrorBoundary>
      {!authUser ? (
        <LoginScreen onLogin={handleLogin} />
      ) : screen === 'start' ? (
        <StartScreen authUsername={authUser} onLogout={handleLogout} />
      ) : (
        <GameScreen />
      )}
      <ToastContainer />
    </ErrorBoundary>
  );
}
