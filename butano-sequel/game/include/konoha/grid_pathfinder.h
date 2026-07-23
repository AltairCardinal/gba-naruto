#ifndef KONOHA_GRID_PATHFINDER_H
#define KONOHA_GRID_PATHFINDER_H

#include <array>
#include <cstddef>
#include <cstdint>
#include <limits>

namespace konoha
{

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
    grid_map()
    {
        _costs.fill(1);
        _occupied.fill(false);
    }

    [[nodiscard]] constexpr bool contains(grid_point value) const
    {
        return value.x >= 0 && value.x < Width && value.y >= 0 && value.y < Height;
    }

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

    [[nodiscard]] static constexpr int index(grid_point value)
    {
        return value.y * Width + value.x;
    }

    [[nodiscard]] static constexpr grid_point from_index(int value)
    {
        return { value % Width, value / Width };
    }

private:
    std::array<std::uint8_t, Width * Height> _costs;
    std::array<bool, Width * Height> _occupied;
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
[[nodiscard]] reachable_cost_result<Width, Height> compute_reachable_costs(
        const grid_map<Width, Height>& map, grid_point start, int budget)
{
    reachable_cost_result<Width, Height> result;
    result.costs.fill(-1);
    if(budget < 0 || ! map.contains(start) || map.cost(start) == 0)
    {
        return result;
    }

    constexpr int cell_count = Width * Height;
    std::array<bool, cell_count> visited = {};
    result.valid = true;
    result.costs[static_cast<std::size_t>(map.index(start))] = 0;
    constexpr std::array<grid_point, 4> directions = {
        grid_point{ 0, -1 }, grid_point{ -1, 0 }, grid_point{ 1, 0 }, grid_point{ 0, 1 }
    };

    for(int iteration = 0; iteration < cell_count; ++iteration)
    {
        int current = -1;
        for(int candidate = 0; candidate < cell_count; ++candidate)
        {
            const int candidate_cost = result.costs[static_cast<std::size_t>(candidate)];
            if(visited[static_cast<std::size_t>(candidate)] || candidate_cost < 0)
            {
                continue;
            }
            if(current < 0 || candidate_cost < result.costs[static_cast<std::size_t>(current)])
            {
                current = candidate;
            }
        }
        if(current < 0)
        {
            break;
        }
        visited[static_cast<std::size_t>(current)] = true;
        const grid_point current_point = map.from_index(current);
        for(grid_point direction : directions)
        {
            const grid_point neighbor = {
                current_point.x + direction.x,
                current_point.y + direction.y,
            };
            if(! map.contains(neighbor) || map.cost(neighbor) == 0 || map.occupied(neighbor))
            {
                continue;
            }
            const int neighbor_index = map.index(neighbor);
            const int next_cost = result.costs[static_cast<std::size_t>(current)] +
                    map.cost(neighbor);
            int& known_cost = result.costs[static_cast<std::size_t>(neighbor_index)];
            if(next_cost <= budget && (known_cost < 0 || next_cost < known_cost))
            {
                known_cost = next_cost;
            }
        }
    }
    return result;
}

template<int Width, int Height, std::size_t Capacity>
[[nodiscard]] path_result<Capacity> find_path(
        const grid_map<Width, Height>& map, grid_point start, grid_point goal, int budget)
{
    path_result<Capacity> result;
    if(budget < 0 || ! map.contains(start) || ! map.contains(goal) || map.cost(start) == 0 ||
            map.cost(goal) == 0 || (goal != start && map.occupied(goal)))
    {
        return result;
    }

    constexpr int cell_count = Width * Height;
    constexpr int infinity = std::numeric_limits<int>::max() / 4;
    std::array<int, cell_count> distances;
    std::array<int, cell_count> parents;
    std::array<int, cell_count> discovery_order;
    std::array<bool, cell_count> visited = {};
    distances.fill(infinity);
    parents.fill(-1);
    discovery_order.fill(infinity);

    const int start_index = map.index(start);
    const int goal_index = map.index(goal);
    distances[start_index] = 0;
    discovery_order[start_index] = 0;
    int next_order = 1;
    constexpr std::array<grid_point, 4> directions = {
        grid_point{ 0, -1 }, grid_point{ -1, 0 }, grid_point{ 1, 0 }, grid_point{ 0, 1 }
    };

    for(int iteration = 0; iteration < cell_count; ++iteration)
    {
        int current = -1;
        for(int candidate = 0; candidate < cell_count; ++candidate)
        {
            if(visited[candidate] || distances[candidate] == infinity)
            {
                continue;
            }
            if(current < 0 || distances[candidate] < distances[current] ||
                    (distances[candidate] == distances[current] &&
                     discovery_order[candidate] < discovery_order[current]))
            {
                current = candidate;
            }
        }
        if(current < 0 || current == goal_index)
        {
            break;
        }
        visited[current] = true;
        const grid_point current_point = map.from_index(current);
        for(grid_point direction : directions)
        {
            const grid_point neighbor = {
                current_point.x + direction.x, current_point.y + direction.y
            };
            if(! map.contains(neighbor) || map.cost(neighbor) == 0 || map.occupied(neighbor))
            {
                continue;
            }
            const int neighbor_index = map.index(neighbor);
            const int candidate_distance = distances[current] + map.cost(neighbor);
            if(candidate_distance <= budget && candidate_distance < distances[neighbor_index])
            {
                distances[neighbor_index] = candidate_distance;
                parents[neighbor_index] = current;
                discovery_order[neighbor_index] = next_order++;
            }
        }
    }

    if(distances[goal_index] == infinity)
    {
        return result;
    }

    std::array<int, cell_count> reverse_path;
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

}

#endif
