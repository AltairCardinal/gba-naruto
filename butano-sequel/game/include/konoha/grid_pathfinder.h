#ifndef KONOHA_GRID_PATHFINDER_H
#define KONOHA_GRID_PATHFINDER_H

#include <array>
#include <cstddef>
#include <cstdint>

namespace konoha
{

inline constexpr std::uint8_t grid_terrain_class_one = 1;
inline constexpr std::uint8_t grid_terrain_class_three = 3;
inline constexpr std::uint8_t grid_terrain_class_seven = 7;
inline constexpr std::uint8_t grid_fully_closed = 15;

struct grid_terrain_traversal_limits
{
    int class_one = 0;
    int class_three = 0;
    int class_seven = 0;

    constexpr bool operator==(
            const grid_terrain_traversal_limits&) const = default;
};

struct grid_point
{
    int x;
    int y;

    constexpr bool operator==(const grid_point&) const = default;
};

template<int Width, int Height>
class grid_map
{
    static_assert(Width > 0 && Height > 0);

public:
    static constexpr int capacity_width = Width;
    static constexpr int capacity_height = Height;

    grid_map()
    {
        _reset_cells();
    }

    [[nodiscard]] constexpr int active_width() const
    {
        return _active_width;
    }

    [[nodiscard]] constexpr int active_height() const
    {
        return _active_height;
    }

    [[nodiscard]] constexpr int battle_id() const
    {
        return _battle_id;
    }

    bool set_battle_id(int battle_id)
    {
        if(battle_id < 0 || battle_id > 255)
        {
            return false;
        }
        _battle_id = battle_id;
        return true;
    }

    bool set_active_dimensions(int width, int height)
    {
        if(width <= 0 || width > Width ||
                height <= 0 || height > Height)
        {
            return false;
        }
        _active_width = width;
        _active_height = height;
        _reset_cells();
        return true;
    }

    [[nodiscard]] constexpr bool contains(grid_point value) const
    {
        return value.x >= 0 && value.x < _active_width &&
                value.y >= 0 && value.y < _active_height;
    }

private:
    void _reset_cells()
    {
        _costs.fill(1);
        _occupied.fill(false);
        _flags.fill(0);
        _tile_classes.fill(0);
        _tile_sides.fill(0);
        _terrain_classes.fill(0);
    }

public:

    bool set_cost(grid_point value, std::uint8_t cost)
    {
        if(! contains(value))
        {
            return false;
        }
        _costs[index(value)] = cost;
        return true;
    }

    [[nodiscard]] std::uint8_t cost(grid_point value) const
    {
        return contains(value) ? _costs[index(value)] : 0;
    }

    bool set_occupied(grid_point value, bool occupied)
    {
        if(! contains(value))
        {
            return false;
        }
        _occupied[index(value)] = occupied;
        return true;
    }

    [[nodiscard]] bool occupied(grid_point value) const
    {
        return contains(value) && _occupied[index(value)];
    }

    bool set_flags(grid_point value, std::uint8_t flags)
    {
        if(! contains(value))
        {
            return false;
        }
        _flags[index(value)] = flags;
        return true;
    }

    [[nodiscard]] std::uint8_t flags(grid_point value) const
    {
        return contains(value) ? _flags[index(value)] : 0;
    }

    bool set_tile_class(grid_point value, std::uint8_t tile_class)
    {
        if(! contains(value))
        {
            return false;
        }
        _tile_classes[index(value)] = tile_class;
        return true;
    }

    [[nodiscard]] std::uint8_t tile_class(grid_point value) const
    {
        return contains(value) ? _tile_classes[index(value)] : 0;
    }

    bool set_tile_side(grid_point value, std::uint8_t side)
    {
        if(! contains(value) || side > 1)
        {
            return false;
        }
        _tile_sides[index(value)] = side;
        return true;
    }

