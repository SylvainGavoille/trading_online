// Progress tracking functionality
export const progress = {
    totalItems: 0,
    completedItems: 0
};

// Count total checkable items for progress tracking
export function countTotalItems() {
    progress.totalItems = document.querySelectorAll('input[type="checkbox"]').length;
}

// Load saved progress from localStorage
export function loadProgress() {
    const savedProgress = localStorage.getItem('quantumTraderProgress');
    if (savedProgress) {
        const checkedItems = JSON.parse(savedProgress);
        checkedItems.forEach(itemId => {
            const checkbox = document.getElementById(itemId);
            if (checkbox) {
                checkbox.checked = true;
                progress.completedItems++;
            }
        });
    }
}

// Save progress to localStorage
export function saveProgress() {
    const checkedItems = Array.from(document.querySelectorAll('input[type="checkbox"]:checked'))
        .map(checkbox => checkbox.id);
    localStorage.setItem('quantumTraderProgress', JSON.stringify(checkedItems));
}

// Update progress bar and text
export function updateProgressBar() {
    const percentage = Math.round((progress.completedItems / progress.totalItems) * 100);
    document.getElementById('progress-bar').style.width = `${percentage}%`;
    document.getElementById('progress-text').textContent = `${percentage}% Complete`;
}

// Handle progress updates when checkboxes are clicked
export function updateProgress() {
    progress.completedItems = document.querySelectorAll('input[type="checkbox"]:checked').length;
    updateProgressBar();
    saveProgress();
}

// Reset progress
export function resetProgress() {
    if (confirm('Are you sure you want to reset all progress? This cannot be undone.')) {
        localStorage.clear();
        document.querySelectorAll('input[type="checkbox"]').forEach(checkbox => {
            checkbox.checked = false;
        });
        progress.completedItems = 0;
        updateProgressBar();
    }
}
