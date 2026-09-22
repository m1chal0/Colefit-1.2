import sys
import os
import numpy as np
from itertools import cycle
import matplotlib.pyplot as plt
import matplotlib.patches as patches
from mpl_toolkits.mplot3d import Axes3D # Import for 3D plotting
from matplotlib.backends.backend_qt5agg import FigureCanvasQTAgg as FigureCanvas
from matplotlib.backends.backend_qt5agg import NavigationToolbar2QT as NavigationToolbar
from matplotlib.widgets import Cursor
from PyQt5.QtWidgets import (QWidget, QVBoxLayout, QLabel, QPushButton, QMessageBox,
                             QFileDialog, QGridLayout, QLineEdit, QApplication, QSpinBox,
                             QHBoxLayout, QTextEdit, QSizeGrip)
from PyQt5.QtCore import Qt, QPoint
from PyQt5 import QtCore, QtGui
from .utils import resource_path


class CustomTitleBar(QWidget):
    """
    Frameless custom title bar matching the app dark theme.
    Supports: drag-to-move, double-click-to-maximize, minimize/maximize/close.
    """
    # Accent and background colours – kept in sync with main.py stylesheet
    _BG        = '#1a1a2e'
    _HOVER_MIN = '#252545'
    _HOVER_MAX = '#252545'
    _HOVER_CLS = '#cc2244'
    _ACCENT    = '#00FFCC'
    _TEXT      = '#e0e0ff'

    def __init__(self, parent: QWidget, title: str = '', icon_path: str = ''):
        super().__init__(parent)
        self._parent        = parent
        self._drag_pos      = QPoint()
        self._is_dragging   = False

        self.setFixedHeight(36)
        self.setAutoFillBackground(True)
        self.setAttribute(QtCore.Qt.WA_StyledBackground, True)
        self.setStyleSheet(f"background-color: {self._BG}; border-bottom: 1px solid #333355;")

        layout = QHBoxLayout(self)
        layout.setContentsMargins(8, 0, 4, 0)
        layout.setSpacing(6)

        # ── App icon ──────────────────────────────────────────────────────── #
        self.lbl_icon = QLabel(self)
        self.lbl_icon.setFixedSize(20, 20)
        if icon_path and os.path.exists(icon_path):
            pix = QtGui.QPixmap(icon_path).scaled(
                20, 20,
                QtCore.Qt.KeepAspectRatio,
                QtCore.Qt.SmoothTransformation
            )
            self.lbl_icon.setPixmap(pix)
        layout.addWidget(self.lbl_icon)

        # ── Title label ───────────────────────────────────────────────────── #
        self.lbl_title = QLabel(title, self)
        self.lbl_title.setStyleSheet(
            f"color: {self._ACCENT}; font-weight: bold;"
            f" font-size: 10pt; letter-spacing: 1px; background: transparent;"
        )
        layout.addWidget(self.lbl_title)
        layout.addStretch()

        # ── Window control buttons ────────────────────────────────────────── #
        _btn_style = (
            "QPushButton {{"
            "  background: transparent; border: none;"
            "  color: {fg}; font-size: 13px; padding: 2px 10px;"
            "  border-radius: 3px;"
            "}}"
            "QPushButton:hover {{ background-color: {hov}; }}"
        )

        self.btn_min = QPushButton("\u2014", self)  # ─ (em dash as minimise icon)
        self.btn_min.setFixedSize(36, 28)
        self.btn_min.setStyleSheet(
            _btn_style.format(fg=self._TEXT, hov=self._HOVER_MIN)
        )
        self.btn_min.setToolTip("Minimize")
        self.btn_min.clicked.connect(self._parent.showMinimized)

        self.btn_max = QPushButton("\u25a1", self)  # □ (restore / maximise)
        self.btn_max.setFixedSize(36, 28)
        self.btn_max.setStyleSheet(
            _btn_style.format(fg=self._TEXT, hov=self._HOVER_MAX)
        )
        self.btn_max.setToolTip("Maximize / Restore")
        self.btn_max.clicked.connect(self._toggle_max)

        self.btn_cls = QPushButton("\u00d7", self)  # × (close)
        self.btn_cls.setFixedSize(36, 28)
        self.btn_cls.setStyleSheet(
            _btn_style.format(fg=self._TEXT, hov=self._HOVER_CLS)
        )
        self.btn_cls.setToolTip("Close")
        self.btn_cls.clicked.connect(self._parent.close)

        layout.addWidget(self.btn_min)
        layout.addWidget(self.btn_max)
        layout.addWidget(self.btn_cls)

    # ── public helpers ──────────────────────────────────────────────────── #
    def set_title(self, title: str):
        self.lbl_title.setText(title)

    def hide_max_button(self):
        """Use on sub-windows that should not be maximisable."""
        self.btn_max.hide()

    # ── internals ───────────────────────────────────────────────────────── #
    def _toggle_max(self):
        if self._parent.isMaximized():
            self._parent.showNormal()
            self.btn_max.setText("\u25a1")
        else:
            self._parent.showMaximized()
            self.btn_max.setText("\u25a0")

    # ── mouse events for dragging ───────────────────────────────────────── #
    def mousePressEvent(self, event):
        if event.button() == QtCore.Qt.LeftButton:
            self._drag_pos    = event.globalPos() - self._parent.frameGeometry().topLeft()
            self._is_dragging = True
            event.accept()

    def mouseMoveEvent(self, event):
        if self._is_dragging and event.buttons() == QtCore.Qt.LeftButton:
            if self._parent.isMaximized():
                self._parent.showNormal()
                self.btn_max.setText("\u25a1")
            self._parent.move(event.globalPos() - self._drag_pos)
            event.accept()

    def mouseReleaseEvent(self, event):
        self._is_dragging = False

    def mouseDoubleClickEvent(self, event):
        if event.button() == QtCore.Qt.LeftButton:
            self._toggle_max()


