/** 属性分配与职业特性：按规则系统选择具体 section。 */
import { useStartWizard } from '../StartWizardContext';
import CocAttributeSection from './attributes/CocAttributeSection';
import CustomAttributeSection from './attributes/CustomAttributeSection';
import DndAttributeSection from './attributes/DndAttributeSection';

export default function AttributeSection() {
  const { gameSystem } = useStartWizard();
  return (
    <>
      {(gameSystem === 'dnd5e' || gameSystem === 'dnd4e') && <DndAttributeSection />}
      {gameSystem === 'coc' && <CocAttributeSection />}
      {gameSystem === 'custom' && <CustomAttributeSection />}
    </>
  );
}
