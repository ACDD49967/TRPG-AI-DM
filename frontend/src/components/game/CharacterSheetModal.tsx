/** 角色卡弹窗：只保留弹窗外壳与标题，正文按系统选择。 */
import Modal from '../ui/Modal';
import CharacterSheetBody from './CharacterSheetBody';

export interface CharacterSheetModalProps {
  [key: string]: any;
}

export default function CharacterSheetModal(props: CharacterSheetModalProps) {
  const {
    invName,
    isDndSheet,
    setShowCharSheet,
    showCharSheet,
    status,
  } = props;

  return (
    <Modal
      open={showCharSheet}
      onClose={() => setShowCharSheet(false)}
      paper
      size="xl"
      icon="🧙"
      title="角色卡"
      subtitle={`${status.character_name || '冒险者'} · ${status.race || '?'} ${status.char_class || '?'} · ${status.game_system || 'dnd5e'}`}
    >
      <CharacterSheetBody status={status} isDndSheet={isDndSheet} invName={invName} />
    </Modal>
  );
}
