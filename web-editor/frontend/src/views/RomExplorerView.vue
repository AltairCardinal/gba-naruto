<script setup lang="ts">
import { onMounted, computed } from 'vue'
import { useRomExplorerStore } from '../stores/romExplorerStore'

const store = useRomExplorerStore()

onMounted(() => {
  store.loadStructures()
})

const currentStruct = computed(() =>
  store.structures.find(s => s.name === store.currentStructure)
)

const columns = computed(() => currentStruct.value?.fields.map(f => f.name) ?? [])
</script>

<template>
  <div class="rom-explorer">
    <h2>🔍 ROM Explorer <span class="version">Phase 5 — read-only mirror of 27 reverse-engineered structures</span></h2>

    <div v-if="store.error" class="error-banner">⚠️ {{ store.error }}</div>

    <div class="layout">
      <aside class="sidebar">
        <h3>Structures ({{ store.structures.length }})</h3>
        <ul v-if="store.structures.length">
          <li
            v-for="s in store.structures"
            :key="s.name"
            :class="{ active: s.name === store.currentStructure }"
            @click="store.loadStructure(s.name)"
          >
            <span class="name">{{ s.name }}</span>
            <span class="count">{{ s.entries_in_db }}</span>
          </li>
        </ul>
        <div v-else-if="store.loading" class="loading">loading…</div>
      </aside>

      <main class="main-pane">
        <div v-if="!store.currentStructure" class="empty">
          ← 从左侧选择一个 structure 浏览。
        </div>

        <div v-else>
          <div class="structure-header">
            <h3>{{ store.currentStructure }}</h3>
            <span class="meta">
              {{ store.total }} entries
              <span v-if="currentStruct">
                · {{ currentStruct.fields.length }} fields
                · table <code>{{ currentStruct.table }}</code>
              </span>
            </span>
          </div>

          <div v-if="store.loading" class="loading">loading…</div>

          <div v-else class="table-wrap">
            <table>
              <thead>
                <tr>
                  <th v-for="c in columns" :key="c" :class="{ '_idx': c === '_idx', '_rom_offset': c === '_rom_offset' }">{{ c }}</th>
                </tr>
              </thead>
              <tbody>
                <tr v-for="row in store.rows" :key="row._idx as string | number">
                  <td
                    v-for="c in columns"
                    :key="c"
                    :class="{ '_idx': c === '_idx', '_rom_offset': c === '_rom_offset', 'null-cell': row[c] === null }"
                  >
                    <span v-if="row[c] === null">·</span>
                    <span v-else-if="typeof row[c] === 'number' && (row[c] as number) > 0x10000" class="hex">
                      0x{{ (row[c] as number).toString(16).toUpperCase() }}
                    </span>
                    <span v-else>{{ row[c] }}</span>
                  </td>
                </tr>
              </tbody>
            </table>
          </div>
        </div>
      </main>
    </div>
  </div>
</template>

<style scoped>
.rom-explorer {
  padding: 1rem;
}
.version {
  font-size: 0.7em;
  color: #888;
  margin-left: 1rem;
  font-weight: normal;
}
.error-banner {
  background: #fee;
  border: 1px solid #fcc;
  padding: 0.5rem 1rem;
  margin-bottom: 1rem;
  border-radius: 4px;
  color: #c00;
}
.layout {
  display: grid;
  grid-template-columns: 280px 1fr;
  gap: 1rem;
  height: calc(100vh - 200px);
}
.sidebar {
  background: #f8f8f8;
  border: 1px solid #ddd;
  border-radius: 6px;
  padding: 1rem;
  overflow-y: auto;
}
.sidebar h3 { margin-top: 0; font-size: 0.9em; color: #555; }
.sidebar ul { list-style: none; padding: 0; margin: 0; }
.sidebar li {
  padding: 0.4rem 0.6rem;
  cursor: pointer;
  border-radius: 4px;
  display: flex;
  justify-content: space-between;
  font-size: 0.85em;
}
.sidebar li:hover { background: #eef; }
.sidebar li.active { background: #4a90e2; color: white; }
.sidebar li.active .count { color: white; }
.count {
  font-weight: bold;
  color: #888;
  font-size: 0.85em;
}
.main-pane {
  background: white;
  border: 1px solid #ddd;
  border-radius: 6px;
  padding: 1rem;
  overflow: auto;
}
.empty {
  display: flex;
  align-items: center;
  justify-content: center;
  height: 100%;
  color: #999;
  font-style: italic;
}
.structure-header h3 { margin: 0; }
.structure-header .meta { color: #888; font-size: 0.85em; }
.table-wrap { overflow: auto; }
table {
  width: 100%;
  border-collapse: collapse;
  font-family: 'SF Mono', 'Consolas', monospace;
  font-size: 0.85em;
}
th, td {
  border: 1px solid #eee;
  padding: 0.3rem 0.6rem;
  text-align: left;
  white-space: nowrap;
}
th {
  background: #f5f5f5;
  position: sticky;
  top: 0;
  z-index: 1;
}
tr:nth-child(even) { background: #fafafa; }
td._idx, th._idx { color: #888; }
td._rom_offset, th._rom_offset { color: #06c; font-weight: bold; }
.null-cell { color: #ccc; }
.hex { color: #06c; }
code {
  background: #f0f0f0;
  padding: 1px 4px;
  border-radius: 3px;
  font-size: 0.85em;
}
.loading { color: #888; padding: 1rem; }
</style>