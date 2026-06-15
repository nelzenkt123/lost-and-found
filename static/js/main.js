/* FindBack Main JavaScript Interactivity */

document.addEventListener('DOMContentLoaded', () => {
    initTheme();
    initImagePreview();
    initPasswordValidation();
    initNotificationsManager();
});

/**
 * Theme Toggle Management
 * Reads and applies theme (light or dark) from localStorage.
 * Dark mode is default.
 */
function initTheme() {
    const themeToggleBtn = document.getElementById('theme-toggle');
    if (!themeToggleBtn) return;
    
    // Get stored theme or default to dark
    const currentTheme = localStorage.getItem('theme') || 'dark';
    
    // Set theme attribute
    document.documentElement.setAttribute('data-theme', currentTheme);
    updateThemeIcon(currentTheme);
    
    themeToggleBtn.addEventListener('click', () => {
        const activeTheme = document.documentElement.getAttribute('data-theme');
        const newTheme = activeTheme === 'dark' ? 'light' : 'dark';
        
        document.documentElement.setAttribute('data-theme', newTheme);
        localStorage.setItem('theme', newTheme);
        updateThemeIcon(newTheme);
    });
}

function updateThemeIcon(theme) {
    const themeIcon = document.querySelector('#theme-toggle i');
    if (!themeIcon) return;
    
    if (theme === 'light') {
        themeIcon.className = 'bi bi-moon-stars-fill';
    } else {
        themeIcon.className = 'bi bi-sun-fill';
    }
}

/**
 * Image Upload Preview
 * Shows user-uploaded file inside the file input container immediately.
 */
function initImagePreview() {
    const fileInput = document.getElementById('item-image-input');
    const previewBox = document.getElementById('image-preview-box');
    
    if (!fileInput || !previewBox) return;
    
    const previewPlaceholder = previewBox.innerHTML;
    
    fileInput.addEventListener('change', function() {
        const file = this.files[0];
        if (file) {
            const reader = new FileReader();
            reader.addEventListener('load', function() {
                previewBox.innerHTML = `<img src="${this.result}" alt="Preview" class="img-fluid rounded">`;
            });
            reader.readAsDataURL(file);
        } else {
            previewBox.innerHTML = previewPlaceholder;
        }
    });
}

/**
 * Form password matcher
 * Checks registration passwords on the fly.
 */
function initPasswordValidation() {
    const registerForm = document.getElementById('register-form');
    if (!registerForm) return;
    
    const password = document.getElementById('password');
    const confirmPassword = document.getElementById('confirm_password');
    const registerBtn = registerForm.querySelector('button[type="submit"]');
    
    if (!password || !confirmPassword) return;
    
    function validatePasswords() {
        if (password.value !== confirmPassword.value) {
            confirmPassword.setCustomValidity("Passwords do not match.");
            confirmPassword.classList.add('is-invalid');
        } else {
            confirmPassword.setCustomValidity("");
            confirmPassword.classList.remove('is-invalid');
            confirmPassword.classList.add('is-valid');
        }
    }
    
    password.addEventListener('change', validatePasswords);
    confirmPassword.addEventListener('keyup', validatePasswords);
}

/**
 * Notifications Asynchronous Marker
 * Marks notification as read using Fetch API to avoid page refresh.
 */
function initNotificationsManager() {
    const unreadNotifications = document.querySelectorAll('.notification-item.unread');
    
    unreadNotifications.forEach(item => {
        const markReadBtn = item.querySelector('.mark-read-btn');
        if (!markReadBtn) return;
        
        markReadBtn.addEventListener('click', (e) => {
            e.preventDefault();
            const notificationId = item.dataset.id;
            
            fetch(`/notifications/read/${notificationId}`, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json'
                }
            })
            .then(res => res.json())
            .then(data => {
                if (data.success) {
                    item.classList.remove('unread');
                    markReadBtn.remove();
                    
                    // Decrease count in global badges
                    const navBadge = document.querySelector('.navbar .notification-badge');
                    if (navBadge) {
                        let count = parseInt(navBadge.textContent) - 1;
                        if (count <= 0) {
                            navBadge.remove();
                        } else {
                            navBadge.textContent = count;
                        }
                    }
                }
            })
            .catch(err => console.error("Error updating notification: ", err));
        });
    });
}
