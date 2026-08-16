/** 应用入口 —— 根据画面状态切换 StartScreen / GameScreen */

import { useGameStore } from './store/gameStore';
import StartScreen from './components/StartScreen';
import GameScreen from './components/GameScreen';

export default function App() {
  const screen = useGameStore((s) => s.screen);

  if (screen === 'start') {
    return <StartScreen />;
  }

  return <GameScreen />;
}
