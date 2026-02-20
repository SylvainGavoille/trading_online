// UI related functionality
import { parseMarkdown } from './markdown.js';
import { showLevel } from './navigation.js';

export async function showTutorial(id) {
    console.log(`Showing tutorial/quiz for ${id}`);
    const content = document.getElementById(id);
    const allTutorials = document.querySelectorAll('.tutorial-content');
    
    // Hide all other tutorials
    allTutorials.forEach(tutorial => {
        if (tutorial.id !== id) {
            tutorial.style.display = 'none';
        }
    });
    
    // If content is not already loaded, fetch it
    if (content.dataset.loaded !== 'true') {
        try {
            console.log('Fetching course data...');
            // Fetch course data to get content info
            const courseResponse = await fetch('./courses/quantum-trading/course.json');
            if (!courseResponse.ok) {
                throw new Error(`HTTP error! status: ${courseResponse.status}`);
            }
            const courseData = await courseResponse.json();
            
            // Find the topic in course data
            let topic;
            for (const level of courseData.levels) {
                topic = level.topics.find(t => t.id === id);
                if (topic) break;
            }
            
            if (!topic) {
                throw new Error(`Topic ${id} not found in course data`);
            }

            console.log('Found topic:', topic);

            // Determine content path based on type and content field from course.json
            const contentPath = `./courses/quantum-trading/content/${topic.type === 'tutorial' ? 'tutorials' : 'exercises'}/${topic.content}`;
            console.log('Loading content from:', contentPath);
            
            // Fetch content
            const response = await fetch(contentPath);
            if (!response.ok) {
                throw new Error(`HTTP error! status: ${response.status}`);
            }
            const data = await response.text();
            console.log('Content loaded successfully');
            
            // For tutorials, render markdown
            if (topic.type === 'tutorial') {
                const htmlContent = parseMarkdown(data);
                content.innerHTML = `<div class="markdown-content">${htmlContent}</div>`;
            } else {
                // For quizzes and exercises, parse JSON and render appropriate template
                const exercise = JSON.parse(data);
                if (exercise.questions) {
                    console.log('Rendering quiz with', exercise.questions.length, 'questions');
                    // Render quiz
                    content.innerHTML = `
                        <h5>${exercise.title}</h5>
                        <p>${exercise.description}</p>
                        <div class="quiz">
                            ${exercise.questions.map(q => `
                                <div class="question">
                                    <p>${q.question}</p>
                                    ${q.options.map(opt => `
                                        <div class="option">
                                            <input type="radio" 
                                                   name="q${q.id}" 
                                                   id="${q.id}${opt.id}" 
                                                   data-question="${q.id}"
                                                   data-answer="${opt.id}">
                                            <label for="${q.id}${opt.id}">${opt.text}</label>
                                        </div>
                                    `).join('')}
                                    <div class="feedback" id="${q.id}-feedback"></div>
                                </div>
                            `).join('')}
                        </div>
                    `;

                    // Add event listeners to all radio inputs in the quiz
                    content.querySelectorAll('input[type="radio"]').forEach(input => {
                        input.addEventListener('change', () => {
                            const questionId = input.dataset.question;
                            const answerId = input.dataset.answer;
                            window.app.checkAnswer(questionId, answerId);
                        });
                    });
                } else {
                    console.log('Rendering exercise');
                    // Render exercise
                    content.innerHTML = `
                        <h5>${exercise.title}</h5>
                        <p>${exercise.description}</p>
                        <textarea id="${id}-input" rows="10" cols="50">${exercise.template}</textarea>
                        <button onclick="window.app.checkConfig()" class="action-btn">Check Configuration</button>
                        <div id="${id}-feedback" class="feedback"></div>
                    `;
                }
            }
            
            content.dataset.loaded = 'true';
        } catch (error) {
            console.error(`Failed to load content for ${id}:`, error);
            content.innerHTML = '<p class="error">Failed to load content. Please try again.</p>';
        }
    }
    
    // Toggle visibility
    content.style.display = content.style.display === 'block' ? 'none' : 'block';
}

// Keyboard navigation disabled
export function initializeKeyboardNavigation() {
    // Function intentionally left empty to disable keyboard navigation
}
