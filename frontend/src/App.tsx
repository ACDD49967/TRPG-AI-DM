/** 应用入口 —— 根据画面状态切换 StartScreen / GameScreen */

import { useGameStore } from './store/gameStore';
import StartScreen from './components/StartScreen';
import GameScreen from './components/GameScreen';
import ToastContainer from './components/ToastContainer';
import ErrorBoundary from './components/ErrorBoundary';

export default function App() {
  const screen = useGameStore((s) => s.screen);

  return (
    <ErrorBoundary>
      {screen === 'start' ? <StartScreen /> : <GameScreen />}
      <ToastContainer />
    </ErrorBoundary>
  );
}
