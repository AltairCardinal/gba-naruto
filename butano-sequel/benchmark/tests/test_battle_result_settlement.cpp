// Measure the remake's post-battle settlement for S49 with the production
// tables, and write a machine readable receipt.
//
// S49 is the original's battle 14.  The original's post-battle state was
// observed by the reverse side (notes/scenario-49-battle-14-runtime-20260720.md):
//
//   Naruto  LV5 -> LV6, HP 138 -> 152 (+14), status page "EXP 100/325"
//   Sasuke  LV4 -> LV6, HP 104 -> 134 (+30)
//   Sakura  LV5 -> LV6, HP 110 -> 125 (+15)
//
// This probe answers a narrower question with the real code instead of with
// a Python mirror: *what does the remake's own settlement produce?*  It uses
// the production tables (reward records, experience thresholds, character
// growth) and the production settlement function, and it prints one JSON
// receipt so the result can be diffed without re-reading C++.
//
// The receipt path comes from KONOHA_SETTLEMENT_RECEIPT; when it is unset
// the probe only prints to stdout.

#include "konoha/battle_campaign.h"
#include "konoha/battle_campaign_route.h"
#include "konoha/battle_progression.h"
#include "konoha/battle_results.h"

#include <cassert>
#include <cstdio>
#include <cstdlib>
#include <fstream>
#include <string>
#include <vector>

using namespace konoha;

namespace
{

struct settlement_row
{
    int character_id = 0;
    int level_before = 0;
    int experience_before = 0;
    int training_points_before = 0;
    int max_hp_before = 0;
    int mission_experience = 0;
    int round_bonus_experience = 0;
    int battle_experience = 0;
    int gained_total = 0;
    int level_after = 0;
    int experience_after = 0;
    int training_points_after = 0;
    int max_hp_after = 0;
};

int max_hp_at_level(int character_id, int level)
{
    if(character_id < 0 ||
            character_id >= static_cast<int>(unit_definitions.size()))
    {
        return 0;
    }
    return character_stats_at_level(
            unit_definitions[character_id],
            character_growth_definitions[character_id],
            level)
        .max_hp;
}

std::string json_rows(const std::vector<settlement_row>& rows)
{
    std::string result = "[";
    for(std::size_t index = 0; index < rows.size(); ++index)
    {
        const settlement_row& row = rows[index];
        if(index != 0)
        {
            result += ",";
        }
        result += "{";
        result += "\"character_id\":" + std::to_string(row.character_id);
        result += ",\"level_before\":" + std::to_string(row.level_before);
        result += ",\"experience_before\":" +
                  std::to_string(row.experience_before);
        result += ",\"training_points_before\":" +
                  std::to_string(row.training_points_before);
        result += ",\"max_hp_before\":" + std::to_string(row.max_hp_before);
        result += ",\"mission_experience\":" +
                  std::to_string(row.mission_experience);
        result += ",\"round_bonus_experience\":" +
                  std::to_string(row.round_bonus_experience);
        result += ",\"battle_experience\":" +
                  std::to_string(row.battle_experience);
        result += ",\"gained_total\":" + std::to_string(row.gained_total);
        result += ",\"level_after\":" + std::to_string(row.level_after);
        result += ",\"experience_after\":" +
                  std::to_string(row.experience_after);
        result += ",\"training_points_after\":" +
                  std::to_string(row.training_points_after);
        result += ",\"max_hp_after\":" + std::to_string(row.max_hp_after);
        result += "}";
    }
    result += "]";
    return result;
}

} // namespace

