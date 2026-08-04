// === ЗАЩИТА ОТ МУСОРА И RICH TEXT ПРИ ВСТАВКЕ ===

document.addEventListener('paste', function(e) {
    if (e.target.classList.contains('editable-task-name') ||
        e.target.classList.contains('editable-task-comment') ||
        e.target.classList.contains('editable-bookmark-name')) {

        e.preventDefault();
        const text = (e.originalEvent || e).clipboardData.getData('text/plain');
        document.execCommand('insertText', false, text);
    }
});