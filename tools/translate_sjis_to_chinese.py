#!/usr/bin/env python3
"""RETIRED -- this tool must not be run.

It used to translate SJIS bytes into Chinese characters with the
hand-made table ``sequel/content/text/sjis-to-tile-mapping.json`` and to
write the result straight into ``sequel/editor.db``.  That is now
**actively dangerous**, for three reasons that were all proved later:

1. **The ROM does not store Shift-JIS.**  It stores a custom double-byte
   font code (``0x80..0x9F`` lead byte) that indexes the ROM's own
   bitmap font -- see ``notes/font-encoding.md``.  Decoding the ROM's
   bytes as SJIS produces the wrong text.
2. **The hand-made table's values are themselves double-encoded mojibake**
   (e.g. ``"浠€"`` is really ``"什"``), and the sentences it claims to
   describe are not at the offsets it gives.  ``tools/font_roundtrip.py``
   now asserts this: 0 of 20 sampled entries match the ROM.
3. It read ``build/naruto-sequel-dev.gba`` (the sequel build) while the
   editor mirror is meant to describe ``rom/base.gba``, and it wrote the
   result into the editor database.  Since the editor->build override
   chain now treats any row that differs from the seed as an author edit,
   running this tool would have pushed mojibake into the base ROM.

The sanctioned path is ``tools/text_codec.py``::

    mapping, report = text_codec.load_mapping()      # fingerprint-checked
    text, nxt   = text_codec.decode_at(rom, off, mapping)
    raw         = text_codec.encode_text("漩涡鸣人", mapping)

``tools/find_sjis_blocks.py`` and ``tools/decode_dialogue_record.py`` were
migrated to that codec; ``tools/import_dialogue.py`` is the write-back
entry point.  See ``notes/font-encoding.md`` and
``notes/text-writeback-migration-20261020.md``.

Kept as a shim so that an old command line fails loudly instead of
quietly corrupting the editor database.
"""
from __future__ import annotations

import sys

MESSAGE = (
    "tools/translate_sjis_to_chinese.py 已退役。\n"
    "  原因：ROM 存的是游戏自有双字节字形码，不是 Shift-JIS；旧手工表的值本身是"
    "双重编码乱码；它还从 dev ROM 读、往 editor.db 写。\n"
    "  请改用 tools/text_codec.py（load_mapping / decode_at / encode_text），"
    "写回走 tools/import_dialogue.py。\n"
    "  详见 notes/font-encoding.md 与 notes/text-writeback-migration-20261020.md。"
)


def main(argv: list[str] | None = None) -> int:
    print(MESSAGE, file=sys.stderr)
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
