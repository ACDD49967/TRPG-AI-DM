/** API 连接设置面板：连接/模型与游玩模式两个 section 的组合。 */
import ConnectionSection from './settings/ConnectionSection';
import PlayModeSection from './settings/PlayModeSection';

export default function ApiSettingsPanel() {
  return (
    <>
      <ConnectionSection />
      <PlayModeSection />
    </>
  );
}
