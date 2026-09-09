// Adapted from myjian/mai-tools, commit 1d1ce89b76950816845e5f82707ab108ae35d0a0.
// See LICENSE and NOTICE.md in this directory.
export function compareNumber(a, b) {
    return a > b ? 1 : a < b ? -1 : 0;
}
export function sum(values) {
    let total = 0;
    for (const v of values) {
        total += v;
    }
    return total;
}
export function roundFloat(num, method, unit) {
    return Math[method](num / unit) * unit;
}
export function formatFloat(n, digits) {
    if (n) {
        return n.toFixed(digits);
    }
    return "0";
}
