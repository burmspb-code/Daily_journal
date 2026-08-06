/**
 * Адаптированное под Django расширение json-enc для HTMX 2.x
 * Автоматически инжектирует CSRF-токен в заголовки JSON-запросов.
 */
(function() {
    // Вспомогательная функция для чтения CSRF-токена из куки браузера
    function getCsrfToken() {
        let cookieValue = null;
        if (document.cookie && document.cookie !== '') {
            const cookies = document.cookie.split(';');
            for (let i = 0; i < cookies.length; i++) {
                const cookie = cookies[i].trim();
                if (cookie.substring(0, 10) === 'csrftoken=') {
                    cookieValue = decodeURIComponent(cookie.substring(10));
                    break;
                }
            }
        }
        return cookieValue;
    }

    htmx.defineExtension('json-enc', {
        onEvent: function (name, evt) {
            if (name === "htmx:configRequest") {
                // Устанавливаем тип контента как JSON
                evt.detail.headers['Content-Type'] = "application/json";

                // АВТОМАТИЧЕСКАЯ ИНЖЕКЦИЯ CSRF ТОКЕНА ДЛЯ DJANGO
                const csrfToken = getCsrfToken();
                if (csrfToken) {
                    evt.detail.headers['X-CSRFToken'] = csrfToken;
                }
            }
        },

        encodeParameters : function(xhr, parameters, elt) {
            xhr.overrideMimeType('text/json');
            return (JSON.stringify(parameters));
        }
    });
})();
