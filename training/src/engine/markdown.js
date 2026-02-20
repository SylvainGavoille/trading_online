// Using Showdown for markdown parsing with syntax highlighting
export function parseMarkdown(markdown) {
    // Create Showdown converter with options
    const converter = new showdown.Converter({
        tables: true,
        tasklists: true,
        strikethrough: true,
        ghCodeBlocks: true,
        smartIndentationFix: true,
        simpleLineBreaks: false,
        requireSpaceBeforeHeadingText: true,
        ghMentions: false,
        extensions: [{
            type: 'output',
            regex: /<pre><code\s*(?:class="([^"]*)")?\s*>([\s\S]*?)<\/code><\/pre>/g,
            replace: function(text, language, code) {
                // Decode HTML entities
                code = code.replace(/&lt;/g, '<')
                         .replace(/&gt;/g, '>')
                         .replace(/&amp;/g, '&')
                         .replace(/&quot;/g, '"');
                
                // Apply syntax highlighting
                if (language) {
                    try {
                        code = hljs.highlight(code, {language: language.replace('language-', '')}).value;
                    } catch (e) {
                        // If language-specific highlighting fails, use auto-detection
                        code = hljs.highlightAuto(code).value;
                    }
                } else {
                    // Auto-detect language if none specified
                    code = hljs.highlightAuto(code).value;
                }

                return `<pre><code class="hljs">${code}</code></pre>`;
            }
        }]
    });

    // Set options for GitHub-style markdown
    converter.setOption('ghCompatibleHeaderId', true);
    converter.setOption('customizedHeaderId', true);
    converter.setOption('parseImgDimensions', true);
    converter.setOption('simplifiedAutoLink', true);
    converter.setOption('excludeTrailingPunctuationFromURLs', true);
    converter.setOption('literalMidWordUnderscores', true);
    converter.setOption('tables', true);
    converter.setOption('simpleLineBreaks', true);
    converter.setOption('smartIndentationFix', false);

    // Convert markdown to HTML
    let html = converter.makeHtml(markdown);

    // Clean up any double line breaks
    html = html.replace(/\n\n+/g, '\n');

    return html;
}

// Initialize highlight.js when the module loads
if (typeof hljs !== 'undefined') {
    hljs.configure({
        ignoreUnescapedHTML: true,
        languages: ['javascript', 'python', 'bash', 'json']
    });
}
