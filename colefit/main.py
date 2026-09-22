import sys
from PyQt5.QtWidgets import QApplication
from .model import BDSModel
from .view import ColeView
from .controller import ColeController

def main():
    app = QApplication(sys.argv)
    
    # Dark mode stylesheet – consistent with Global Fit window
    app.setStyleSheet("""
        /* ── Base widget ── */
        QWidget {
            background-color: #12121f;
            color: #e0e0ff;
            font-size: 10pt;
            font-family: "Segoe UI", Arial, sans-serif;
        }

        /* ── Main window ── */
        QMainWindow {
            background-color: #12121f;
        }

        /* ── Buttons ── */
        QPushButton {
            background-color: #1a1a2e;
            color: #e0e0ff;
            border: 1px solid #333355;
            border-radius: 4px;
            padding: 5px 12px;
        }
        QPushButton:hover {
            background-color: #252545;
            border: 1px solid #00FFCC;
            color: #00FFCC;
        }
        QPushButton:pressed {
            background-color: #0d0d1a;
        }
        QPushButton:disabled {
            background-color: #0d0d1a;
            color: #444466;
            border: 1px solid #222244;
        }

        /* ── Text input ── */
        QLineEdit {
            background-color: #0d0d1a;
            color: #e0e0ff;
            border: 1px solid #333355;
            border-radius: 3px;
            padding: 3px 6px;
        }
        QLineEdit:focus {
            border: 1px solid #00FFCC;
        }

        /* ── SpinBox ── */
        QSpinBox {
            background-color: #0d0d1a;
            color: #e0e0ff;
            border: 1px solid #333355;
            border-radius: 3px;
            padding: 2px 4px;
        }
        QSpinBox::up-button, QSpinBox::down-button {
            background-color: #1a1a2e;
            border: none;
        }
        QSpinBox::up-button:hover, QSpinBox::down-button:hover {
            background-color: #252545;
        }

        /* ── Label ── */
        QLabel {
            color: #e0e0ff;
        }

        /* ── MessageBox ── */
        QMessageBox {
            background-color: #1a1a2e;
        }
        QMessageBox QLabel {
            color: #e0e0ff;
        }

        /* ── Dialog ── */
        QDialog {
            background-color: #1a1a2e;
        }

        /* ── ProgressDialog ── */
        QProgressDialog {
            background-color: #1a1a2e;
        }
        QProgressBar {
            background-color: #0d0d1a;
            border: 1px solid #333355;
            border-radius: 3px;
            text-align: center;
            color: #e0e0ff;
        }
        QProgressBar::chunk {
            background-color: #00FFCC;
            border-radius: 3px;
        }

        /* ── Scrollbar ── */
        QScrollBar:vertical {
            background-color: #0d0d1a;
            width: 10px;
        }
        QScrollBar::handle:vertical {
            background-color: #333355;
            border-radius: 4px;
        }

        /* ── Toolbar (matplotlib NavigationToolbar) ── */
        QToolBar {
            background-color: #1a1a2e;
            border: none;
            spacing: 2px;
        }
        QToolButton {
            background-color: #1a1a2e;
            color: #e0e0ff;
            border: none;
            border-radius: 3px;
            padding: 3px;
        }
        QToolButton:hover {
            background-color: #252545;
        }

        /* ── QTextEdit (Terminal) ── */
        QTextEdit {
            background-color: #050510;
            color: #00FFCC;
            font-family: "Consolas", "Courier New", monospace;
            border: 1px solid #333355;
            border-radius: 4px;
            padding: 5px;
        }

        /* ── FileDialog ── */
        QFileDialog {
            background-color: #1a1a2e;
        }
    """)
    
    model = BDSModel()
    view = ColeView()
    controller = ColeController(model, view)
    
    view.show()
    sys.exit(app.exec_())

if __name__ == '__main__':
    main()