class HelpWindow(QWidget):
    def __init__(self):
        super().__init__()
        # ── Frameless + custom title bar ──────────────────────────────────── #
        self.setWindowFlags(Qt.FramelessWindowHint | Qt.Window)
        self.setAttribute(QtCore.Qt.WA_TranslucentBackground, False)
        self.setMinimumSize(600, 700)
        self.setStyleSheet("background-color: #12121f; border: 1px solid #333355;")

        icon_path = resource_path('res/iconH.ico')
        title_bar = CustomTitleBar(self, title="ColeFIT – User Guide", icon_path=icon_path)
        title_bar.hide_max_button()

        # ── Content ───────────────────────────────────────────────────────── #
        content = QWidget(self)
        layoutH = QVBoxLayout(content)
        layoutH.setContentsMargins(15, 10, 15, 15)
        layoutH.setSpacing(10)

        # Use QTextEdit for rich text guide
        self.guide_text = QTextEdit(content)
        self.guide_text.setReadOnly(True)
        self.guide_text.setStyleSheet("""
            QTextEdit {
                background-color: #0d0d1a;
                color: #e0e0ff;
                border: 1px solid #333355;
                border-radius: 5px;
                padding: 10px;
                font-size: 10pt;
            }
        """)

        guide_html = """
        <h2 style="color: #00FFCC;">ColeFIT ver. 1.2 – User Guide</h2>
        <p>ColeFIT is a professional tool designed for analyzing Broadband Dielectric Spectroscopy (BDS) data using Havriliak-Negami (HN) models and physical relaxation laws.</p>

        <h3 style="color: #aaaacc;">1. Getting Started</h3>
        <p><b>Select Data:</b> Load your .txt or .csv file. The expected format is [Frequency, Temp, Eps', Eps''].<br>
        <b>Temperature:</b> Enter the temperature you wish to analyze and click <i>Process Data</i>.<br>
        <b>Frequency Selection:</b> You can interactively select a frequency range by clicking on <b>Graph 1 (Imaginary)</b> or <b>Graph 3 (Cole-Cole)</b>. Click twice to define the start and end frequency limits.</p>

        <h3 style="color: #aaaacc;">2. Fitting Methods</h3>
        <ul>
            <li><b>Make Fit:</b> Performs a local fit for the current temperature using 1 to 3 HN peaks.</li>
            <li><b>Automatic Analysis:</b> Uses global optimization (Differential Evolution) to find the best fit parameters automatically.</li>
            <li><b>Global 3D Fit:</b> Fits the <b>entire dataset</b> simultaneously using physical laws (Arrhenius or VFT). This is the most robust method for extracting activation energies.</li>
            <li><b>Chain Fit:</b> Automatically processes all temperatures in the file sequentially, using results from the previous step as initial guesses.</li>
        </ul>

        <h3 style="color: #aaaacc;">3. Visualization & Analysis</h3>
        <ul>
            <li><b>Show 3D:</b> Interactive 3D visualization of the whole dataset with model vs. data comparison.</li>
            <li><b>Show Log-Log:</b> Displays data in a broad log-log scale to identify power-law behaviors.</li>
            <li><b>Error Landscape:</b> Generates a 2D χ² contour map (e.g., α vs β). Use this to analyze parameter correlation and fit stability for publications.</li>
            <li><b>Deconvoluted Peaks:</b> Automatically visualizes individual relaxation processes and DC conductivity after a successful fit.</li>
        </ul>

        <h3 style="color: #aaaacc;">4. Results & Exports</h3>
        <ul>
            <li><b>Results Terminal:</b> Displays fit parameters (Δε, τ, α, β, σ_DC) and statistics (BIC, χ²).</li>
            <li><b>Excel Export:</b> Global and Chain fits automatically export results to <b>Excel (.xlsx)</b> files.</li>
            <li><b>PNG Export:</b> High-resolution (300 DPI) export button is available in analysis windows for scientific publications.</li>
        </ul>

        <hr style="border: 0; border-top: 1px solid #333355;">
        <p style="color: #8888aa; font-size: 9pt;">Developed for Dielectric Spectroscopy research by Ing. Ondřej Michal, Ph.D. Faculty of Electrical Engineering, University of West Bohemia in Pilsen, Czechia (mionge@fel.zcu.cz) .</p>
        """
        self.guide_text.setHtml(guide_html)
        layoutH.addWidget(self.guide_text)

        # ── Outer wrapper layout ───────────────────────────────────────────── #
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)
        outer.addWidget(title_bar)
        outer.addWidget(content)
        self.setLayout(outer)

