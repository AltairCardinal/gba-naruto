// Byte-level helpers shared by the pack model and the ROM writer.
// Everything is little-endian: the GBA is a little-endian 32-bit machine.

export const HEX = '0123456789abcdef';

export function bytesToHex(bytes) {
  let out = '';
  for (let i = 0; i < bytes.length; i++) {
    out += HEX[bytes[i] >> 4] + HEX[bytes[i] & 15];
  }
  return out;
}

export function hexToBytes(hex) {
  const clean = String(hex).replace(/[^0-9a-fA-F]/g, '');
  if (clean.length % 2 !== 0) throw new Error(`hex 长度必须是偶数: ${hex.length}`);
  const out = new Uint8Array(clean.length / 2);
  for (let i = 0; i < out.length; i++) {
    out[i] = parseInt(clean.substr(i * 2, 2), 16);
  }
  return out;
}

export function bytesToBase64(bytes) {
  let binary = '';
  const chunk = 0x8000;
  for (let i = 0; i < bytes.length; i += chunk) {
    binary += String.fromCharCode.apply(null, bytes.subarray(i, i + chunk));
  }
  return btoa(binary);
}

export function base64ToBytes(text) {
  const binary = atob(text);
  const out = new Uint8Array(binary.length);
  for (let i = 0; i < binary.length; i++) out[i] = binary.charCodeAt(i);
  return out;
}

/** Read an unsigned little-endian integer of 1/2/4 bytes. */
export function readUint(bytes, offset, size) {
  let value = 0;
  for (let i = size - 1; i >= 0; i--) value = value * 256 + bytes[offset + i];
  return value;
}

/** Read a signed little-endian integer of 1/2/4 bytes. */
export function readInt(bytes, offset, size) {
  const raw = readUint(bytes, offset, size);
  const signBit = 1 << (size * 8 - 1);
  return raw >= signBit ? raw - (signBit * 2) : raw;
}

/** Write an unsigned little-endian integer of 1/2/4 bytes into `bytes`. */
export function writeUint(bytes, offset, size, value) {
  let v = value >>> 0;
  for (let i = 0; i < size; i++) {
    bytes[offset + i] = v & 0xff;
    v = Math.floor(v / 256);
  }
  return bytes;
}

/** Convert a ROM file offset to the pointer value the game stores. */
export const ROM_BASE = 0x08000000;

export function offsetToPointer(offset) {
  return offset + ROM_BASE;
}

export function pointerToOffset(pointer) {
  return pointer - ROM_BASE;
}

export function isRomPointer(pointer, romSize) {
  return (
    pointer >= ROM_BASE &&
    pointer < ROM_BASE + romSize
  );
}

export function formatHex(value, width) {
  const text = '0x' + (value >>> 0).toString(16).toUpperCase();
  const pad = width ? width * 2 : 0;
  return pad ? text.padStart(pad + 2, '0') : text;
}

/** Read a NUL-terminated ASCII-ish string out of a byte range. */
export function readCString(bytes, offset, maxLength) {
  const limit = Math.min(bytes.length, offset + (maxLength ?? bytes.length));
  let end = offset;
  while (end < limit && bytes[end] !== 0) end++;
  let out = '';
  for (let i = offset; i < end; i++) {
    const b = bytes[i];
    out += b >= 0x20 && b < 0x7f ? String.fromCharCode(b) : '.';
  }
  return out;
}
