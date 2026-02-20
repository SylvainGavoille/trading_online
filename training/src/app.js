// Import core engine modules
import { showTutorial, initializeKeyboardNavigation } from './engine/ui.js';
import { countTotalItems, loadProgress, updateProgress, resetProgress } from './engine/progress.js';
import { initializeNavigation } from './engine/navigation.js';
import { checkAnswer, checkConfig, checkAlgorithm } from './engine/exercises.js';

class TrainingApp {
    constructor() {
        this.courseData = null;
        // Set up global app functions immediately
        window.app = {
            handleProgress: () => {
                updateProgress();
            },
            checkAnswer: async (questionId, selectedAnswer) => {
                await checkAnswer(questionId, selectedAnswer);
            },
            checkConfig: async () => {
                await checkConfig();
            },
            checkAlgorithm: async () => {
                await checkAlgorithm();
            },
            resetProgress
        };
    }

    async initialize() {
        try {
            // Load course data
            const response = await fetch('./courses/quantum-trading/course.json');
            this.courseData = await response.json();

            // Initialize UI components first
            await this.initializeUI();

            // Set up event listeners
            this.setupEventListeners();

            // Initialize core functionality after UI is ready
            countTotalItems();
            loadProgress();
            initializeNavigation();
            initializeKeyboardNavigation();

        } catch (error) {
            console.error('Failed to initialize training app:', error);
            console.error(error.stack);
        }
    }

    async initializeUI() {
        // Set course title
        document.querySelector('h1').textContent = this.courseData.title;

        // Create navigation buttons
        const navContainer = document.getElementById('level-nav');
        navContainer.innerHTML = this.courseData.levels
            .map((level, index) => `
                <button class="nav-btn ${index === 0 ? 'active' : ''}" 
                        data-level="${index + 1}">
                    Level ${index + 1}
                </button>
            `).join('');

        // Create level content
        const contentContainer = document.getElementById('content');
        contentContainer.innerHTML = this.courseData.levels
            .map((level, index) => `
                <div class="level ${index === 0 ? 'active' : ''}" id="level${index + 1}">
                    <h2>${level.title}</h2>
                    <p class="duration">Duration: ${level.duration}</p>
                    
                    ${level.prerequisites ? `
                        <section class="prerequisites">
                            <h3>Prerequisites</h3>
                            <ul>
                                ${level.prerequisites.map(prereq => `
                                    <li>
                                        <input type="checkbox" id="prereq-${level.id}-${level.prerequisites.indexOf(prereq)}" 
                                               onchange="window.app.handleProgress()">
                                        <label for="prereq-${level.id}-${level.prerequisites.indexOf(prereq)}">${prereq}</label>
                                    </li>
                                `).join('')}
                            </ul>
                        </section>
                    ` : ''}

                    <section class="topics">
                        <h3>Topics</h3>
                        ${level.topics.map(topic => `
                            <div class="topic">
                                <h4>${topic.title}</h4>
                                <div class="interactive-content">
                                    <button class="tutorial-btn" data-topic-id="${topic.id}">
                                        View ${topic.type === 'quiz' ? 'Quiz' : topic.type === 'exercise' ? 'Exercise' : 'Tutorial'}
                                    </button>
                                    <div class="tutorial-content" id="${topic.id}"></div>
                                </div>
                            </div>
                        `).join('')}
                    </section>
                </div>
            `).join('');

        // Return a promise that resolves when content is loaded
        return new Promise(resolve => {
            // Use requestAnimationFrame to ensure DOM is updated
            requestAnimationFrame(() => {
                resolve();
            });
        });
    }

    setupEventListeners() {
        // Add click handlers for tutorial buttons
        document.querySelectorAll('.tutorial-btn').forEach(btn => {
            btn.addEventListener('click', async (e) => {
                const topicId = btn.dataset.topicId;
                await showTutorial(topicId);
            });
        });
    }
}

// Initialize the app when the DOM is loaded
document.addEventListener('DOMContentLoaded', () => {
    const app = new TrainingApp();
    app.initialize();
});
