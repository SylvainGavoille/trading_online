// Navigation functionality
export function showLevel(levelNum) {
    // Update navigation buttons
    document.querySelectorAll('.nav-btn').forEach(btn => {
        btn.classList.remove('active');
    });
    document.querySelector(`[data-level="${levelNum}"]`).classList.add('active');

    // Show selected level content
    document.querySelectorAll('.level').forEach(level => {
        level.classList.remove('active');
    });
    document.getElementById(`level${levelNum}`).classList.add('active');
}

// Initialize navigation
export function initializeNavigation() {
    // Add click handlers to navigation buttons
    document.querySelectorAll('.nav-btn').forEach(btn => {
        btn.addEventListener('click', () => {
            const level = parseInt(btn.dataset.level);
            showLevel(level);
        });
    });

    // Set initial level
    showLevel(1);
}
