// id 空间：同一个 id 在几张表里指的是同一个东西。
//
// `structure.id_relation` 说「本表的记录下标就是那张表的 id」。于是：
//
//   忍术名表 #37   ←→  忍术记录表 #37      （一个是名字，一个是这条忍术自己的参数）
//   技能名表 #12   ←→  角色特性表 #12      （一个是名字，一个是这个技能自己的参数）
//   人物名表 #5    ←→  角色定义表 #5       ←→  逐角色成长表 #5
//
// 以前界面上只认「指向名字表」这一条路，所以作者从角色的技能槽点「跳过去」
// 只能落到一张**只有名字**的表上 —— 技能本身的参数（效果类型、基础值、
// 每级成长）在另一张表里，却没有任何入口指过去。
//
// 这个模块没有依赖，fields.js 与 xref.js 都要用它，所以单独放。

/**
 * The tables that share an id space with this one.
 *
 * @param {ContentPack} pack
 * @param {string} tableId
 * @returns {string[]} 表 id 列表（含自己）
 */
export function idSpace(pack, tableId) {
  const members = new Set([tableId]);
  let grew = true;
  while (grew) {
    grew = false;
    for (const structure of pack.structures || []) {
      const relation = structure.id_relation;
      if (!relation || !relation.table) continue;
      if (members.has(structure.id) && !members.has(relation.table)) {
        members.add(relation.table);
        grew = true;
      } else if (members.has(relation.table) && !members.has(structure.id)) {
        members.add(structure.id);
        grew = true;
      }
    }
  }
  return [...members];
}

/**
 * The *other* tables in the same id space.
 *
 * @param {ContentPack} pack
 * @param {string} tableId
 * @returns {string[]} 表 id 列表（不含自己）
 */
export function idSpaceOthers(pack, tableId) {
  return idSpace(pack, tableId).filter((id) => id !== tableId);
}

/**
 * The table descriptor for a table id (structure or text table).
 */
export function tableOf(pack, tableId) {
  return pack.structure(tableId) || pack.textTable(tableId) || null;
}
