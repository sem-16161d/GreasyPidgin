// max js script

var attackTimes = [];

// Add a new attack timestamp (in seconds)
function newAttackTimeStamp(t) {
    attackTimes.push(t);
}

// Delete all entries older than n seconds relative to 'now'
function clearOlderThan(n, now) {
    var cutoff = now - n;

    while (attackTimes.length > 0 && attackTimes[0] < cutoff) {
        attackTimes.shift();
    }
}

// Density WITHOUT modifying the original buffer
function getNSecondDensity(n, now) {
    var cutoff = now - n;

    var count = 0;

    // Iterate from the end (faster if recent events matter most)
    for (var i = attackTimes.length - 1; i >= 0; i--) {
        if (attackTimes[i] < cutoff) break;
        if (attackTimes[i] <= now) count++;
    }

    var density = count / n;

    // Normalize + clip
    var normalized = density / 20;
    normalized = Math.max(0, Math.min(1, normalized));
	normalized = normalized**0.25;
    outlet(0, n, normalized);
}