int main()
{
    // The campaign state the remake starts S49 with: chapter 49 and the
    // team_seven party, seeded by the route's default branch.
    battle_campaign_state campaign;
    assert(prepare_battle_campaign_stage_in_place(campaign).success());
    assert(campaign.chapter_id == 49);

    const int battle_id = 14;
    const int variant = 0;
    const int record = battle_reward_record_for_scenario(battle_id, variant);
    assert(record != no_battle_reward_record);
    const battle_reward_definition& reward = battle_reward_definitions[record];

    // The S49 walk ends the battle inside the reward's round limit, so the
    // round bonus is paid.
    const int battle_round = 4;
    const int round_bonus = battle_round <= reward.round_limit ?
                                   reward.round_bonus_experience :
                                   0;

    // The original's own rule (closed in
    // notes/s49-post-battle-exp-rule-20260720.md):
    //   gain = mission_experience (everyone)
    //        + round_bonus (everyone, while the round is within the limit)
    //        + carried_experience of the units that member defeated.
    // Battle 14's five enemies each carry 50, and the original's recorded
    // route credits them Naruto 1, Sasuke 4, Sakura 0.
    auto carried_experience_for = [](std::uint8_t character_id) {
        switch(character_id)
        {
            case 1: return 50;
            case 2: return 200;
            default: return 0;
        }
    };

    std::vector<settlement_row> rows;
    for(std::uint8_t index = 0; index < campaign.party.size(); ++index)
    {
        const std::uint8_t character_id = campaign.party[index];
        if(character_id == 0 ||
                character_id >= campaign.characters.size())
        {
            continue;
        }
        const character_progression_record& before =
                campaign.characters[character_id].progression;
        if(! before.active)
        {
            continue;
        }
        const int battle_experience = carried_experience_for(character_id);
        const int gained = reward.mission_experience + round_bonus +
                           battle_experience;
        const level_settlement settlement = settle_character_progression(
                before, gained);
        settlement_row row;
        row.character_id = character_id;
        row.level_before = before.level;
        row.experience_before = before.experience;
        row.training_points_before = before.training_points;
        row.max_hp_before = max_hp_at_level(character_id, before.level);
        row.mission_experience = reward.mission_experience;
        row.round_bonus_experience = round_bonus;
        row.battle_experience = battle_experience;
        row.gained_total = gained;
        row.level_after = settlement.after.level;
        row.experience_after = settlement.after.experience;
        row.training_points_after = settlement.after.training_points;
        row.max_hp_after = max_hp_at_level(
                character_id, settlement.after.level);
        rows.push_back(row);
    }

    assert(rows.size() == 3);

    // The original's recorded post-battle state: all three reach LV6 with
    // 100 / 35 / 180 experience left (notes/s49-post-battle-exp-rule-20260720.md).
    assert(rows[0].character_id == 1);
    assert(rows[0].level_after == 6);
    assert(rows[0].experience_after == 100);
    assert(rows[0].max_hp_after == 152);
    assert(rows[1].character_id == 2);
    assert(rows[1].level_after == 6);
    assert(rows[1].experience_after == 35);
    assert(rows[1].max_hp_after == 134);
    assert(rows[2].character_id == 3);
    assert(rows[2].level_after == 6);
    assert(rows[2].experience_after == 180);
    assert(rows[2].max_hp_after == 125);

    const std::string payload =
            std::string("{\"schema\":\"konoha.s49-result-settlement.v1\",") +
            "\"battle_id\":" + std::to_string(battle_id) + "," +
            "\"variant\":" + std::to_string(variant) + "," +
            "\"reward_record\":" + std::to_string(record) + "," +
            "\"mission_experience\":" +
            std::to_string(reward.mission_experience) + "," +
            "\"round_bonus_experience\":" + std::to_string(round_bonus) + "," +
            "\"round_limit\":" + std::to_string(reward.round_limit) + "," +
            "\"battle_experience_by_character\":[" +
            std::to_string(rows[0].battle_experience) + "," +
            std::to_string(rows[1].battle_experience) + "," +
            std::to_string(rows[2].battle_experience) + "]," +
            "\"battle_round\":" + std::to_string(battle_round) + "," +
            "\"party\":" + json_rows(rows) + "}";

    const char* receipt_path = std::getenv("KONOHA_SETTLEMENT_RECEIPT");
    if(receipt_path != nullptr && receipt_path[0] != '\0')
    {
        std::ofstream output(receipt_path);
        assert(output.is_open());
        output << payload << "\n";
    }
    std::printf("%s\n", payload.c_str());
    return 0;
}
