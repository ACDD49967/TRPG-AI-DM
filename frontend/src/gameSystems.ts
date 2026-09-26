/** 规则系统前端配置 —— 与后端 backend/engine/game_systems.py 对齐。
 *
 * 按数据 / 掷骰 / 派生拆成三个模块，这里只做再导出，既有 import 全部照旧：
 * - gameSystemsData：标签、选项、COC 与 4e 静态表
 * - gameSystemsRolls：属性与幸运掷骰
 * - gameSystemsDerived：派生值与升级经验
 */
export * from './gameSystemsData';
export * from './gameSystemsRolls';
export * from './gameSystemsDerived';
