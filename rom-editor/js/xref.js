// Reverse references: "who points at this record?"
//
// The pack knows the forward direction (a field is an id into another table,
// a pointer into a data block, a base index into a run of rows), so the
// backward direction can be computed by scanning the pack.  This is what lets
// the editor answer 「改这个忍术会动到谁」「这个奖励是从哪几关来的」.
//
// The scan is done once per pack and cached: 116 tables / 6,752 records is
// still a few milliseconds, but the editor asks this question for every
// record the author opens.

import { idRelationName } from './fields.js';
import { indexKey } from './indexkey.js';

const ROM_BASE = 0x08000000;

/**
 * The records that point at a given record.
 *
 * @param {ContentPack} pack
 * @param {{kind: string, id: string, recordId: number}} target
 * @returns {Array<{structure: object, field: object, record: object, label: string}>}
 */
export function backReferences(pack, target) {
  const out = [];
  if (!target || target.recordId === null || target.recordId === undefined) return out;

  // 引用者往往指向的是**名字表**（忍术 id 落在忍术名表的空间里），
  // 而目标可能是同号空间的另一张表（忍术记录表 ↔ 忍术名表）。
  // 这种情况下要把查询转到名字表上去做。
  const structure = pack.structure(target.id);
  if (structure && structure.id_relation && structure.id_relation.kind === 'text') {
    return backReferences(pack, {
      kind: 'text', id: structure.id_relation.table, recordId: target.recordId,
    });
  }

  for (const structure of pack.structures || []) {
    for (const field of structure.fields || []) {
      const relation = field.relation;
      if (!relation || relation.kind === 'by_category') continue;
      if (relation.table !== target.id) continue;
      for (const record of structure.records || []) {
        const value = record.values ? record.values[field.key] : undefined;
        if (value !== target.recordId) continue;
        out.push({
          structure,
          field,
          record,
          label: referenceLabel(pack, structure, record, field),
        });
      }
    }
  }
  return out;
}

/**
 * The same, for a *text* table: which structures point at this text's bytes?
 */
export function backReferencesToText(pack, tableId, recordId) {
  return backReferences(pack, { kind: 'text', id: tableId, recordId });
}

/** "漩涡鸣人 · 忍术槽 4" —— enough to know which slot points here. */
function referenceLabel(pack, structure, record, field) {
  const name = idRelationName(pack, structure, record);
  const slot = field.array ? `${field.array}${field.index}` : field.key;
  return name ? `${name} · ${slot}` : `${structure.label} · ${slot}`;
}

// ---------------------------------------------------------------------------
// The full source index
// ---------------------------------------------------------------------------

/**
 * The tables that share an id space with this one.
 *
 * `structure.id_relation` says 「本表的记录下标就是那张表的 id」。
 * 于是同一个 id 在两张表里指的是同一个东西：
 * 指向**忍术名表** #37 的字段，也指向**忍术记录表** #37。
 *
 * 这个别名关系把「谁引用了我」从 6 张表扩展到全部 id 空间，
 * 而不必在每个字段上重复声明。
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

const indexCache = new WeakMap();

/**
 * Every record's sources, indexed.
 *
 * 三条来源路径：
 *  1. **字段声明的关系**（`field.relation`）：下标、绝对地址、连续段基址；
 *  2. **指针字段**：值恰好等于某条记录的 ROM 起点 ⇒ 它指向那条记录
 *     （音效描述符 → 81 张乐曲描述符表就是这样连起来的）；
 *  3. **文本字节**：共用同一段字的其他条目、归属别处的条目。
 *
 * @param {ContentPack} pack
 * @returns {Map<string, Array<object>>} 键是 `表id#记录id`
 */
export function sourceIndex(pack) {
  if (!pack || typeof pack !== 'object') return new Map();
  const cached = indexCache.get(pack);
  if (cached) return cached;
  const index = buildSourceIndex(pack);
  indexCache.set(pack, index);
  return index;
}

/** Drop the cached index (the pack changed). */
export function clearSourceIndex(pack) {
  if (pack && typeof pack === 'object') indexCache.delete(pack);
}

