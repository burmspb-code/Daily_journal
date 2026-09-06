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
    
    if (profileModal) {
        profileModal.addEventListener('show.bs.modal', function() {
            // Загружаем форму через AJAX
            fetch("/users/profile/")
                .then(response => response.text())
                .then(html => {
                    profileFormContainer.innerHTML = html;
                })
                .catch(error => {
                    profileFormContainer.innerHTML = '<div class="alert alert-danger">Ошибка загрузки формы</div>';
                });
        });
    }
    
    // Обработка отправки формы
    if (profileForm) {
        profileForm.addEventListener('submit', function(e) {
            e.preventDefault();
            
            const formData = new FormData(this);
            const csrftoken = getCookie('csrftoken');
            
            fetch("/users/profile/", {
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
                    // Закрываем модальное окно
                    const modal = bootstrap.Modal.getInstance(profileModal);
                    modal.hide();
                    // Перезагружаем страницу для обновления данных
                    location.reload();
                } else {
                    // Показываем ошибки
                    let errorHtml = '<div class="alert alert-danger">';
                    for (const [field, errors] of Object.entries(data.errors)) {
                        errorHtml += `<div><strong>${field}:</strong> ${Array.isArray(errors) ? errors.join(', ') : errors}</div>`;
                    }
                    errorHtml += '</div>';
                    profileFormContainer.innerHTML = errorHtml + profileFormContainer.innerHTML;
                }
            })
            .catch(error => {
                alert('Ошибка при сохранении профиля');
            });
        });
    }
});