    [[nodiscard]] std::uint8_t tile_side(grid_point value) const
    {
        return contains(value) ? _tile_sides[index(value)] : 0;
    }

    bool set_terrain_class(
            grid_point value, std::uint8_t terrain_class)
    {
        if(! contains(value) ||
                terrain_class > grid_fully_closed)
        {
            return false;
        }
        _terrain_classes[index(value)] = terrain_class;
        return true;
    }

    [[nodiscard]] std::uint8_t terrain_class(
            grid_point value) const
    {
        return contains(value) ?
                _terrain_classes[index(value)] :
                grid_fully_closed;
    }

    [[nodiscard]] bool can_step(
            grid_point from, grid_point to) const
    {
        if(! contains(from) || ! contains(to) ||
                cost(from) == 0 || cost(to) == 0 ||
                occupied(to))
        {
            return false;
        }
        const int dx = to.x - from.x;
        const int dy = to.y - from.y;
        const int absolute_dx = dx < 0 ? -dx : dx;
        const int absolute_dy = dy < 0 ? -dy : dy;
        if(absolute_dx + absolute_dy != 1)
        {
            return false;
        }
        return terrain_class(from) != grid_fully_closed &&
               terrain_class(to) != grid_fully_closed;
    }

    [[nodiscard]] static constexpr int index(grid_point value)
    {
        return value.y * Width + value.x;
    }

    [[nodiscard]] static constexpr grid_point from_index(int value)
    {
        return { value % Width, value / Width };
    }

    constexpr bool operator==(const grid_map&) const = default;

private:
    int _battle_id = 0;
    int _active_width = Width;
    int _active_height = Height;
    std::array<std::uint8_t, Width * Height> _costs;
    std::array<bool, Width * Height> _occupied;
    std::array<std::uint8_t, Width * Height> _flags;
    std::array<std::uint8_t, Width * Height> _tile_classes;
    std::array<std::uint8_t, Width * Height> _tile_sides;
    std::array<std::uint8_t, Width * Height>
            _terrain_classes;
};

template<std::size_t Capacity>
struct path_result
{
    bool found = false;
    bool overflow = false;
    int total_cost = 0;
    std::size_t length = 0;
    std::array<grid_point, Capacity> points = {};
};

template<int Width, int Height>
struct pathfinder_workspace
{
    static constexpr int cell_count = Width * Height;

    std::array<int, cell_count> distances = {};
    std::array<int, cell_count> parents = {};
    std::array<int, cell_count> discovery_order = {};
    std::array<bool, cell_count> visited = {};
    std::array<int, cell_count> reverse_path = {};
};

template<int Width, int Height>
struct reachable_cost_result
{
    bool valid = false;
    std::array<int, Width * Height> costs = {};

