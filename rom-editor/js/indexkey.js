// Composite record keys and empty records.
//
// Some tables are indexed by a *composite* key: 角色出生点 is
// (stage × variant × slot), 战场物件 is (stage × variant × object).
// The content pack says how to decompose the record index
// (`structure.index_scheme`), so the editor can show
// 「第 12 关 · 变体 1 · 槽 3」instead of a bare number the author has to
// compute by hand.

/**
 * Decompose a record index into its composite parts.
 *
 * The parts are listed **outer to inner**; the outer part is the high-order
 * part of the index.
 *
 * @param {object} structure
 * @param {object} record
 * @returns {{parts: object[], text: string, id: number}|null}
 */
export function indexKey(structure, record) {
  const scheme = structure && structure.index_scheme;
  if (!scheme || !record) return null;
  const parts = scheme.parts || [];
  if (!parts.length) return null;

  let rest = record.id;
  const values = {};
  // 先把最内层（最低位）算出来：每一步除以该层的容量。
  for (let i = parts.length - 1; i >= 0; i--) {
    const part = parts[i];
    const count = part.count || 1;
    values[part.key] = rest % count;
    rest = Math.floor(rest / count);
  }
  const text = parts
    .map((part) => (part.text || '{' + part.key + '}')
      .replace(/\{(\w+)\}/g, (_, key) => String(values[key])))
    .join(' · ');
  return { parts: parts.map((p) => ({ ...p, value: values[p.key] })), text, id: record.id };
}

/**
 * Is this record empty?
 *
 * "Empty" means every *known* field is zero — the unknown-byte filler
 * (`hex`) does not count, because it is never zero in the data.
 */
export function isEmptyRecord(structure, record) {
  if (!structure || !record) return false;
  for (const field of structure.fields || []) {
    if (field.type === 'hex') continue;
    const value = record.values ? record.values[field.key] : undefined;
    if (value === undefined || value === null) continue;
    if (Number(value) !== 0) return false;
  }
  return true;
}

/**
 * The records of a structure, with the big-table conveniences applied:
 *   * a row limit (the same 200 the text tables use);
 *   * "only the records that have something in them" (for the tables whose
 *     rows are almost all zero);
 *   * "only this stage" (for the composite-key tables).
 */
export function visibleRecords(structure, options = {}) {
  const all = structure.records || [];
  let list = all;
  if (structure.hide_empty && options.showEmpty !== true) {
    list = list.filter((r) => !isEmptyRecord(structure, r));
  }
  if (options.onlyStage !== undefined && options.onlyStage !== null) {
    list = list.filter((r) => {
      const key = indexKey(structure, r);
      if (!key) return true;
      const stage = key.parts.find((p) => p.key === 'stage');
      return stage ? stage.value === options.onlyStage : true;
    });
  }
  const limit = options.limit || 200;
  return { list, shown: list.slice(0, limit), total: list.length, hidden: Math.max(0, list.length - limit) };
}