function targetKey(tableId, recordId) {
  return `${tableId}#${recordId}`;
}

function buildSourceIndex(pack) {
  const index = new Map();
  const add = (key, ref) => {
    const list = index.get(key);
    if (list) list.push(ref);
    else index.set(key, [ref]);
  };

  // --- 记录起点 → 记录（指针反查用） -------------------------------------
  // 指针存的是 **ROM 地址**，而记录里的 rom_offset 是**文件偏移**，
  // 比的时候要加上 ROM 基址 —— 否则一条都对不上。
  const byOffset = new Map();
  for (const structure of pack.structures || []) {
    for (const record of structure.records || []) {
      const key = (record.rom_offset + ROM_BASE) >>> 0;
      const list = byOffset.get(key);
      if (list) list.push({ structure, record });
      else byOffset.set(key, [{ structure, record }]);
    }
  }

  // --- 1. 声明了关系���字段 ------------------------------------------------
  for (const structure of pack.structures || []) {
    for (const field of structure.fields || []) {
      const relation = field.relation;
      if (!relation || relation.kind === 'by_category') continue;

      if (relation.kind === 'row_range') {
        // 值是一段连续行的**基址**：每一行都算被引用。
        const count = relation.count || 1;
        const tables = relation.tables || (relation.table ? [relation.table] : []);
        for (const record of structure.records || []) {
          const base = (record.values || {})[field.key];
          if (typeof base !== 'number') continue;
          for (const tableId of tables) {
            for (const alias of idSpace(pack, tableId)) {
              for (let i = 0; i < count; i++) {
                add(targetKey(alias, base + i), {
                  kind: 'field',
                  structure,
                  field,
                  record,
                  tableId: alias,
                  label: sourceLabel(pack, structure, record, field),
                });
              }
            }
          }
        }
        continue;
      }

      const tableId = relation.table;
      if (!tableId) continue;
      const aliases = idSpace(pack, tableId);
      for (const record of structure.records || []) {
        const value = (record.values || {})[field.key];
        if (typeof value !== 'number') continue;
        if (relation.kind === 'text' && value >= ROM_BASE) {
          // 绝对地址：按文本的 ROM 位置找那条记录。
          const offset = value - ROM_BASE;
          for (const table of pack.texts || []) {
            if (table.id !== tableId && !aliases.includes(table.id)) continue;
            for (const textRecord of table.records || []) {
              if (textRecord.text_offset !== offset) continue;
              add(targetKey(table.id, textRecord.id), {
                kind: 'field',
                structure,
                field,
                record,
                tableId: table.id,
                label: sourceLabel(pack, structure, record, field),
              });
            }
          }
          continue;
        }
        for (const alias of aliases) {
          add(targetKey(alias, value), {
            kind: 'field',
            structure,
            field,
            record,
            tableId: alias,
            label: sourceLabel(pack, structure, record, field),
          });
        }
      }
    }
  }

  // --- 2. 指针字段：值 = 某条记录的 ROM 起点 ------------------------------
  for (const structure of pack.structures || []) {
    for (const field of structure.fields || []) {
      if (field.type !== 'ptr') continue;
      for (const record of structure.records || []) {
        const value = (record.values || {})[field.key];
        if (!value) continue;
        const hits = byOffset.get(value >>> 0);
        if (!hits) continue;
        for (const hit of hits) {
          add(targetKey(hit.structure.id, hit.record.id), {
            kind: 'pointer',
            structure,
            field,
            record,
            tableId: hit.structure.id,
            label: sourceLabel(pack, structure, record, field),
          });
        }
      }
    }
  }

  // --- 3. 同一个 id 空间里的其它表 --------------------------------------
  // 「忍术记录表 #37」与「忍术名表 #37」说的是同一个忍术；
  // 「角色定义表 #5」与「逐角色成长表 #5」说的是同一个角色。
  // 所以一条记录的「来源」里应该有同一个 id 的其它那张表。
  //
  // 注意要**文本表也进来**：名表在文本侧、记录表在结构侧，
  // 只遍历结构表的话，「道具记录表 #5」就找不到它的同名表。
  const allTables = [
    ...(pack.structures || []),
    ...(pack.texts || []),
  ];
  for (const structure of allTables) {
    const space = idSpace(pack, structure.id);
    if (space.length < 2) continue;
    for (const alias of space) {
      if (alias === structure.id) continue;
      const other = pack.structure(alias) || pack.textTable(alias);
      if (!other) continue;
      for (const record of structure.records || []) {
        const peer = (other.records || [])[record.id];
        if (!peer) continue;
        add(targetKey(alias, peer.id), {
          kind: 'idspace',
          structure,
          record,
          tableId: alias,
          label: `${structure.label} · 同一个 id`,
        });
      }
    }
  }

  // --- 4. 同键对应（同一件事在另一张表里各记一份） ----------------------
  // 战斗的「四件套」：战场布置按关卡编号，角色出生点 / 战场物件 /
  // 战斗目标按「关卡 × 变体 × 槽」编号，但讲的是同一关。
  // 这个关系是**双向**的：两边都要看得到对方。
  for (const structure of pack.structures || []) {
    const peers = structure.peers || [];
    if (!peers.length) continue;
    for (const peer of peers) {
      const other = pack.structure(peer.table);
      if (!other) continue;
      const byKey = new Map();
      for (const record of other.records || []) {
        byKey.set(peerKey(other, record, peer.by), record);
      }
      for (const record of structure.records || []) {
        const hit = byKey.get(peerKey(structure, record, peer.by));
        if (!hit) continue;
        const same = peer.by === 'stage' ? '同一关' : '同一个 id';
        // 这一条说的是「**谁**在讲同一件事」，所以标签写的是**来源那张表**。
        add(targetKey(other.id, hit.id), {
          kind: 'peer',
          structure,
          record,
          tableId: other.id,
          label: `${structure.label} · ${same}`,
        });
        add(targetKey(structure.id, record.id), {
          kind: 'peer',
          structure: other,
          record: hit,
          tableId: structure.id,
          label: `${other.label} · ${same}`,
        });
      }
    }
  }

  // --- 5. 文本表：共用同一段字 / 归属别处 --------------------------------
  for (const table of pack.texts || []) {
    for (const record of table.records || []) {
      const shared = record.shared_with || [];
      for (const other of shared) {
        add(targetKey(table.id, other), {
          kind: 'shared',
          table,
          record,
          tableId: table.id,
          label: `${table.label} · #${record.id}（同一段字）`,
        });
      }
      if (record.owned_by) {
        // owned_by 的格式是 `表id#记录id`（导出器写的），所以能跳回去。
        const [ownerTable, ownerRecord] = String(record.owned_by).split('#');
        add(targetKey(table.id, record.id), {
          kind: 'owned',
          table,
          record,
          tableId: table.id,
          ownerTableId: ownerTable,
          ownerRecordId: Number(ownerRecord),
          label: `${table.label} · 归属 ${record.owned_by}`,
        });
      }
    }
  }

  // --- 6. 剧情脚本 → 头像指针表 ------------------------------------------
  // op 0x08「设置头像 + 说话人名字」的字节落在头像表的 64 条之内
  // （仓库的 opcode 表已证这一条，实测取值 1..61）。
  const portraits = pack.structure('portrait_table');
  if (portraits) {
    for (const script of pack.scripts || []) {
      for (const ref of script.portraits || []) {
        const record = (portraits.records || [])[ref.portrait_id];
        if (!record) continue;
        add(targetKey('portrait_table', record.id), {
          kind: 'script',
          script,
          record,
          tableId: 'portrait_table',
          label: `${scriptLabel(script)} · 设置头像`,
        });
      }
    }
  }

  return index;
}

