// Reverse references: "who points at this record?"
//
// The pack knows the forward direction (a field is an id into another table),
// so the backward direction can be computed by scanning the pack.  This is
// what lets the editor answer 「改这个忍术会动到谁」and「这个忍具在哪几关掉落」.
//
// The scan is done once per question, not cached — the pack is small enough
// (40 tables / ~6,700 records) that a full pass is a few milliseconds.

import { idRelationName } from './fields.js';

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
