#ifndef KONOHA_BATTLE_PRESENTATION_TEXT_LAYOUT_H
#define KONOHA_BATTLE_PRESENTATION_TEXT_LAYOUT_H

#include <array>
#include <cstddef>
#include <cstdint>

namespace konoha
{

enum class battle_presentation_text_layout_result : std::uint8_t
{
    ok,
    truncated_code,
    invalid_code,
    glyph_overflow,
};

struct battle_presentation_glyph
{
    std::uint16_t code = 0;
    std::uint8_t column = 0;
    std::uint8_t row = 0;
};

template<std::size_t MaxGlyphs>
class battle_presentation_text_layout
{
    static_assert(MaxGlyphs > 0);

public:
    [[nodiscard]] battle_presentation_text_layout_result build(
            const std::uint8_t* text,
            std::size_t length)
    {
        _glyph_count = 0;
        if(! text && length != 0)
        {
            return battle_presentation_text_layout_result::
                    invalid_code;
        }
        std::uint8_t column = 0;
        std::uint8_t row = 0;
        std::size_t index = 0;
        while(index < length)
        {
            const std::uint8_t lead = text[index];
            if(lead == 0x0A)
            {
                column = 0;
                ++row;
                ++index;
                continue;
            }
            if(! _valid_lead(lead))
            {
                _glyph_count = 0;
                return battle_presentation_text_layout_result::
                        invalid_code;
            }
            if(index + 1 >= length)
            {
                _glyph_count = 0;
                return battle_presentation_text_layout_result::
                        truncated_code;
            }
            const std::uint8_t trail = text[index + 1];
            if(! _valid_trail(trail))
            {
                _glyph_count = 0;
                return battle_presentation_text_layout_result::
                        invalid_code;
            }
            const std::uint16_t code =
                    static_cast<std::uint16_t>(
                            lead << 8) |
                    trail;
            if(code != 0x8140)
            {
                if(_glyph_count == MaxGlyphs)
                {
                    _glyph_count = 0;
                    return battle_presentation_text_layout_result::
                            glyph_overflow;
                }
                _glyphs[_glyph_count] = {
                    code,
                    column,
                    row,
                };
                ++_glyph_count;
            }
            ++column;
            index += 2;
        }
        return battle_presentation_text_layout_result::ok;
    }

    [[nodiscard]] std::size_t glyph_count() const
    {
        return _glyph_count;
    }

    [[nodiscard]] const battle_presentation_glyph* glyph(
            std::size_t index) const
    {
        return index < _glyph_count ?
                &_glyphs[index] :
                nullptr;
    }

private:
    [[nodiscard]] static constexpr bool _valid_lead(
            std::uint8_t value)
    {
        return (value >= 0x81 && value <= 0x9F) ||
                (value >= 0xE0 && value <= 0xFC);
    }

    [[nodiscard]] static constexpr bool _valid_trail(
            std::uint8_t value)
    {
        return (value >= 0x40 && value <= 0x7E) ||
                (value >= 0x80 && value <= 0xFC);
    }

    std::array<battle_presentation_glyph, MaxGlyphs>
            _glyphs = {};
    std::size_t _glyph_count = 0;
};

}

#endif
