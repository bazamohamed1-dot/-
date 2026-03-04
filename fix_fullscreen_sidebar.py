import re

def update_fullscreen_logic(file_path):
    with open(file_path, 'r', encoding='utf-8') as f:
        content = f.read()

    new_js = """
<script>
    function toggleFullscreen() {
        const elem = document.documentElement;
        const icon = document.getElementById('fullscreenIcon');
        const sidebar = document.querySelector('.sidebar');
        const header = document.querySelector('.header');
        const mainContent = document.querySelector('.main');
        const wrapper = document.getElementById('fullscreenWrapper');

        if (!document.fullscreenElement) {
            if (elem.requestFullscreen) {
                elem.requestFullscreen().catch(err => {
                    alert(`Error attempting to enable fullscreen: ${err.message} (${err.name})`);
                });
            } else if (elem.webkitRequestFullscreen) { /* Safari */
                elem.webkitRequestFullscreen();
            } else if (elem.msRequestFullscreen) { /* IE11 */
                elem.msRequestFullscreen();
            }
            icon.classList.remove('fa-eye');
            icon.classList.add('fa-eye-slash');

            // Hide Sidebar and Header to cover entire screen
            if (sidebar) sidebar.style.display = 'none';
            if (header) header.style.display = 'none';
            if (mainContent) {
                mainContent.style.marginLeft = '0';
                mainContent.style.paddingTop = '0';
                mainContent.style.padding = '10px';
            }
            if (wrapper) {
                wrapper.style.margin = '0';
                wrapper.style.padding = '10px';
            }
        } else {
            if (document.exitFullscreen) {
                document.exitFullscreen();
            } else if (document.webkitExitFullscreen) { /* Safari */
                document.webkitExitFullscreen();
            } else if (document.msExitFullscreen) { /* IE11 */
                document.msExitFullscreen();
            }
            icon.classList.remove('fa-eye-slash');
            icon.classList.add('fa-eye');

            // Restore Sidebar and Header
            if (sidebar) sidebar.style.display = '';
            if (header) header.style.display = '';
            if (mainContent) {
                mainContent.style.marginLeft = '';
                mainContent.style.paddingTop = '';
                mainContent.style.padding = '';
            }
            if (wrapper) {
                wrapper.style.margin = '';
                wrapper.style.padding = '20px';
            }
        }
    }

    // Listen for Escape key exit
    document.addEventListener('fullscreenchange', (event) => {
        if (!document.fullscreenElement) {
            const icon = document.getElementById('fullscreenIcon');
            const sidebar = document.querySelector('.sidebar');
            const header = document.querySelector('.header');
            const mainContent = document.querySelector('.main');
            const wrapper = document.getElementById('fullscreenWrapper');

            if (icon) {
                icon.classList.remove('fa-eye-slash');
                icon.classList.add('fa-eye');
            }
            if (sidebar) sidebar.style.display = '';
            if (header) header.style.display = '';
            if (mainContent) {
                mainContent.style.marginLeft = '';
                mainContent.style.paddingTop = '';
                mainContent.style.padding = '';
            }
            if (wrapper) {
                wrapper.style.margin = '';
                wrapper.style.padding = '20px';
            }
        }
    });
</script>
"""

    # Replace the old script
    content = re.sub(r"<script>\s*function toggleFullscreen\(\).*?</script>", new_js, content, flags=re.DOTALL)

    with open(file_path, 'w', encoding='utf-8') as f:
        f.write(content)

update_fullscreen_logic('./students/templates/students/analytics.html')
update_fullscreen_logic('./students/templates/students/advanced_analytics.html')
print("Updated fullscreen toggle in both files")
