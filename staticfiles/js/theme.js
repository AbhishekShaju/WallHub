// Theme switching functionality
document.addEventListener('DOMContentLoaded', () => {
    const themeSwitch = document.querySelector('.theme-switch input[type="checkbox"]');
    
    // Check for saved theme preference, otherwise use system preference
    const currentTheme = localStorage.getItem('theme') || 
        (window.matchMedia('(prefers-color-scheme: dark)').matches ? 'dark' : 'light');
    
    // Set initial theme
    document.documentElement.setAttribute('data-theme', currentTheme);
    if (themeSwitch) {
        themeSwitch.checked = currentTheme === 'dark';
    }
    
    // Handle theme switch
    if (themeSwitch) {
        themeSwitch.addEventListener('change', function(e) {
            if (e.target.checked) {
                document.documentElement.setAttribute('data-theme', 'dark');
                localStorage.setItem('theme', 'dark');
            } else {
                document.documentElement.setAttribute('data-theme', 'light');
                localStorage.setItem('theme', 'light');
            }
        });
    }
}); 