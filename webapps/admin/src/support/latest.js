// Typing, sorting, paging and moving from one record to the next overlap, and an earlier answer arriving later would put back what nobody asked for.
export function newest() {
    let sequence = 0;

    return {
        take: () => (sequence += 1),

        // The attempt in force, for work that must hear whether a later one replaced it without replacing anything itself.
        current: () => sequence,
        stale: (attempt) => attempt !== sequence,
    };
}