class ColeView(QWidget):
    def __init__(self):
        super().__init__()
        self.controller = None
        self.fit_colors = cycle(['red', 'green', 'purple', 'orange', 'cyan', 'magenta', 'brown'])
        
        self.init_ui()
        
    def init_ui(self):
        # ── Remove native frame; add custom title bar ──────────────────────── #
        self.setWindowFlags(Qt.FramelessWindowHint | Qt.Window)
        self.setAttribute(QtCore.Qt.WA_TranslucentBackground, False)
        self.setMinimumSize(1200, 900)
        self.setStyleSheet("background-color: #12121f; border: 1px solid #222244;")

        icon_path = resource_path('res/icon.ico')
        self._title_bar = CustomTitleBar(self, title='ColeFIT  ver. 1.2', icon_path=icon_path)

        # Widgets
        self.btn_select = QPushButton("1. Select data", self)
        self.txt_temp = QLineEdit(self)
        self.txt_temp.setPlaceholderText("-50.0")
        self.btn_process = QPushButton("2. Process data", self)
        self.btn_process.setEnabled(False)
        self.lbl_file_name = QLabel("No file loaded", self)
        self.lbl_file_name.setStyleSheet("color: #00FFCC; font-style: italic; margin-left: 10px;")
        
        self.lbl_peaks = QLabel("No. of peaks:", self)
        self.spin_peaks = QSpinBox(self)
        self.spin_peaks.setRange(1, 3)
        self.spin_peaks.setValue(1)
        self.lbl_peaks.setEnabled(False)
        self.spin_peaks.setEnabled(False)
        
        self.btn_fit = QPushButton("3.1 Make Fit", self)
        self.btn_fit.setEnabled(False)
        self.btn_auto_analysis = QPushButton("3.2 Automatic Analysis", self) # New GA button
        self.btn_auto_analysis.setEnabled(False)
        self.btn_chain_fit = QPushButton("Chain Fit", self) # New Chain Fit button
        self.btn_chain_fit.setEnabled(False)
        self.btn_global_fit = QPushButton("Global Fit", self) # New Global Fit button
        self.btn_global_fit.setEnabled(False)
        self.btn_error_map = QPushButton("Error Map", self)  # Contour error landscape
        self.btn_error_map.setEnabled(False)
        self.btn_error_map.setToolTip("Show contour error landscape (α₁ vs β₁) for the last fit result")
        self.btn_3d = QPushButton("Show 3D", self) # New 3D button
        self.btn_3d.setEnabled(False)
        self.btn_loglog = QPushButton("Show Log-Log", self) # New Log-Log button
        self.btn_loglog.setEnabled(False)
        self.btn_help = QPushButton("Guide", self)
        
        # Terminal Widgets
        self.terminal = QTextEdit(self)
        self.terminal.setReadOnly(True)
        self.terminal.setPlaceholderText("Fitting results and logs will appear here...")
        self.terminal.setMinimumHeight(150)
        self.btn_save_log = QPushButton("Save Log", self)
        self.btn_clear_log = QPushButton("Clear Log", self)
        
        # Plots
        FIG_BG  = '#1a1a2e'
        AXES_BG = '#0d0d1a'

        self.fig1 = plt.Figure(figsize=(5, 5), constrained_layout=True, facecolor=FIG_BG)
        self.canvas1 = FigureCanvas(self.fig1)
        self.canvas1.setStyleSheet("background-color: #1a1a2e;")
        self.ax1 = self.fig1.add_subplot(111, facecolor=AXES_BG)

        self.fig2 = plt.Figure(figsize=(5, 5), constrained_layout=True, facecolor=FIG_BG)
        self.canvas2 = FigureCanvas(self.fig2)
        self.canvas2.setStyleSheet("background-color: #1a1a2e;")
        self.ax2 = self.fig2.add_subplot(111, facecolor=AXES_BG)

        self.fig3 = plt.Figure(figsize=(5, 5), constrained_layout=True, facecolor=FIG_BG)
        self.canvas3 = FigureCanvas(self.fig3)
        self.canvas3.setStyleSheet("background-color: #1a1a2e;")
        self.ax3 = self.fig3.add_subplot(111, facecolor=AXES_BG)

        self.toolbar1 = NavigationToolbar(self.canvas1, self)
        self.toolbar2 = NavigationToolbar(self.canvas2, self)
        self.toolbar3 = NavigationToolbar(self.canvas3, self)

        # --- 0. MAIN CONTAINER ---
        main_layout = QVBoxLayout()
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)

        # Custom title bar is always the very first row
        main_layout.addWidget(self._title_bar)

        # Inner content widget (margins restored inside)
        self._content = QWidget(self)
        self._content.setStyleSheet("background-color: #12121f;")
        content_layout = QVBoxLayout(self._content)
        content_layout.setContentsMargins(8, 6, 8, 6)
        content_layout.setSpacing(4)
        main_layout = content_layout   # alias – rest of init_ui fills this

        # --- 1. TOP CONTROL BAR ---
        control_layout = QHBoxLayout()

        # Group A: Data and processing
        control_layout.addWidget(self.btn_select)
        control_layout.addWidget(self.txt_temp)
        control_layout.addWidget(self.btn_process)
        control_layout.addWidget(self.lbl_file_name)

        control_layout.addSpacing(20) # Visual separator between logical groups
        control_layout.addSpacing(20)

        # Push preceding items to the left
        control_layout.addStretch()

        # Help button pinned to the far right
        control_layout.addWidget(self.btn_help)

        # Add control bar to the main layout
        main_layout.addLayout(control_layout)

        # --- 1.1 TOP FUNCTION BAR ---
        function_layout = QHBoxLayout()

        # Group B: Parameters and analysis
        function_layout.addWidget(self.lbl_peaks)
        function_layout.addWidget(self.spin_peaks)
        function_layout.addWidget(self.btn_fit)
        function_layout.addWidget(self.btn_auto_analysis)
        function_layout.addWidget(self.btn_3d)
        function_layout.addWidget(self.btn_loglog)
        #function_layout.addWidget(self.btn_undo)
        function_layout.addWidget(self.btn_global_fit)
        function_layout.addWidget(self.btn_chain_fit)
        function_layout.addWidget(self.btn_error_map)

        function_layout.addStretch()

        main_layout.addLayout(function_layout)
        
        # --- 2. PLOT AREA ---
        graph_layout = QGridLayout()

        # Canvas 1 (top-left)
        vbox_canvas1 = QVBoxLayout()
        vbox_canvas1.addWidget(self.toolbar1)
        vbox_canvas1.addWidget(self.canvas1)
        graph_layout.addLayout(vbox_canvas1, 0, 0)

        # Canvas 2 (top-right)
        vbox_canvas2 = QVBoxLayout()
        vbox_canvas2.addWidget(self.toolbar2)
        vbox_canvas2.addWidget(self.canvas2)
        graph_layout.addLayout(vbox_canvas2, 0, 1)

        # Canvas 3 (bottom, full width)
        vbox_canvas3 = QVBoxLayout()
        vbox_canvas3.addWidget(self.toolbar3)
        vbox_canvas3.addWidget(self.canvas3)
        # Placed at (row 1, col 0) spanning 1 row and 2 columns
        graph_layout.addLayout(vbox_canvas3, 1, 0, 1, 2)

        # Equal stretch for all plots
        graph_layout.setRowStretch(0, 1)
        graph_layout.setRowStretch(1, 1)
        graph_layout.setColumnStretch(0, 1)
        graph_layout.setColumnStretch(1, 1)

        # Add plot area to main layout
        main_layout.addLayout(graph_layout)

        # --- 3. TERMINAL (Results Area) ---
        terminal_section = QVBoxLayout()
        terminal_label = QLabel("Analysis Results Terminal:", self)
        terminal_label.setStyleSheet("font-weight: bold; color: #00FFCC;")
        terminal_section.addWidget(terminal_label)
        terminal_section.addWidget(self.terminal)

        terminal_btns = QHBoxLayout()
        terminal_btns.addWidget(self.btn_save_log)
        terminal_btns.addWidget(self.btn_clear_log)
        terminal_btns.addStretch()
        terminal_section.addLayout(terminal_btns)

        main_layout.addLayout(terminal_section)

        # --- 4. APLIKACE LAYOUTU ---
        self._content.setLayout(content_layout)

        # Size grip (bottom-right) for frameless resizing
        grip = QSizeGrip(self)
        grip.setFixedSize(14, 14)

        # Outer wrapper that holds titlebar + content + grip row
        grip_row = QHBoxLayout()
        grip_row.setContentsMargins(0, 0, 0, 0)
        grip_row.addStretch()
        grip_row.addWidget(grip)

        outer_layout = QVBoxLayout(self)
        outer_layout.setContentsMargins(0, 0, 0, 0)
        outer_layout.setSpacing(0)
        outer_layout.addWidget(self._title_bar)
        outer_layout.addWidget(self._content, 1)
        outer_layout.addLayout(grip_row)
        self.setLayout(outer_layout)

        self._setup_axes()

    def _apply_dark_ax(self, ax, title=None):
        """Aplikuje dark mode styl na libovolnou matplotlib osu."""
        ax.set_facecolor('#0d0d1a')
        ax.tick_params(colors='white', labelsize=8)
        ax.xaxis.label.set_color('white')
        ax.yaxis.label.set_color('white')
        if title:
            ax.set_title(title, color='#aaaacc', fontsize=9)
        else:
            ax.title.set_color('#aaaacc')
        ax.grid(True, linestyle='--', alpha=0.35, color='#333355')
        for spine in ax.spines.values():
            spine.set_edgecolor('#333355')

    def _setup_axes(self):
        self.ax1.set_facecolor('#0d0d1a')
        self.ax2.set_facecolor('#0d0d1a')
        self.ax3.set_facecolor('#0d0d1a')

        self.ax1.set_xlabel('Frequency [Hz]', color='white')
        self.ax1.set_ylabel("ε'' (Imaginary)", color='white')
        self.ax1.tick_params(colors='white')
        self.ax1.grid(True, linestyle='--', alpha=0.35, color='#333355')
        self.ax1.set_title("Click to select range", fontsize=9, color='#aaaacc')
        for spine in self.ax1.spines.values():
            spine.set_edgecolor('#333355')

        self.ax2.set_xlabel('Frequency [Hz]', color='white')
        self.ax2.set_ylabel("ε' (Real)", color='white')
        self.ax2.tick_params(colors='white')
        self.ax2.grid(True, linestyle='--', alpha=0.35, color='#333355')
        for spine in self.ax2.spines.values():
            spine.set_edgecolor('#333355')

        self.ax3.set_xlabel("ε' (Real)", color='white')
        self.ax3.set_ylabel("ε'' (Imaginary)", color='white')
        self.ax3.tick_params(colors='white')
        self.ax3.set_title("Cole-Cole Plot (Click to Select Range)", color='#aaaacc')
        self.ax3.grid(True, linestyle='--', alpha=0.35, color='#333355')
        for spine in self.ax3.spines.values():
            spine.set_edgecolor('#333355')

    def plot_data(self, freq, real, imag, temp):
        self.ax1.clear()
        self.ax2.clear()
        self.ax3.clear()
        self._setup_axes()

        # Cyan for better visibility on dark background
        self.ax1.semilogx(freq, imag, 'o', color='#00FFFF', markersize=4, label=f"Data T={temp}")
        self.ax2.semilogx(freq, real, 'o', color='#00FFFF', markersize=4)
        self.ax3.plot(real, imag, 'o', color='#00FFFF', markersize=4)
        
        # Cursor only on ax1 for now (could extend to ax3)
        self._add_cursors()
        
        self.canvas1.draw()
        self.canvas2.draw()
        self.canvas3.draw()

    def highlight_selection(self, freq, real, imag, temp, dlimit, hlimit):
        """Highlights selected range in blue, others in gray."""
        self.ax1.clear()
        self.ax2.clear()
        self.ax3.clear()
        self._setup_axes()
        
        # Create masks
        if hlimit is None:
            # First click: assume it's the lower limit (High Freq on Cole-Cole), highlight everything to the right (Low Freqs)
            mask = (freq <= dlimit)
        else:
            # Two clicks: highlight range
            mask = (freq >= dlimit) & (freq <= hlimit)
            
        inv_mask = ~mask
        
        # Inactive points – dark grey
        if np.any(inv_mask):
            self.ax1.semilogx(freq[inv_mask], imag[inv_mask], 'o', color='#444466', markersize=4)
            self.ax2.semilogx(freq[inv_mask], real[inv_mask], 'o', color='#444466', markersize=4)
            self.ax3.plot(real[inv_mask], imag[inv_mask], 'o', color='#444466', markersize=4)

        # Selected points – cyan
        if np.any(mask):
            self.ax1.semilogx(freq[mask], imag[mask], 'o', color='#00FFFF', markersize=4, label=f"Selected T={temp}")
            self.ax2.semilogx(freq[mask], real[mask], 'o', color='#00FFFF', markersize=4)
            self.ax3.plot(real[mask], imag[mask], 'o', color='#00FFFF', markersize=4)
            
        self._add_cursors()
        
        self.canvas1.draw()
        self.canvas2.draw()
        self.canvas3.draw()

    def _add_cursors(self):
        # Vertical cursor for Frequency vs Imag (ax1)
        self.cursor1 = Cursor(self.ax1, horizOn=False, vertOn=True, color='red', linewidth=1, useblit=True)
        # Crosshair cursor for Cole-Cole (ax3)
        self.cursor3 = Cursor(self.ax3, horizOn=True, vertOn=True, color='red', linewidth=1, useblit=True)

    def plot_fit(self, freq, fitted_real, fitted_imag, params, components=None):
        """
        Plots the total fit and optionally the individual decomposed components.
        """
        color = next(self.fit_colors)
        
        l1, = self.ax1.semilogx(freq, fitted_imag, '-', color=color, linewidth=2, label='Total Fit')
        l2, = self.ax2.semilogx(freq, fitted_real, '-', color=color, linewidth=2, label='Total Fit')
        l3, = self.ax3.plot(fitted_real, fitted_imag, '-', color=color, linewidth=2, label='Total Fit')
        
        # Draw components into the imaginary axis – neon colours visible on dark background
        comp_lines = []
        if components:
            comp_colors = cycle(['#00FF88', '#FFAA00', '#AA44FF', '#FF6600', '#44FFFF', '#FF88CC'])
            for name, comp_real, comp_imag in components:
                c = next(comp_colors)
                # Draw only in ax1 (Eps'') as a dashed line
                lc, = self.ax1.semilogx(freq, comp_imag, '--', color=c, linewidth=1.5, label=name)
                comp_lines.append(lc)

        _leg_kw = dict(facecolor='#1a1a2e', labelcolor='white', edgecolor='#333355', framealpha=0.85)
        self.ax1.legend(loc='upper left', **_leg_kw)
        self.ax2.legend(loc='upper left', **_leg_kw)
        self.ax3.legend(loc='upper right', **_leg_kw)
        
        self.canvas1.draw()
        self.canvas2.draw()
        self.canvas3.draw()
        
        # Expose fit and component lines for Undo
        return ([l1, l2, l3] + comp_lines, color)

    def remove_lines(self, lines):
        for line in lines:
            try:
                line.remove()
            except ValueError:
                pass
        self.canvas1.draw()
        self.canvas2.draw()
        self.canvas3.draw()

    def show_message(self, title, message, icon=QMessageBox.Information):
        msg = QMessageBox(self)
        msg.setWindowTitle(title)
        msg.setText(message)
        msg.setIcon(icon)
        msg.exec_()

    def show_params(self, text):
        # Keep the message box for immediate attention if desired, 
        # but also write to terminal
        self.write_to_terminal(text)
        
        msg = QMessageBox(self)
        msg.setWindowTitle("Fit Results")
        msg.setText(text)
        msg.setTextInteractionFlags(QtCore.Qt.TextSelectableByMouse)
        msg.exec_()

    def write_to_terminal(self, text):
        import datetime
        timestamp = datetime.datetime.now().strftime("%H:%M:%S")
        safe_text = text.replace('\n', '<br/>')
        self.terminal.append(f"<b>[{timestamp}]</b><br/>{safe_text}<br/>" + "-"*40)
        # Scroll to bottom
        self.terminal.moveCursor(QtGui.QTextCursor.End)

    def clear_terminal(self):
        self.terminal.clear()

    def get_terminal_text(self):
        return self.terminal.toPlainText()

    # ---------------------------------------------------------------------- #
    #  Helper: create a frameless sub-window with custom title bar + grip     #
    # ---------------------------------------------------------------------- #
    def _make_sub_window(self, title: str, width: int, height: int,
                         allow_maximize: bool = True):
        """
        Create a frameless QWidget sub-window that matches the app dark theme.

        Returns:
            (win, inner_layout)  – caller adds its widgets to inner_layout;
                                   win.setLayout() is already called internally.
        """
        win = QWidget()
        win.setWindowFlags(Qt.FramelessWindowHint | Qt.Window)
        win.resize(width, height)
        win.setStyleSheet(
            "background-color: #1a1a2e; border: 1px solid #333355;"
        )

        tb = CustomTitleBar(win, title=title)
        if not allow_maximize:
            tb.hide_max_button()

        # Content area
        content = QWidget(win)
        content.setStyleSheet("background-color: #1a1a2e;")
        inner = QVBoxLayout(content)
        inner.setContentsMargins(4, 4, 4, 4)
        inner.setSpacing(4)

        # Resize grip (bottom-right)
        grip = QSizeGrip(win)
        grip.setFixedSize(14, 14)
        grip_row = QHBoxLayout()
        grip_row.setContentsMargins(0, 0, 0, 0)
        grip_row.addStretch()
        grip_row.addWidget(grip)

        outer = QVBoxLayout(win)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)
        outer.addWidget(tb)
        outer.addWidget(content, 1)
        outer.addLayout(grip_row)
        win.setLayout(outer)

        return win, inner

    def plot_3d(self, data):
        """Plots 3D graphs for Real, Imaginary, and Tan Delta."""
        freqs = data[:, 0]
        temps = data[:, 1]
        reals = data[:, 2]
        imags = data[:, 3]

        with np.errstate(divide='ignore', invalid='ignore'):
            tan_delta = imags / reals
            tan_delta = np.nan_to_num(tan_delta)

        self.win3d, layout = self._make_sub_window(
            "3D Dielectric Landscape Analysis", 1450, 600
        )

        fig = plt.Figure(figsize=(14, 6), facecolor='#1a1a2e')
        canvas = FigureCanvas(fig)
        canvas.setStyleSheet("background-color: #1a1a2e;")
        toolbar = NavigationToolbar(canvas, self.win3d)

        log_freqs = np.log10(freqs)

        # Shared colour scale for all 3 subplots
        CMAP = 'turbo'
        all_z = np.concatenate([reals, imags, tan_delta])
        G_VMIN = float(np.nanmin(all_z))
        G_VMAX = float(np.nanmax(all_z))
        norm_shared = plt.Normalize(vmin=G_VMIN, vmax=G_VMAX)

        def create_subplot(pos, z_data, z_label, title):
            ax = fig.add_subplot(pos, projection='3d')
            ax.set_facecolor('#0d0d1a')
            ax.tick_params(colors='white', labelsize=7)
            ax.xaxis.label.set_color('white')
            ax.yaxis.label.set_color('white')
            ax.zaxis.label.set_color('white')
            ax.title.set_color('white')
            for pane in (ax.xaxis.pane, ax.yaxis.pane, ax.zaxis.pane):
                pane.fill = False
                pane.set_edgecolor('#333355')
            ax.scatter(log_freqs, temps, z_data, c=z_data, cmap=CMAP,
                       norm=norm_shared, marker='o', s=6)
            ax.set_xlabel("log\u2081\u2080(f) [Hz]", labelpad=12)
            ax.set_ylabel("Temp [\u00b0C]",          labelpad=12)
            ax.set_zlabel(z_label,                   labelpad=10)
            ax.set_title(title)
            return ax

        ax_r  = create_subplot(131, reals,     "\u03b5' (Real)",  "Real permittivity")
        ax_i  = create_subplot(132, imags,     "\u03b5'' (Imag)", "Imag permittivity")
        ax_td = create_subplot(133, tan_delta, "tan(\u03b4)",     "Loss tangent")

        # Single shared colorbar to the right of the third subplot
        sm = plt.cm.ScalarMappable(cmap=CMAP, norm=norm_shared)
        sm.set_array([])
        cb = fig.colorbar(sm, ax=[ax_r, ax_i, ax_td], shrink=0.6, aspect=20, pad=0.04)
        cb.ax.yaxis.set_tick_params(color='white')
        cb.outline.set_edgecolor('white')
        plt.setp(cb.ax.yaxis.get_ticklabels(), color='white')
        cb.set_label('Value (shared scale)', color='white')

        fig.suptitle("3D Dielectric Landscape", color='white', fontsize=11, y=0.98)
        # tight_layout() is incompatible with 3D axes – use explicit margins instead
        fig.subplots_adjust(left=0.04, right=0.88, bottom=0.08, top=0.93, wspace=0.35)

        layout.addWidget(toolbar)
        layout.addWidget(canvas)
        self.win3d.show()

    def plot_global_fit_3d(self, data, fit_result, n_peaks):
        """
        Displays a 3D window comparing measured data against the global 3D model.

        Args:
            data:       numpy array (N×4) – [Freq, Temp_C, Eps', Eps'']
            fit_result: lmfit MinimizerResult returned by run_global_fit()
            n_peaks:    number of relaxation processes
        """
        from .model import BDSModel

        freqs   = data[:, 0]
        temps_C = data[:, 1]
        temps_K = temps_C + 273.15
        data_real = data[:, 2]
        data_imag = data[:, 3]

        # ---- Compute model values for every data point ----
        omega = BDSModel.calc_omega(freqs)
        eps_model = BDSModel.global_eps_total(omega, temps_K, fit_result.params, n_peaks)
        model_real = np.real(eps_model)
        model_imag = -np.imag(eps_model)

        # Safe tan δ (guard against division by zero)
        with np.errstate(divide='ignore', invalid='ignore'):
            data_tand  = np.where(np.abs(data_real)  > 1e-12, data_imag  / data_real,  0.0)
            model_tand = np.where(np.abs(model_real) > 1e-12, model_imag / model_real, 0.0)

        log_freqs = np.log10(freqs)

        # ---- Log10 Z-axes ----
        def safe_log10(arr):
            with np.errstate(divide='ignore', invalid='ignore'):
                return np.where(arr > 0, np.log10(arr), np.nan)

        log_data_real  = safe_log10(data_real)
        log_model_real = safe_log10(model_real)
        log_data_imag  = safe_log10(data_imag)
        log_model_imag = safe_log10(model_imag)
        log_data_tand  = safe_log10(np.abs(data_tand))
        log_model_tand = safe_log10(np.abs(model_tand))

        # ====== WINDOW 1: 3D comparison ======
        self.win_global_3d, layout = self._make_sub_window(
            "Global 3D Fit – Model vs Data", 1550, 650
        )

        fig = plt.Figure(figsize=(15, 6), facecolor='#1a1a2e')
        canvas = FigureCanvas(fig)
        toolbar = NavigationToolbar(canvas, self.win_global_3d)

        # Export Button
        btn_export = QPushButton("Export Data (CSV)", self.win_global_3d)
        btn_export.setFixedWidth(200)
        
        def save_global_csv():
            import pandas as pd
            try:
                df = pd.DataFrame({
                    'Frequency_Hz': freqs,
                    'Temperature_C': temps_C,
                    'Data_Eps_Real': data_real,
                    'Data_Eps_Imag': data_imag,
                    'Model_Eps_Real': model_real,
                    'Model_Eps_Imag': model_imag,
                    'Data_TanDelta': data_tand,
                    'Model_TanDelta': model_tand
                })
                path, _ = QFileDialog.getSaveFileName(self.win_global_3d, "Export Global Fit Data", "", "CSV Files (*.csv)")
                if path:
                    df.to_csv(path, index=False)
                    self.show_message("Exported", f"Data saved to {path}")
            except Exception as e:
                self.show_message("Export Error", str(e), QMessageBox.Critical)

        btn_export.clicked.connect(save_global_csv)

        # Data: bright fixed colours;  Model: high-contrast colormaps (light starts – won't blend into dark bg)
        DATA_COLORS  = ['#00FFFF', '#FFFF00', '#00FF88']   # cyan / yellow / lime
        MODEL_CMAPS  = ['hot',     'turbo',   'cool']       # bright maps without dark edges

        def make_ax(pos, z_data, z_model, z_label, title, data_color, model_cmap):
            ax = fig.add_subplot(pos, projection='3d')
            ax.set_facecolor('#0d0d1a')
            ax.tick_params(colors='white', labelsize=7)
            ax.xaxis.label.set_color('white')
            ax.yaxis.label.set_color('white')
            ax.zaxis.label.set_color('white')
            ax.title.set_color('white')
            for pane in (ax.xaxis.pane, ax.yaxis.pane, ax.zaxis.pane):
                pane.fill = False
                pane.set_edgecolor('#333355')

            # --- Data: large bright points with fixed distinct color ---
            valid = np.isfinite(z_data)
            ax.scatter(
                log_freqs[valid], temps_C[valid], z_data[valid],
                color=data_color, edgecolors='white', linewidths=0.2,
                marker='o', s=14, alpha=0.90, zorder=5, label='Data'
            )

            # --- Model: colored surface ---
            unique_logf = np.sort(np.unique(np.round(log_freqs, 2)))
            unique_temp = np.sort(np.unique(np.round(temps_C, 1)))

            if len(unique_logf) > 1 and len(unique_temp) > 1:
                LF, TC = np.meshgrid(unique_logf, unique_temp)
                ZM = np.full_like(LF, np.nan)
                for ri, t in enumerate(unique_temp):
                    for ci, lf in enumerate(unique_logf):
                        dist = np.abs(log_freqs - lf) + np.abs(temps_C - t)
                        idx  = np.argmin(dist)
                        ZM[ri, ci] = z_model[idx]

                ax.plot_surface(
                    LF, TC, ZM,
                    cmap=model_cmap, alpha=0.55,
                    linewidth=0.0, antialiased=True, shade=True
                )
            else:
                valid_m = np.isfinite(z_model)
                ax.scatter(log_freqs[valid_m], temps_C[valid_m], z_model[valid_m],
                           color='#FF4444', marker='^', s=10, alpha=0.7)

            ax.set_xlabel("log₁₀(f) [Hz]", fontsize=8, labelpad=12)
            ax.set_ylabel("T [°C]",         fontsize=8, labelpad=12)
            ax.set_zlabel(z_label,           fontsize=8, labelpad=10)
            ax.set_title(title, fontsize=9, pad=6)
            return ax

        make_ax(131, log_data_real,  log_model_real,  "log₁₀(ε')",    "Real permittivity",
                DATA_COLORS[0], MODEL_CMAPS[0])
        make_ax(132, log_data_imag,  log_model_imag,  "log₁₀(ε'')",   "Imag permittivity",
                DATA_COLORS[1], MODEL_CMAPS[1])
        make_ax(133, log_data_tand,  log_model_tand,  "log₁₀(tan δ)", "Loss tangent",
                DATA_COLORS[2], MODEL_CMAPS[2])

        from matplotlib.lines import Line2D
        legend_elements = [
            Line2D([0], [0], marker='o', color='w', markerfacecolor='#00FFFF', markersize=7, label='Data'),
            Line2D([0], [0], marker='s', color='w', markerfacecolor='#FF6600', markersize=7, label='Model'),
        ]
        fig.legend(handles=legend_elements, loc='upper center', ncol=2, fontsize=9,
                   framealpha=0.8, facecolor='#1a1a2e', labelcolor='white',
                   edgecolor='#555577')

        fig.suptitle(
            f"Global 3D Fit  |  red\u03c7\u00b2 = {fit_result.redchi:.3e}  |  {n_peaks} peak(s)",
            fontsize=10, color='white', y=0.98
        )
        # tight_layout() is incompatible with 3D axes – use explicit margins instead
        fig.subplots_adjust(left=0.04, right=0.96, bottom=0.08, top=0.92, wspace=0.40)
        
        top_bar = QHBoxLayout()
        top_bar.addWidget(toolbar)
        top_bar.addStretch()
        top_bar.addWidget(btn_export)
        
        layout.addLayout(top_bar)
        layout.addWidget(canvas)
        self.win_global_3d.show()

        # ====== WINDOW 2: Model vs Data Deviation per Temperature ======
        self._plot_deviation_per_temp(
            temps_C, data_real, model_real, data_imag, model_imag,
            data_tand, model_tand, fit_result.redchi
        )

    def _plot_deviation_per_temp(self, temps_C,
                                  data_real, model_real,
                                  data_imag, model_imag,
                                  data_tand, model_tand,
                                  redchi):
        """
        Displays a window with the mean relative deviation of the model from the data (in %)
        for each temperature separately — for ε', ε'', and tan δ.
        """
        unique_temps = np.sort(np.unique(np.round(temps_C, 1)))

        rel_err_real = []
        rel_err_imag = []
        rel_err_tand = []

        def mean_rel_err(data_arr, model_arr, mask):
            d = data_arr[mask]
            m = model_arr[mask]
            valid = np.abs(d) > 1e-12
            if not np.any(valid):
                return np.nan
            return 100.0 * np.mean(np.abs((d[valid] - m[valid]) / d[valid]))

        for t in unique_temps:
            mask = np.abs(temps_C - t) < 0.15
            rel_err_real.append(mean_rel_err(data_real,  model_real,  mask))
            rel_err_imag.append(mean_rel_err(data_imag,  model_imag,  mask))
            rel_err_tand.append(mean_rel_err(data_tand,  model_tand,  mask))

        rel_err_real = np.array(rel_err_real)
        rel_err_imag = np.array(rel_err_imag)
        rel_err_tand = np.array(rel_err_tand)

        # --- Window ---
        self.win_dev, layout2 = self._make_sub_window(
            "Global Fit – Deviation per Temperature", 900, 500
        )

        fig2 = plt.Figure(figsize=(9, 5), facecolor='#1a1a2e')
        canvas2 = FigureCanvas(fig2)
        toolbar2 = NavigationToolbar(canvas2, self.win_dev)

        # Export Button
        btn_export = QPushButton("Export Deviation (CSV)", self.win_dev)
        btn_export.setFixedWidth(200)

        def save_dev_csv():
            import pandas as pd
            try:
                df = pd.DataFrame({
                    'Temperature_C': unique_temps,
                    'RelErr_EpsReal_Pct': rel_err_real,
                    'RelErr_EpsImag_Pct': rel_err_imag,
                    'RelErr_TanDelta_Pct': rel_err_tand
                })
                path, _ = QFileDialog.getSaveFileName(self.win_dev, "Export Deviation Data", "", "CSV Files (*.csv)")
                if path:
                    df.to_csv(path, index=False)
                    self.show_message("Exported", f"Data saved to {path}")
            except Exception as e:
                self.show_message("Export Error", str(e), QMessageBox.Critical)

        btn_export.clicked.connect(save_dev_csv)

        ax = fig2.add_subplot(111)
        ax.set_facecolor('#0d0d1a')
        ax.tick_params(colors='white', labelsize=9)
        ax.xaxis.label.set_color('white')
        ax.yaxis.label.set_color('white')
        ax.title.set_color('white')
        for spine in ax.spines.values():
            spine.set_edgecolor('#444466')

        ax.plot(unique_temps, rel_err_real, 'o-', color='#00FFFF', linewidth=2,
                markersize=6, label="ε' (Real)")
        ax.plot(unique_temps, rel_err_imag, 's-', color='#FFFF00', linewidth=2,
                markersize=6, label="ε'' (Imag)")
        ax.plot(unique_temps, rel_err_tand, '^-', color='#00FF88', linewidth=2,
                markersize=6, label="tan δ")

        # Red vertical line at temperatures where error > 10 %
        threshold = 10.0
        for i, t in enumerate(unique_temps):
            worst = max(
                rel_err_real[i] if np.isfinite(rel_err_real[i]) else 0,
                rel_err_imag[i] if np.isfinite(rel_err_imag[i]) else 0,
            )
            if worst > threshold:
                ax.axvline(t, color='#FF4444', linewidth=0.8, alpha=0.4)

        ax.axhline(threshold, color='#FF4444', linewidth=1.2, linestyle='--', alpha=0.8,
                   label=f"{threshold:.0f} % threshold")

        ax.set_xlabel("Temperature [°C]", fontsize=10)
        ax.set_ylabel("Mean relative error [%]", fontsize=10)
        ax.set_title(
            f"Model vs Data – deviation per temperature  (redχ² = {redchi:.3e})",
            fontsize=10
        )
        ax.legend(fontsize=9, facecolor='#1a1a2e', labelcolor='white', framealpha=0.6)
        ax.grid(True, linestyle='--', alpha=0.3, color='#555577')

        fig2.tight_layout()

        top_bar = QHBoxLayout()
        top_bar.addWidget(toolbar2)
        top_bar.addStretch()
        top_bar.addWidget(btn_export)

        layout2.addLayout(top_bar)
        layout2.addWidget(canvas2)
        self.win_dev.show()

    def plot_loglog(self, data):
        """Plots Log-Log graphs for Real and Imaginary Permittivity."""
        freqs = data[:, 0]
        temps = data[:, 1]
        reals = data[:, 2]
        imags = data[:, 3]

        self.win_log, layout = self._make_sub_window(
            "Log-Log Analysis", 1100, 600
        )

        # Wider figure – space on the right for colorbar
        fig = plt.Figure(figsize=(11, 5.5), facecolor='#1a1a2e')
        canvas = FigureCanvas(fig)
        canvas.setStyleSheet("background-color: #1a1a2e;")
        toolbar = NavigationToolbar(canvas, self.win_log)

        unique_temps = np.unique(temps)
        cmap = plt.get_cmap('plasma')
        norm = plt.Normalize(vmin=float(unique_temps.min()), vmax=float(unique_temps.max()))

        # GridSpec: 2 plots + 1 narrow axis for colorbar (outside plots)
        from matplotlib.gridspec import GridSpec
        gs = GridSpec(1, 3, figure=fig,
                      width_ratios=[1, 1, 0.05],
                      left=0.07, right=0.93, top=0.90, bottom=0.12,
                      wspace=0.30)

        ax1 = fig.add_subplot(gs[0, 0], facecolor='#0d0d1a')
        ax2 = fig.add_subplot(gs[0, 1], facecolor='#0d0d1a')
        cax = fig.add_subplot(gs[0, 2])   # dedicated axis for colorbar

        for ax, ylabel, title in [
            (ax1, "ε' (Real)",        "Real Permittivity (Log-Log)"),
            (ax2, "ε'' (Imaginary)",  "Imaginary Permittivity (Log-Log)"),
        ]:
            ax.set_xlabel("Frequency [Hz]", color='white')
            ax.set_ylabel(ylabel, color='white')
            ax.set_title(title, color='#aaaacc')
            ax.tick_params(colors='white')
            ax.grid(True, which="both", ls="--", alpha=0.3, color='#333355')
            for spine in ax.spines.values():
                spine.set_edgecolor('#333355')

        for temp in unique_temps:
            mask = (temps == temp)
            f = freqs[mask]
            r = reals[mask]
            i = imags[mask]
            color = cmap(norm(temp))
            sort_idx = np.argsort(f)
            ax1.loglog(f[sort_idx], r[sort_idx], '.-', color=color, linewidth=1, markersize=3)
            ax2.loglog(f[sort_idx], i[sort_idx], '.-', color=color, linewidth=1, markersize=3)

        # Colorbar in dedicated axis – outside plots
        sm = plt.cm.ScalarMappable(cmap=cmap, norm=norm)
        sm.set_array([])
        cb = fig.colorbar(sm, cax=cax)
        cb.set_label('Temperature [°C]', color='white')
        cb.ax.yaxis.set_tick_params(color='white')
        cb.outline.set_edgecolor('#555577')
        plt.setp(cb.ax.yaxis.get_ticklabels(), color='white')

        layout.addWidget(toolbar)
        layout.addWidget(canvas)
        self.win_log.show()


    def plot_deconvoluted_peaks(self, freq, data_real, data_imag, fitted_real, fitted_imag, components):
        """
        Displays deconvoluted peaks and the conductivity component together with original data in a new window.
        """
        self.win_peaks, layout = self._make_sub_window(
            "Deconvoluted Peaks Analysis", 1000, 500
        )

        fig = plt.Figure(figsize=(10, 5), facecolor='#1a1a2e')
        canvas = FigureCanvas(fig)
        canvas.setStyleSheet("background-color: #1a1a2e;")
        toolbar = NavigationToolbar(canvas, self.win_peaks)

        ax1 = fig.add_subplot(121, facecolor='#0d0d1a')
        ax2 = fig.add_subplot(122, facecolor='#0d0d1a')

        for ax in (ax1, ax2):
            ax.tick_params(colors='white')
            ax.grid(True, linestyle='--', alpha=0.3, color='#333355')
            for spine in ax.spines.values():
                spine.set_edgecolor('#333355')

        # Common X-axis (logarithmic frequency)
        ax1.set_xlabel('Frequency [Hz]', color='white')
        ax1.set_ylabel("ε' (Real)", color='white')
        ax1.set_title("Real Permittivity Components", color='#aaaacc')

        ax2.set_xlabel('Frequency [Hz]', color='white')
        ax2.set_ylabel("ε'' (Imaginary)", color='white')
        ax2.set_title("Imaginary Permittivity Components", color='#aaaacc')

        # Plot data – cyan
        ax1.semilogx(freq, data_real, 'o', color='#00FFFF', markersize=4, alpha=0.8, label='Data')
        ax2.semilogx(freq, data_imag, 'o', color='#00FFFF', markersize=4, alpha=0.8, label='Data')

        # Plot total fit – neon red-pink
        ax1.semilogx(freq, fitted_real, '--', color='#FF4488', linewidth=2, label='Total Fit')
        ax2.semilogx(freq, fitted_imag, '--', color='#FF4488', linewidth=2, label='Total Fit')

        # Plot individual components – neon colors
        colors = cycle(['#00FF88', '#FFAA00', '#AA44FF', '#FF6600', '#44FFFF', '#FF88CC'])

        for name, comp_real, comp_imag in components:
            c = next(colors)
            ax1.semilogx(freq, comp_real, '-', color=c, linewidth=1.5, label=name)
            ax2.semilogx(freq, comp_imag, '-', color=c, linewidth=1.5, label=name)

        ax1.legend(loc='best', fontsize='small', facecolor='#1a1a2e', labelcolor='white', framealpha=0.7)
        ax2.legend(loc='best', fontsize='small', facecolor='#1a1a2e', labelcolor='white', framealpha=0.7)

        fig.tight_layout()

        layout.addWidget(toolbar)
        layout.addWidget(canvas)
        self.win_peaks.show()

    def plot_relaxation_map(self, peaks_data, fit_type="Arrhenius"):
        """
        Displays the Relaxation Map (Arrhenius/VFT plot) for all available peaks in a new window.
        peaks_data is a list of dictionaries with data.
        """
        self.win_map, layout = self._make_sub_window(
            f"Relaxation Map – {fit_type}", 900, 600
        )

        fig = plt.Figure(figsize=(9, 6), facecolor='#1a1a2e')
        canvas = FigureCanvas(fig)
        canvas.setStyleSheet("background-color: #1a1a2e;")
        toolbar = NavigationToolbar(canvas, self.win_map)

        ax = fig.add_subplot(111, facecolor='#0d0d1a')
        ax.set_xlabel('1000 / T [K\u207b\u00b9]', color='white')
        ax.set_ylabel('log\u2081\u2080(\u03c4) [s]', color='white')
        ax.set_title('Relaxation Map', color='#aaaacc')
        ax.tick_params(colors='white')
        ax.grid(True, linestyle='--', alpha=0.35, color='#333355')
        for spine in ax.spines.values():
            spine.set_edgecolor('#333355')

        colors = cycle(['#00FFFF', '#00FF88', '#FFAA00'])
        fit_colors = cycle(['#FF4488', '#AA44FF', '#FF6600'])

        for peak in peaks_data:
            c_data = next(colors)
            c_fit = next(fit_colors)

            name = peak['name']
            inv_T_data = peak['inv_T_data']
            log_tau_data = peak['log_tau_data']
            inv_T_fit = peak['inv_T_fit']
            log_tau_fit = peak['log_tau_fit']
            param1 = peak['param1']
            param2 = peak['param2']

            # Body (Data)
            ax.plot(inv_T_data, log_tau_data, 'o', color=c_data, markersize=8, alpha=0.9, label=f'{name} Data')

            # Fitted curve/line
            if fit_type == "Arrhenius":
                label_fit = f"{name} Fit (E_a = {param1:.3f} eV, log(\u03c4\u2080) = {param2:.2f})"
            else:
                label_fit = f"{name} Fit (T\u2080 = {param1:.1f} K, B = {param2:.1f})"

            ax.plot(inv_T_fit, log_tau_fit, '-', color=c_fit, linewidth=2, label=label_fit)

        ax.legend(loc='best', facecolor='#1a1a2e', labelcolor='white', framealpha=0.7)
        fig.tight_layout()

        layout.addWidget(toolbar)
        layout.addWidget(canvas)
        self.win_map.show()

    def plot_error_landscape(
        self,
        X: np.ndarray,
        Y: np.ndarray,
        Z: np.ndarray,
        opt_x: float,
        opt_y: float,
        param_x_name: str = 'alpha_1',
        param_y_name: str = 'beta_1'
    ):
        """
        Plots the contour error landscape map in a new separate matplotlib window.

        Designed for scientific publications: academic style, LaTeX axis descriptions,
        marked global optimum (star), colorbar with chi² label.

        Args:
            X   (ndarray): Parameter X grid (X axis).
            Y   (ndarray): Parameter Y grid (Y axis).
            Z   (ndarray): RSS values grid (error landscape / chi²).
            opt_x (float): Optimal param_x value – marked with a star.
            opt_y (float): Optimal param_y value – marked with a star.
            param_x_name (str): Internal parameter X name (for axis label).
            param_y_name (str): Internal parameter Y name (for axis label).
        """
        # --- Convert internal parameter name to human-readable LaTeX label ---
        def _param_to_label(name: str) -> str:
            label_map = {
                'alpha_1': r'Shape parameter $\alpha_1$',
                'alpha_2': r'Shape parameter $\alpha_2$',
                'alpha_3': r'Shape parameter $\alpha_3$',
                'beta_1':  r'Shape parameter $\beta_1$',
                'beta_2':  r'Shape parameter $\beta_2$',
                'beta_3':  r'Shape parameter $\beta_3$',
                'tau_1':   r'Relaxation time $\tau_1$ [s]',
                'tau_2':   r'Relaxation time $\tau_2$ [s]',
                'tau_3':   r'Relaxation time $\tau_3$ [s]',
                'delta_eps_1': r'Dielectric strength $\Delta\varepsilon_1$',
                'delta_eps_2': r'Dielectric strength $\Delta\varepsilon_2$',
                'delta_eps_3': r'Dielectric strength $\Delta\varepsilon_3$',
                'eps_inf':  r'High-freq. permittivity $\varepsilon_{\infty}$',
                'sigma_dc': r'DC conductivity $\sigma_{\mathrm{DC}}$',
                's':        r'Conductivity exponent $s$',
            }
            return label_map.get(name, name)

        xlabel = _param_to_label(param_x_name)
        ylabel = _param_to_label(param_y_name)

        # ---- Qt Window -------------------------------------------------------- #
        self.win_error_map, layout = self._make_sub_window(
            f"Error Landscape  –  {param_x_name}  vs  {param_y_name}",
            720, 640
        )

        # ---- Matplotlib figure --------------------------------------------- #
        FIG_BG = '#1a1a2e'
        fig = plt.Figure(figsize=(6.8, 5.8), facecolor=FIG_BG)
        canvas = FigureCanvas(fig)
        canvas.setStyleSheet(f"background-color: {FIG_BG};")
        toolbar = NavigationToolbar(canvas, self.win_error_map)

        # Main plot axis + separate axis for colorbar (right)
        ax = fig.add_axes([0.12, 0.11, 0.70, 0.78])
        ax.set_facecolor('#0d0d1a')

        # ---- Contour Map (gradient fill) ----------------------------- #
        Z_finite = Z[np.isfinite(Z)]
        if Z_finite.size == 0:
            # Fallback: if all RSS are NaN, show a warning
            ax.text(0.5, 0.5, 'No valid data (all NaN)',
                    ha='center', va='center', color='#FF4444',
                    transform=ax.transAxes, fontsize=12)
        else:
            # Robust scaling: percentiles ignore extreme outliers
            vmin = float(np.percentile(Z_finite, 2))
            vmax = float(np.percentile(Z_finite, 98))

            cf = ax.contourf(
                X, Y, Z,
                levels=50,
                cmap='viridis',
                vmin=vmin,
                vmax=vmax
            )

            # Fine contour lines for orientation (without numerical labels)
            ax.contour(
                X, Y, Z,
                levels=10,
                colors='white',
                linewidths=0.35,
                alpha=0.25
            )

            # Colorbar in a dedicated axis to the right of the plot
            cbar_ax = fig.add_axes([0.85, 0.11, 0.03, 0.78])
            cb = fig.colorbar(cf, cax=cbar_ax)
            cb.set_label(
                r'Residual Sum of Squares ($\chi^2$)',
                color='white', fontsize=10, labelpad=8
            )
            cb.ax.yaxis.set_tick_params(color='white', labelsize=8)
            cb.outline.set_edgecolor('#555577')
            plt.setp(cb.ax.yaxis.get_ticklabels(), color='white')

        # ---- Mark the global optimum with a white star ------------------- #
        ax.plot(
            opt_x, opt_y,
            marker='*',
            color='white',
            markersize=18,
            markeredgecolor='#FF4444',
            markeredgewidth=1.2,
            zorder=10,
            linestyle='None',
            label=(
                f'Global optimum\n'
                f'{param_x_name} = {opt_x:.4f}\n'
                f'{param_y_name} = {opt_y:.4f}'
            )
        )

        # ---- Axis labels (academic style, 11 pt) --------------------------- #
        ax.set_xlabel(xlabel, color='white', fontsize=11)
        ax.set_ylabel(ylabel, color='white', fontsize=11)
        ax.set_title(
            f'Error Landscape: {param_x_name} vs {param_y_name}',
            color='#ccccee', fontsize=12, pad=10
        )
        ax.tick_params(colors='white', labelsize=9)
        for spine in ax.spines.values():
            spine.set_edgecolor('#555577')

        # Legend with optimum values
        ax.legend(
            loc='upper right',
            fontsize=9,
            facecolor='#1a1a2e',
            labelcolor='white',
            edgecolor='#555577',
            framealpha=0.85
        )

        # ---- Export button (300 dpi PNG, for scientific publication) --------- #
        btn_export_png = QPushButton("Export PNG (300 dpi)", self.win_error_map)
        btn_export_png.setFixedWidth(200)
        btn_export_png.setStyleSheet(
            "background-color: #2a2a4e; color: white; border: 1px solid #555577;"
        )

        def _save_png():
            path, _ = QFileDialog.getSaveFileName(
                self.win_error_map,
                "Export Error Landscape",
                f"error_landscape_{param_x_name}_vs_{param_y_name}.png",
                "PNG Images (*.png);;All Files (*)"
            )
            if path:
                try:
                    fig.savefig(path, dpi=300, facecolor=FIG_BG, bbox_inches='tight')
                    self.show_message("Exported", f"Error landscape saved to:\n{path}")
                except Exception as e:
                    self.show_message("Export Error", str(e), QMessageBox.Critical)

        btn_export_png.clicked.connect(_save_png)

        # ---- Layout Assembly --------------------------------------------- #
        top_bar = QHBoxLayout()
        top_bar.addWidget(toolbar)
        top_bar.addStretch()
        top_bar.addWidget(btn_export_png)

        layout.addLayout(top_bar)
        layout.addWidget(canvas)
        self.win_error_map.show()