    [[nodiscard]] int cost(grid_point point) const
    {
        if(point.x < 0 || point.x >= Width || point.y < 0 || point.y >= Height)
        {
            return -1;
        }
        return costs[static_cast<std::size_t>(point.y * Width + point.x)];
    }
};

template<int Width, int Height>
void compute_reachable_costs(
        const grid_map<Width, Height>& map,
        grid_point start,
        int budget,
        grid_terrain_traversal_limits traversal_limits,
        reachable_cost_result<Width, Height>& result)
{
    result = {};
    result.costs.fill(-1);
    if(budget < 0 || ! map.contains(start) ||
            map.cost(start) == 0 ||
            map.terrain_class(start) == grid_fully_closed)
    {
        return;
    }

    result.valid = true;
    const auto consume_terrain =
            [](std::uint8_t terrain_class,
               grid_terrain_traversal_limits& limits)
            {
                int* remaining = nullptr;
                if(terrain_class == grid_terrain_class_one)
                {
                    remaining = &limits.class_one;
                }
                else if(terrain_class ==
                        grid_terrain_class_three)
                {
                    remaining = &limits.class_three;
                }
                else if(terrain_class ==
                        grid_terrain_class_seven)
                {
                    remaining = &limits.class_seven;
                }
                if(! remaining)
                {
                    return terrain_class != grid_fully_closed;
                }
                if(*remaining <= 0)
                {
                    return false;
                }
                --*remaining;
                return true;
            };
    const auto visit =
            [&map, budget, &result, &consume_terrain](
                    auto&& self,
                    grid_point point,
                    int cost,
                    bool start_point,
                    grid_terrain_traversal_limits limits) -> void
            {
                if(cost > budget || ! map.contains(point) ||
                        map.cost(point) == 0 ||
                        (! start_point && map.occupied(point)) ||
                        ! consume_terrain(
                                map.terrain_class(point),
                                limits))
                {
                    return;
                }
                int& known_cost = result.costs[
                        static_cast<std::size_t>(
                                map.index(point))];
                if(known_cost >= 0 && known_cost <= cost)
                {
                    return;
                }
                known_cost = cost;
                constexpr std::array<grid_point, 4>
                        directions = {
                            grid_point{ 0, -1 },
                            grid_point{ -1, 0 },
                            grid_point{ 1, 0 },
                            grid_point{ 0, 1 },
                        };
                for(const grid_point direction : directions)
                {
                    const grid_point neighbor = {
                        point.x + direction.x,
                        point.y + direction.y,
                    };
                    if(! map.contains(neighbor))
                    {
                        continue;
                    }
                    self(
                            self,
                            neighbor,
                            cost + map.cost(neighbor),
                            false,
                            limits);
                }
            };
    visit(
            visit,
            start,
            0,
            true,
            traversal_limits);
}

template<int Width, int Height>
[[nodiscard]] reachable_cost_result<Width, Height> compute_reachable_costs(
        const grid_map<Width, Height>& map,
        grid_point start,
        int budget,
        grid_terrain_traversal_limits traversal_limits)
{
    reachable_cost_result<Width, Height> result;
    compute_reachable_costs(
            map,
            start,
            budget,
            traversal_limits,
            result);
    return result;
}

template<int Width, int Height>
void compute_reachable_costs(
        const grid_map<Width, Height>& map,
        grid_point start,
        int budget,
        grid_terrain_traversal_limits traversal_limits,
        reachable_cost_result<Width, Height>& result,
        pathfinder_workspace<Width, Height>& workspace)
{
    result = {};
    result.costs.fill(-1);
    if(budget < 0 || ! map.contains(start) ||
            map.cost(start) == 0 ||
            map.terrain_class(start) == grid_fully_closed)
    {
        return;
    }

    const auto consume_terrain =
            [](std::uint8_t terrain_class,
               grid_terrain_traversal_limits& limits)
            {
                int* remaining = nullptr;
                if(terrain_class == grid_terrain_class_one)
                {
                    remaining = &limits.class_one;
                }
                else if(terrain_class ==
                        grid_terrain_class_three)
                {
                    remaining = &limits.class_three;
                }
                else if(terrain_class ==
                        grid_terrain_class_seven)
                {
                    remaining = &limits.class_seven;
                }
                if(! remaining)
                {
                    return terrain_class != grid_fully_closed;
                }
                if(*remaining <= 0)
                {
                    return false;
                }
                --*remaining;
                return true;
            };

    std::array<int, Width * Height>& distances =
            workspace.distances;
    std::array<int, Width * Height>& class_one =
            workspace.parents;
    std::array<int, Width * Height>& class_three =
            workspace.discovery_order;
    std::array<int, Width * Height>& class_seven =
            workspace.reverse_path;
    std::array<bool, Width * Height>& visited =
            workspace.visited;
    distances.fill(-1);
    class_one.fill(0);
    class_three.fill(0);
    class_seven.fill(0);
    visited.fill(false);

    if(! consume_terrain(
               map.terrain_class(start),
               traversal_limits))
    {
        return;
    }
    const int start_index = map.index(start);
    distances[start_index] = 0;
    class_one[start_index] = traversal_limits.class_one;
    class_three[start_index] = traversal_limits.class_three;
    class_seven[start_index] = traversal_limits.class_seven;
    result.valid = true;

    constexpr std::array<grid_point, 4> directions = {
        grid_point{ 0, -1 },
        grid_point{ -1, 0 },
        grid_point{ 1, 0 },
        grid_point{ 0, 1 },
    };
    for(int processed = 0;
            processed < Width * Height;
            ++processed)
    {
        int current_index = -1;
        int current_distance = budget + 1;
        grid_point current = {};
        for(int y = 0; y < map.active_height(); ++y)
        {
            for(int x = 0; x < map.active_width(); ++x)
            {
                const grid_point candidate = { x, y };
                const int candidate_index =
                        map.index(candidate);
                const int candidate_distance =
                        distances[candidate_index];
                if(! visited[candidate_index] &&
                        candidate_distance >= 0 &&
                        candidate_distance <
                                current_distance)
                {
                    current_index = candidate_index;
                    current_distance =
                            candidate_distance;
                    current = candidate;
                }
            }
        }
        if(current_index < 0)
        {
            break;
        }
        visited[current_index] = true;
        result.costs[current_index] =
                current_distance;
        for(const grid_point direction : directions)
        {
            const grid_point neighbor = {
                current.x + direction.x,
                current.y + direction.y,
            };
            if(! map.contains(neighbor) ||
                    map.cost(neighbor) == 0 ||
                    (neighbor != start &&
                     map.occupied(neighbor)))
            {
                continue;
            }
            const int neighbor_cost =
                    current_distance +
                    map.cost(neighbor);
            if(neighbor_cost > budget)
            {
                continue;
            }
            grid_terrain_traversal_limits next_limits = {
                class_one[current_index],
                class_three[current_index],
                class_seven[current_index],
            };
            if(! consume_terrain(
                       map.terrain_class(neighbor),
                       next_limits))
            {
                continue;
            }
            const int neighbor_index =
                    map.index(neighbor);
            const int known_distance =
                    distances[neighbor_index];
            if(known_distance >= 0 &&
                    known_distance <= neighbor_cost)
            {
                continue;
            }
            distances[neighbor_index] =
                    neighbor_cost;
            class_one[neighbor_index] =
                    next_limits.class_one;
            class_three[neighbor_index] =
                    next_limits.class_three;
            class_seven[neighbor_index] =
                    next_limits.class_seven;
        }
    }
}

template<int Width, int Height, std::size_t Capacity>
[[nodiscard]] path_result<Capacity> find_path(
        const grid_map<Width, Height>& map,
        grid_point start,
        grid_point goal,
        int budget,
        grid_terrain_traversal_limits traversal_limits,
        pathfinder_workspace<Width, Height>& workspace)
{
    path_result<Capacity> result;
    if(budget < 0 || ! map.contains(start) ||
            ! map.contains(goal) || map.cost(start) == 0 ||
            map.cost(goal) == 0 ||
            map.terrain_class(start) == grid_fully_closed ||
            map.terrain_class(goal) == grid_fully_closed ||
            (goal != start && map.occupied(goal)))
    {
        return result;
    }

    constexpr int cell_count = Width * Height;
    std::array<int, cell_count>& distances =
            workspace.distances;
    std::array<int, cell_count>& parents =
            workspace.parents;
    distances.fill(-1);
    parents.fill(-1);

    const int start_index = map.index(start);
    const int goal_index = map.index(goal);
    const auto consume_terrain =
            [](std::uint8_t terrain_class,
               grid_terrain_traversal_limits& limits)
            {
                int* remaining = nullptr;
                if(terrain_class == grid_terrain_class_one)
                {
                    remaining = &limits.class_one;
                }
                else if(terrain_class ==
                        grid_terrain_class_three)
                {
                    remaining = &limits.class_three;
                }
                else if(terrain_class ==
                        grid_terrain_class_seven)
                {
                    remaining = &limits.class_seven;
                }
                if(! remaining)
                {
                    return terrain_class != grid_fully_closed;
                }
                if(*remaining <= 0)
                {
                    return false;
                }
                --*remaining;
                return true;
            };
    const auto visit =
            [&map,
             budget,
             &distances,
             &parents,
             &consume_terrain](
                    auto&& self,
                    grid_point point,
                    int cost,
                    int parent,
                    grid_terrain_traversal_limits limits) -> void
            {
                if(cost > budget || ! map.contains(point) ||
                        map.cost(point) == 0 ||
                        (parent >= 0 && map.occupied(point)) ||
                        ! consume_terrain(
                                map.terrain_class(point),
                                limits))
                {
                    return;
                }
                const int point_index = map.index(point);
                if(distances[point_index] >= 0 &&
                        distances[point_index] <= cost)
                {
                    return;
                }
                distances[point_index] = cost;
                parents[point_index] = parent;
                constexpr std::array<grid_point, 4>
                        directions = {
                            grid_point{ 0, -1 },
                            grid_point{ -1, 0 },
                            grid_point{ 1, 0 },
                            grid_point{ 0, 1 },
                        };
                for(const grid_point direction : directions)
                {
                    const grid_point neighbor = {
                        point.x + direction.x,
                        point.y + direction.y,
                    };
                    if(! map.contains(neighbor))
                    {
                        continue;
                    }
                    self(
                            self,
                            neighbor,
                            cost + map.cost(neighbor),
                            point_index,
                            limits);
                }
            };
    visit(
            visit,
            start,
            0,
            -1,
            traversal_limits);

    if(distances[goal_index] < 0)
    {
        return result;
    }

    std::array<int, cell_count>& reverse_path =
            workspace.reverse_path;
    std::size_t path_length = 0;
    for(int current = goal_index; current >= 0; current = parents[current])
    {
        reverse_path[path_length++] = current;
        if(current == start_index)
        {
            break;
        }
    }
    if(path_length > Capacity)
    {
        result.overflow = true;
        return result;
    }
    result.found = true;
    result.total_cost = distances[goal_index];
    result.length = path_length;
    for(std::size_t index = 0; index < path_length; ++index)
    {
        result.points[index] = map.from_index(reverse_path[path_length - index - 1]);
    }
    return result;
}

template<int Width, int Height>
[[nodiscard]] reachable_cost_result<Width, Height>
compute_reachable_costs(
        const grid_map<Width, Height>& map,
        grid_point start,
        int budget)
{
    return compute_reachable_costs(
            map, start, budget, {});
}

template<int Width, int Height, std::size_t Capacity>
[[nodiscard]] path_result<Capacity> find_path(
        const grid_map<Width, Height>& map,
        grid_point start,
        grid_point goal,
        int budget,
        pathfinder_workspace<Width, Height>& workspace)
{
    return find_path<Width, Height, Capacity>(
            map,
            start,
            goal,
            budget,
            {},
            workspace);
}

template<int Width, int Height, std::size_t Capacity>
[[nodiscard]] path_result<Capacity> find_path(
        const grid_map<Width, Height>& map,
        grid_point start,
        grid_point goal,
        int budget)
{
    pathfinder_workspace<Width, Height> workspace;
    return find_path<Width, Height, Capacity>(
            map, start, goal, budget, {}, workspace);
}

template<int Width, int Height, std::size_t Capacity>
[[nodiscard]] path_result<Capacity> find_path(
        const grid_map<Width, Height>& map,
        grid_point start,
        grid_point goal,
        int budget,
        grid_terrain_traversal_limits traversal_limits)
{
    pathfinder_workspace<Width, Height> workspace;
    return find_path<Width, Height, Capacity>(
            map,
            start,
            goal,
            budget,
            traversal_limits,
            workspace);
}

}

#endif
