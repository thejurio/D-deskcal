"""
Example of how to integrate auto-update functionality into ui_main.py

This shows the minimal changes needed to add auto-update to your existing UI.
"""

# Add these imports to the top of ui_main.py
from auto_update_integration import integrate_auto_update, add_update_menu_action

# In your MainWindow class, add this to __init__ method:
class MainWindow(QWidget):  # or QMainWindow
    def __init__(self):
        super().__init__()
        
        # Your existing initialization code...
        self.init_ui()
        self.setup_system_tray()
        
        # ADD THIS: Auto-update integration
        try:
            self.auto_updater = integrate_auto_update(self)
            print("Auto-update system initialized")
        except Exception as e:
            print(f"Auto-update initialization failed: {e}")
            self.auto_updater = None
    
    def create_tray_menu(self):
        """Your existing tray menu creation method"""
        menu = QMenu()
        
        # Your existing menu items...
        show_action = QAction("Show", self)
        show_action.triggered.connect(self.show_window)
        menu.addAction(show_action)
        
        hide_action = QAction("Hide", self)  
        hide_action.triggered.connect(self.hide_window)
        menu.addAction(hide_action)
        
        menu.addSeparator()
        
        # ADD THIS: Update check menu item
        if self.auto_updater:
            update_action = QAction("Check for Updates", self)
            update_action.triggered.connect(self.auto_updater.manual_check)
            menu.addAction(update_action)
            menu.addSeparator()
        
        # Your existing quit action...
        quit_action = QAction("Quit", self)
        quit_action.triggered.connect(self.quit_application)
        menu.addAction(quit_action)
        
        return menu
    
    def quit_application(self):
        """Your existing quit method"""
        # ADD THIS: Stop auto-updater
        if hasattr(self, 'auto_updater') and self.auto_updater:
            self.auto_updater.stop_periodic_check()
        
        # Your existing quit logic...
        QApplication.quit()

# Alternative: If you have a menu bar, add this method:
def setup_menu_bar(self):
    """Setup menu bar with auto-update option"""
    menubar = self.menuBar()
    
    # Your existing menus...
    file_menu = menubar.addMenu('File')
    edit_menu = menubar.addMenu('Edit')
    
    # ADD THIS: Help menu with update check
    help_menu = menubar.addMenu('Help')
    
    if self.auto_updater:
        add_update_menu_action(help_menu, self.auto_updater)
        help_menu.addSeparator()
    
    about_action = QAction('About', self)
    about_action.triggered.connect(self.show_about)
    help_menu.addAction(about_action)

# That's it! The auto-updater will:
# 1. Check for updates every 24 hours automatically
# 2. Show a dialog when updates are available
# 3. Handle download and installation
# 4. Restart the application after update