/** 「战前剧情 第 3 场」 */
function scriptLabel(script) {
  const root = { before: '战前剧情', after: '战后剧情', logic: '战场事件逻辑', events: '战场事件' };
  return `${root[script.root] || script.root} 第 ${script.scene} 场`;
}

/**
 * The key two records of different tables are matched on.
 *
 * `by: "stage"` uses the 关卡号 from the table's `index_scheme`
 * (so 「关卡 12 · 变体 1 · 槽 3」and 「关卡 12」match);
 * `by: "id"` uses the record index itself.
 */function peerKey(structure, record, by) {
  if (by === 'id') return `id:${record.id}`;
  const scheme = structure && structure.index_scheme;
  if (scheme && scheme.parts) {
    const key = indexKey(structure, record);
    if (key) {
      const stage = key.parts.find((p) => p.key === 'stage');
      if (stage) return `stage:${stage.value}`;
    }
  }
  // 没有 index_scheme 的表：它的记录下标**就是**关卡号（战场布置描述符就是）。
  return `stage:${record.id}`;
}

/**
 * The label of a referring record: 「谁、在哪、用哪个字段指向我」。
 */
function sourceLabel(pack, structure, record, field) {
  // 记录自己的名字最有用（任务索引表的「第40关」），其次是它指向的名字。
  const own = record && record.label;
  const name = own || idRelationName(pack, structure, record);
  const where = name || structure.label || structure.id;
  const fieldLabel = field.label || field.key;
  return `${where} · ${fieldLabel}`;
}

