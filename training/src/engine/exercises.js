// Exercise handling functionality

// Quiz functionality
export async function checkAnswer(questionId, selectedAnswer) {
    const feedback = document.getElementById(`${questionId}-feedback`);
    
    try {
        // Find the topic element to get the quiz ID
        const questionElement = document.getElementById(`${questionId}-feedback`).closest('.tutorial-content');
        const quizId = questionElement.id;
        
        // Keep the -quiz suffix since that's how the files are named
        const response = await fetch(`./courses/quantum-trading/content/exercises/${quizId}-quiz.json`);
        if (!response.ok) {
            throw new Error(`HTTP error! status: ${response.status}`);
        }
        const quizData = await response.json();
        
        // Find the question
        const question = quizData.questions.find(q => q.id === questionId);
        if (!question) {
            throw new Error(`Question ${questionId} not found`);
        }

        console.log('Checking answer:', selectedAnswer, 'against correct:', question.correctAnswer);

        // Check answer and show feedback
        if (selectedAnswer === question.correctAnswer) {
            feedback.textContent = question.feedback.correct;
            feedback.className = 'feedback correct';
            
            // Add to progress if not already completed
            const progressKey = `quiz_${questionId}`;
            if (!localStorage.getItem(progressKey)) {
                localStorage.setItem(progressKey, 'completed');
                // Import progress module functions
                const { progress, updateProgressBar } = await import('./progress.js');
                progress.completedItems++;
                updateProgressBar();
            }
        } else {
            feedback.textContent = question.feedback.incorrect;
            feedback.className = 'feedback incorrect';
        }
    } catch (error) {
        console.error('Error checking answer:', error);
        feedback.textContent = 'Error checking answer. Please try again.';
        feedback.className = 'feedback error';
    }
}

// Configuration exercise checker
export async function checkConfig() {
    const configText = document.getElementById('adv-config-input').value;
    const feedback = document.getElementById('adv-config-feedback');
    
    try {
        // Parse and validate the configuration
        const hasPositionLimits = configText.includes('max_position_size') && 
                                 configText.includes('max_portfolio_exposure');
        const hasLossLimits = configText.includes('daily_loss_limit') && 
                             configText.includes('max_drawdown');
        
        // Check if all placeholder values are replaced
        const hasPlaceholders = configText.includes('???');
        
        // Check for reasonable values
        const values = {
            position_size: parseFloat(configText.match(/max_position_size:\s*(\d+)/)?.[1]),
            portfolio_exposure: parseFloat(configText.match(/max_portfolio_exposure:\s*(0\.\d+)/)?.[1]),
            daily_loss: parseFloat(configText.match(/daily_loss_limit:\s*(\d+)/)?.[1]),
            drawdown: parseFloat(configText.match(/max_drawdown:\s*(0\.\d+)/)?.[1])
        };

        if (hasPlaceholders) {
            feedback.textContent = 'Please replace all ??? with appropriate values.';
            feedback.className = 'feedback incorrect';
            return;
        }
        
        if (!hasPositionLimits || !hasLossLimits) {
            feedback.textContent = 'Configuration is incomplete. Make sure to include all required parameters.';
            feedback.className = 'feedback incorrect';
            return;
        }

        // Validate reasonable ranges for values
        if (values.position_size > 0 && values.position_size <= 1000 &&
            values.portfolio_exposure > 0 && values.portfolio_exposure <= 1 &&
            values.daily_loss > 0 && values.daily_loss <= 10000 &&
            values.drawdown > 0 && values.drawdown <= 1) {
            
            feedback.textContent = 'Configuration looks good! The values are within reasonable ranges.';
            feedback.className = 'feedback correct';
            
            // Add to progress if not already completed
            if (!localStorage.getItem('config_exercise')) {
                localStorage.setItem('config_exercise', 'completed');
                // Import progress module functions
                const { progress, updateProgressBar } = await import('./progress.js');
                progress.completedItems++;
                updateProgressBar();
            }
        } else {
            feedback.textContent = 'Some values appear to be outside reasonable ranges. Please review your configuration.';
            feedback.className = 'feedback incorrect';
        }
    } catch (error) {
        feedback.textContent = 'Invalid configuration format. Please check your syntax.';
        feedback.className = 'feedback incorrect';
    }
}

// Algorithm exercise checker
export async function checkAlgorithm() {
    const algoText = document.getElementById('algo-exercise').value;
    const feedback = document.getElementById('algo-feedback');
    
    try {
        // Check if all placeholders are replaced
        if (algoText.includes('???')) {
            feedback.textContent = 'Please replace all ??? with appropriate code.';
            feedback.className = 'feedback incorrect';
            return;
        }

        // Check for required components
        const hasMA = algoText.includes('ma_period') && 
                     (algoText.includes('rolling().mean()') || algoText.includes('rolling().average()'));
        const hasStdDev = algoText.includes('std_dev') && 
                         algoText.includes('rolling().std()');
        const hasBands = algoText.includes('upper_band') && 
                        algoText.includes('lower_band');
        
        if (!hasMA || !hasStdDev || !hasBands) {
            feedback.textContent = 'Implementation incomplete. Make sure to include moving average, standard deviation, and bands calculation.';
            feedback.className = 'feedback incorrect';
            return;
        }

        feedback.textContent = 'Algorithm implementation looks good! The components are properly structured.';
        feedback.className = 'feedback correct';
        
        // Add to progress if not already completed
        if (!localStorage.getItem('algo_exercise')) {
            localStorage.setItem('algo_exercise', 'completed');
            // Import progress module functions
            const { progress, updateProgressBar } = await import('./progress.js');
            progress.completedItems++;
            updateProgressBar();
        }
    } catch (error) {
        feedback.textContent = 'Invalid algorithm implementation. Please check your code.';
        feedback.className = 'feedback incorrect';
    }
}
