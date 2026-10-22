// The exhaustive ROM text index, loaded on demand.
//
// The index lists every font-coded string in the cartridge (16,915 entries in
// the baseline ROM).  It is far bigger than the core content pack, so it lives
// in its own file and is only fetched when a view actually needs it.
//
// The 剧情与对白 module uses it as the generic text-table editor's source.
// (The battle objective sentences have their own table — `battle_objectives`
// — so the same bytes never belong to two tables.)

import { fetchJsonSmart, editorUrl } from './loader.js';

const TABLE_ID = 'rom_text_index';

/** The in-flight load, so several views can ask for it at the same time. */
let pending = null;

/**
 * Make sure the text index is in the pack, and return it (or null on failure).
 *
 * @param {import('./pack.js').ContentPack} pack
 * @param {(message: string) => void} [onStatus]
 * @returns {Promise<object|null>}
 */
export async function ensureTextIndex(pack, onStatus) {
  if (!pack) return null;
  const existing = pack.textTable(TABLE_ID);
  if (existing) return existing;

  if (!pending) {
    pending = fetchJsonSmart(editorUrl('content/text-index.json'))
      .then((table) => {
        pending = null;
        return table;
      })
      .catch((err) => {
        pending = null;
        throw err;
      });
  }
  try {
    const table = await pending;
    if (!pack.textTable(TABLE_ID)) pack.texts.push(table);
    return pack.textTable(TABLE_ID);
  } catch (err) {
    if (onStatus) onStatus(`全 ROM 文本索引载入失败：${err.message}`);
    return null;
  }
}
