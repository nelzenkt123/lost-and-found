document.addEventListener('DOMContentLoaded', () => {
    // 1. Theme Management (Dark/Light mode)
    const themeToggleBtn = document.getElementById('theme-toggle');
    const getPreferredTheme = () => {
        const storedTheme = localStorage.getItem('theme');
        if (storedTheme) {
            return storedTheme;
        }
        return window.matchMedia('(prefers-color-scheme: dark)').matches ? 'dark' : 'light';
    };

    const setTheme = (theme) => {
        document.documentElement.setAttribute('data-theme', theme);
        localStorage.setItem('theme', theme);
        
        // Update button icon
        if (themeToggleBtn) {
            const icon = themeToggleBtn.querySelector('i');
            if (icon) {
                if (theme === 'dark') {
                    icon.className = 'fas fa-sun';
                } else {
                    icon.className = 'fas fa-moon';
                }
            }
        }
    };

    // Initialize theme
    setTheme(getPreferredTheme());

    if (themeToggleBtn) {
        themeToggleBtn.addEventListener('click', () => {
            const currentTheme = document.documentElement.getAttribute('data-theme');
            const newTheme = currentTheme === 'dark' ? 'light' : 'dark';
            setTheme(newTheme);
        });
    }

    // 2. Image Upload Preview
    const fileInput = document.getElementById('item-image');
    const previewContainer = document.getElementById('image-upload-preview');
    const uploadPlaceholder = document.getElementById('upload-placeholder');

    if (fileInput && previewContainer) {
        fileInput.addEventListener('change', function() {
            const file = this.files[0];
            if (file) {
                const reader = new FileReader();
                reader.addEventListener('load', function() {
                    previewContainer.src = this.result;
                    previewContainer.style.display = 'block';
                    if (uploadPlaceholder) {
                        uploadPlaceholder.style.display = 'none';
                    }
                });
                reader.readAsDataURL(file);
            } else {
                previewContainer.src = '';
                previewContainer.style.display = 'none';
                if (uploadPlaceholder) {
                    uploadPlaceholder.style.display = 'flex';
                }
            }
        });
    }

    // 3. Auto-Dismiss Toasts
    const toasts = document.querySelectorAll('.toast');
    toasts.forEach(toast => {
        setTimeout(() => {
            toast.style.animation = 'fadeOut 0.3s cubic-bezier(0.16, 1, 0.3, 1) forwards';
            setTimeout(() => {
                toast.remove();
            }, 300);
        }, 5000);
    });

    // 4. Dashboard Tab Switcher
    const tabs = document.querySelectorAll('.dashboard-tab');
    const tabContents = document.querySelectorAll('.dashboard-tab-content');

    if (tabs.length > 0 && tabContents.length > 0) {
        tabs.forEach(tab => {
            tab.addEventListener('click', () => {
                const targetTab = tab.getAttribute('data-tab');
                
                // Remove active classes
                tabs.forEach(t => t.classList.remove('active'));
                tabContents.forEach(content => content.style.display = 'none');
                
                // Add active class to clicked tab and show related content
                tab.classList.add('active');
                const targetContent = document.getElementById(`tab-content-${targetTab}`);
                if (targetContent) {
                    targetContent.style.display = 'block';
                }
            });
        });
        
        // Show first tab by default
        tabs[0].click();
    }
});
