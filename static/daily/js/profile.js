// Функция для получения CSRF токена из куки
function getCookie(name) {
    let cookieValue = null;
    if (document.cookie && document.cookie !== '') {
        const cookies = document.cookie.split(';');
        for (let i = 0; i < cookies.length; i++) {
            const cookie = cookies[i].trim();
            if (cookie.substring(0, name.length + 1) === (name + '=')) {
                cookieValue = decodeURIComponent(cookie.substring(name.length + 1));
                break;
            }
        }
    }
    return cookieValue;
}

// Загрузка формы профиля при открытии модального окна
document.addEventListener('DOMContentLoaded', function() {
    const profileModal = document.getElementById('editProfileModal');
    const profileFormContainer = document.getElementById('profile-form-container');
    const profileForm = document.getElementById('edit-profile-form');

    if (profileModal && profileFormContainer) {
        profileModal.addEventListener('show.bs.modal', function() {
            profileFormContainer.innerHTML = `
                <div class="text-center py-4">
                    <div class="spinner-border text-warning" role="status">
                        <span class="visually-hidden">Загрузка...</span>
                    </div>
                </div>`;

            // Загружаем только поля формы, а не целую страницу
            fetch('/users/profile/', {
                headers: { 'X-Requested-With': 'XMLHttpRequest' }
            })
                .then(response => {
                    if (response.redirected && response.url.includes('/users/login/')) {
                        window.location.href = response.url;
                        throw new Error('redirected');
                    }
                    if (!response.ok) {
                        throw new Error(`HTTP ${response.status}`);
                    }
                    return response.text();
                })
                .then(html => {
                    profileFormContainer.innerHTML = html;
                })
                .catch(error => {
                    if (error.message === 'redirected') {
                        return;
                    }
                    profileFormContainer.innerHTML = `
                        <div class="alert alert-danger mb-0">
                            Не удалось загрузить форму профиля. Обновите страницу и попробуйте снова.
                        </div>`;
                });
        });
    }

    // Обработка отправки формы
    if (profileForm) {
        profileForm.addEventListener('submit', function(e) {
            e.preventDefault();

            const formData = new FormData(this);
            const csrftoken = getCookie('csrftoken') ||
                this.querySelector('[name=csrfmiddlewaretoken]')?.value;

            fetch('/users/profile/', {
                method: 'POST',
                body: formData,
                headers: {
                    'X-Requested-With': 'XMLHttpRequest',
                    'X-CSRFToken': csrftoken
                }
            })
                .then(response => response.json())
                .then(data => {
                    if (data.success) {
                        const modal = bootstrap.Modal.getInstance(profileModal);
                        if (modal) {
                            modal.hide();
                        }
                        location.reload();
                        return;
                    }

                    // Показываем ошибки, не стирая уже введённые значения
                    const oldAlert = profileFormContainer.querySelector('.profile-save-errors');
                    if (oldAlert) {
                        oldAlert.remove();
                    }

                    const alert = document.createElement('div');
                    alert.className = 'alert alert-danger mb-3 profile-save-errors';

                    const errors = data.errors || {};
                    const entries = Object.entries(errors);
                    if (!entries.length) {
                        alert.textContent = 'Не удалось сохранить профиль. Проверьте введённые данные.';
                    } else {
                        for (const [field, fieldErrors] of entries) {
                            const messages = (Array.isArray(fieldErrors) ? fieldErrors : [fieldErrors])
                                .map(error => typeof error === 'string' ? error : (error.message || ''))
                                .filter(Boolean)
                                .join(', ');
                            const row = document.createElement('div');
                            row.textContent = `${field}: ${messages}`;
                            alert.appendChild(row);
                        }
                    }

                    profileFormContainer.prepend(alert);
                })
                .catch(error => {
                    if (typeof window.showNotification === 'function') {
                        window.showNotification('Ошибка при сохранении профиля', 'error');
                    } else {
                        console.error('Ошибка при сохранении профиля:', error);
                    }
                });
        });
    }
});