/**
 * Everything that leads to this record: fields, pointers, shared bytes.
 *
 * @param {ContentPack} pack
 * @param {{kind: string, id: string, recordId: number}} target
 * @returns {Array<{kind: string, structure?: object, field?: object, record?: object,
 *                  table?: object, tableId: string, label: string}>}
 */
export function recordSources(pack, target) {
  if (!target || target.recordId === null || target.recordId === undefined) return [];
  const index = sourceIndex(pack);
  const list = index.get(targetKey(target.id, target.recordId));
  if (!list) return [];
  return list.slice();
}

/**
 * How many places lead to this record (the badge on the list row).
 */
export function sourceCount(pack, target) {
  if (!target || target.recordId === null || target.recordId === undefined) return 0;
  const index = sourceIndex(pack);
  const list = index.get(targetKey(target.id, target.recordId));
  return list ? list.length : 0;
}

/**
 * Which stages own a given mission-text index.
 *
 * `mission_index` maps a stage to the first of its three reward rows, but
 * the mapping is **not** `3 × (stage − 1)`: stages 0, 1 and 47 share index 0,
 * and stages 32..39 are not multiples of three.  So the reward table's rows
 * have to be resolved by reading the index, not by arithmetic.
 *
 * @param {ContentPack} pack
 * @returns {Map<number, Array<{stage: number, sub: number}>>}
 */
export function missionIndexOwners(pack) {
  const owners = new Map();
  const index = pack.structure('mission_index');
  if (!index) return owners;
  for (const record of index.records || []) {
    const stage = record.id;
    const base = record.values ? record.values.value : undefined;
    if (base === undefined) continue;
    for (let sub = 0; sub < 3; sub++) {
      const slot = base + sub;
      if (!owners.has(slot)) owners.set(slot, []);
      owners.get(slot).push({ stage, sub });
    }
  }
  return owners;
}

/** "第 40 关子 1" */
export function ownerLabel(owner) {
  return `第 ${owner.stage} 关子 ${owner.sub}`;
}

/**
 * Which records hold a pointer to this address?
 *
 * The pack's own relation kinds answer 「谁引用了这个 id」, but a **pointer**
 * has no id — it is an address.  Audio descriptors, resource pointers and
 * script operands are all raw addresses, so the backward direction has to
 * scan the `ptr` fields of every structure.
 *
 * @param {ContentPack} pack
 * @param {number} address  a ROM address
 * @returns {Array<{structure: object, field: object, record: object, label: string}>}
 */
export function backReferencesByPointer(pack, address) {
  const out = [];
  if (!address) return out;
  for (const structure of pack.structures || []) {
    for (const field of structure.fields || []) {
      if (field.type !== 'ptr') continue;
      for (const record of structure.records || []) {
        const value = record.values ? record.values[field.key] : undefined;
        if (value !== address) continue;
        out.push({
          structure,
          field,
          record,
          label: referenceLabel(pack, structure, record, field),
        });
      }
    }
  }
  return out;
}
