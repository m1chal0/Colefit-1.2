import os
import numpy as np
from PyQt5.QtWidgets import QFileDialog, QMessageBox, QApplication, QProgressDialog, QInputDialog
from PyQt5.QtCore import QThread, pyqtSignal, Qt
from .view import HelpWindow

class Worker(QThread):
    finished = pyqtSignal(bool, object)
    error = pyqtSignal(str)

    def __init__(self, model, dlimit=None, hlimit=None):
        super().__init__()
        self.model = model
        self.dlimit = dlimit
        self.hlimit = hlimit

    def run(self):
        try:
            result = self.model.auto_fit(3, self.dlimit, self.hlimit)
            if result is not None and result.success:
                self.finished.emit(True, result)
            else:
                self.finished.emit(False, "Fit failed")
        except Exception as e:
            self.error.emit(str(e))

class ChainFitWorker(QThread):
    progress = pyqtSignal(int, int, float) # idx, total, temp
    finished = pyqtSignal(bool, object) # success, DataFrame/error
    
    def __init__(self, model, max_peaks, dlimit=None, hlimit=None):
        super().__init__()
        self.model = model
        self.max_peaks = max_peaks
        self.dlimit = dlimit
        self.hlimit = hlimit
        
    def run(self):
        try:
            df_results = self.model.chain_fit(
                self.max_peaks, 
                self.dlimit, 
                self.hlimit, 
                progress_callback=self._emit_progress
            )
            self.finished.emit(True, df_results)
        except Exception as e:
            self.finished.emit(False, str(e))
            
    def _emit_progress(self, idx, total, temp):
        self.progress.emit(idx, total, temp)

class ColeController:
    def __init__(self, model, view):
        self.model = model
        self.view = view
        self.help_window = None
        self.dlimit = None
        self.hlimit = None
        self.rect_dlimit = None
        self.rect_hlimit = None
        self.worker = None
        self.progress_dialog = None
        
        self.connect_signals()
        
    def connect_signals(self):
        self.view.btn_select.clicked.connect(self.select_file)
        self.view.btn_process.clicked.connect(self.process_data)
        self.view.btn_fit.clicked.connect(self.make_fit)
        self.view.btn_auto_analysis.clicked.connect(self.auto_analysis)
        self.view.btn_chain_fit.clicked.connect(self.chain_fit)
        self.view.btn_global_fit.clicked.connect(self.global_fit)
        self.view.btn_3d.clicked.connect(self.show_3d)
        self.view.btn_loglog.clicked.connect(self.show_loglog)
        self.view.btn_help.clicked.connect(self.show_help)
        self.view.btn_save_log.clicked.connect(self.save_log)
        self.view.btn_clear_log.clicked.connect(self.clear_log)
        self.view.btn_error_map.clicked.connect(self.show_error_map)
        
        self.view.canvas1.mpl_connect('button_press_event', self.on_graph_click)
        self.view.canvas3.mpl_connect('button_press_event', self.on_graph_click)

    def select_file(self):
        options = QFileDialog.Options()
        file_path, _ = QFileDialog.getOpenFileName(self.view, "Choose data file", "", 
                                                 "Data Files (*.txt *.csv);;All Files (*)", options=options)
        if file_path:
            self.model.file_path = file_path
            self.view.btn_process.setEnabled(True)
            self.view.lbl_file_name.setText(os.path.basename(file_path))
            # Reset
            self.model.frequency = np.array([])
            self.view.ax1.clear()
            self.view.ax2.clear()
            self.view.ax3.clear()
            self.view._setup_axes()
            self.view.canvas1.draw()
            self.view.canvas2.draw()
            self.view.canvas3.draw()
            self.view.btn_fit.setEnabled(False)
            self.view.spin_peaks.setEnabled(False)
            self.view.lbl_peaks.setEnabled(False)
            self.view.btn_auto_analysis.setEnabled(False)
            #self.view.btn_chain_fit.setEnabled(False)
            #self.view.btn_global_fit.setEnabled(False)
            #self.view.btn_undo.setEnabled(False)
            #self.view.btn_save.setEnabled(False)

    def process_data(self):
        temp_text = self.view.txt_temp.text().strip()
        try:
            temp = float(temp_text) if temp_text else -50.0
        except ValueError:
            self.view.show_message("Input Error", "Invalid temperature format.")
            return

        success = self.model.load_data(self.model.file_path, temp)
        if success:
            self.view.plot_data(self.model.frequency, self.model.real_part, self.model.imag_part, temp)
            self.view.btn_fit.setEnabled(True)
            self.view.spin_peaks.setEnabled(True)
            self.view.lbl_peaks.setEnabled(True)
            self.view.btn_auto_analysis.setEnabled(True)
            self.view.btn_chain_fit.setEnabled(True)
            self.view.btn_global_fit.setEnabled(True)
            self.view.btn_3d.setEnabled(True)
            self.view.btn_loglog.setEnabled(True)
            self.dlimit = None
            self.hlimit = None
        else:
            self.view.show_message("Error", "Failed to load data.", QMessageBox.Critical)

    def on_graph_click(self, event):
        if len(self.model.frequency) == 0: return
        if event.button != 1: return

        limit_value = None
        
        # Handle click on Cole-Cole (ax3)
        if event.inaxes == self.view.ax3:
            clicked_real = event.xdata
            clicked_imag = event.ydata
            # Find nearest point in 2D space (Real, Imag)
            # Normalize to avoid scaling issues? Ideally yes, but simple Euclidean usually works locally
            dist = np.sqrt((self.model.real_part - clicked_real)**2 + (self.model.imag_part - clicked_imag)**2)
            idx = dist.argmin()
            limit_value = self.model.frequency[idx]
            
        if limit_value is None: return

        # Selection Logic
        if self.dlimit is not None and self.hlimit is not None:
            # Reset selection
            self.dlimit = None
            self.hlimit = None
            self.view.plot_data(self.model.frequency, self.model.real_part, self.model.imag_part, self.model.temperature)
            self.view.btn_fit.setEnabled(True) # Allow full range fit
            self.view.spin_peaks.setEnabled(True)
            self.view.btn_auto_analysis.setEnabled(True)
            return

        if self.dlimit is None:
            self.dlimit = limit_value
            # Visual feedback for first click: gray out left side
            self.view.highlight_selection(self.model.frequency, self.model.real_part, self.model.imag_part, 
                                        self.model.temperature, self.dlimit, None)
            self.view.btn_fit.setEnabled(False) # Wait for second limit
            self.view.spin_peaks.setEnabled(False)
            self.view.btn_auto_analysis.setEnabled(False)
        elif self.hlimit is None:
            # Second click - determine min and max
            f1 = self.dlimit
            f2 = limit_value
            
            self.dlimit = min(f1, f2)
            self.hlimit = max(f1, f2)
            
            self.view.highlight_selection(self.model.frequency, self.model.real_part, self.model.imag_part, 
                                        self.model.temperature, self.dlimit, self.hlimit)
            self.view.btn_fit.setEnabled(True)
            self.view.spin_peaks.setEnabled(True)
            self.view.btn_auto_analysis.setEnabled(True)

    def make_fit(self):
        try:
            n_peaks = self.view.spin_peaks.value()
            result = self.model.fit_data(n_peaks, self.dlimit, self.hlimit)
            if result.success:
                omega = self.model.calc_omega(self.model.frequency)
                eps_complex = self.model.eps_total(omega, result.params, n_peaks)
                real_calc = np.real(eps_complex)
                imag_calc = -np.imag(eps_complex)
                
                components = self.model.get_components(result.params, n_peaks)
                lines = self.view.plot_fit(self.model.frequency, real_calc, imag_calc, result.params, components=components)
                
                eps_inf = result.params['eps_inf'].value
                sigma_dc = result.params['sigma_dc'].value
                s = result.params['s'].value
                
                text = f"Manual Fit Results at {self.model.temperature} °C (χ²={result.chisqr:.1e}):\n"
                text += f"eps_inf = {eps_inf:.4e}\n"
                text += f"sigma_dc = {sigma_dc:.2e}, s = {s:.3f}\n"
                
                param_str_chunk = ""
                
                for i in range(1, n_peaks + 1):
                    de = result.params[f'delta_eps_{i}'].value
                    a = result.params[f'alpha_{i}'].value
                    b = result.params[f'beta_{i}'].value
                    t = result.params[f'tau_{i}'].value
                    eps_stat = eps_inf + de
                    
                    text += f"\nPeak {i}:\n"
                    text += f"  Delta eps = {de:.4e}\n"
                    text += f"  alpha = {a:.4f}\n"
                    text += f"  beta = {b:.4f}\n"
                    text += f"  tau = {t:.4e}\n"
                    
                    param_str_chunk += f"{eps_stat:.5f} {eps_inf:.5f} {t:.5e} {a:.5f} {b:.5f} {sigma_dc:.5e} {s:.5f}\n"
                
                self.model.cparams += param_str_chunk
                self.model.fit_history.append({
                    'lines': lines,
                    'param_str': param_str_chunk
                })
                
                self.view.btn_error_map.setEnabled(True)  # Fit result is available
                
                self.view.show_params(text)
            else:
                self.view.show_message("Fit Error", "Optimization failed.", QMessageBox.Critical)
        except Exception as e:
            self.view.show_message("Fit Error", str(e), QMessageBox.Critical)

    def auto_analysis(self):
        """Performs automatic analysis using lmfit in a background thread."""
        self.worker = Worker(self.model, self.dlimit, self.hlimit)
        self.worker.finished.connect(self.on_auto_analysis_finished)
        self.worker.error.connect(self.on_auto_analysis_error)
        
        # Create Progress Dialog
        self.progress_dialog = QProgressDialog("Running NLS Minimization... Please wait.", "Cancel", 0, 0, self.view)
        self.progress_dialog.setWindowModality(Qt.WindowModal)
        self.progress_dialog.setCancelButton(None) # Disable cancel for now as thread killing is tricky
        self.progress_dialog.show()
        
        self.worker.start()

    def on_auto_analysis_finished(self, success, result):
        if self.progress_dialog:
            self.progress_dialog.close()
            self.progress_dialog = None
            
        if success:
            n_peaks = getattr(result, 'n_peaks', 1)
            omega = self.model.calc_omega(self.model.frequency)
            eps_complex = self.model.eps_total(omega, result.params, n_peaks)
            fitted_real = np.real(eps_complex)
            fitted_imag = -np.imag(eps_complex)
            
            components = self.model.get_components(result.params, n_peaks)
            lines = self.view.plot_fit(self.model.frequency, fitted_real, fitted_imag, result.params, components=components)
            
            eps_inf = result.params['eps_inf'].value
            sigma_dc = result.params['sigma_dc'].value
            s = result.params['s'].value
            
            text = f"Auto Analysis Results at {self.model.temperature} °C (BIC={result.bic:.1f}, χ²={result.chisqr:.1e}):\n"
            text += f"eps_inf = {eps_inf:.4e}\n"
            text += f"sigma_dc = {sigma_dc:.2e}, s = {s:.3f}\n"
            
            param_str_chunk = ""
            
            for i in range(1, n_peaks + 1):
                de = result.params[f'delta_eps_{i}'].value
                a = result.params[f'alpha_{i}'].value
                b = result.params[f'beta_{i}'].value
                t = result.params[f'tau_{i}'].value
                eps_stat = eps_inf + de
                
                text += f"\nPeak {i}:\n"
                text += f"  Delta eps = {de:.4e}\n"
                text += f"  alpha = {a:.4f}\n"
                text += f"  beta = {b:.4f}\n"
                text += f"  tau = {t:.4e}\n"
                
                param_str_chunk += f"{eps_stat:.5f} {eps_inf:.5f} {t:.5e} {a:.5f} {b:.5f} {sigma_dc:.5e} {s:.5f}\n"
            
            self.model.cparams += param_str_chunk
            self.model.fit_history.append({
                'lines': lines,
                'param_str': param_str_chunk
            })
            
            self.view.btn_error_map.setEnabled(True)  # Fit result is available
            self.view.show_params(text)
        else:
            self.view.show_message("Analysis Error", "Fit failed", QMessageBox.Critical)

    def on_auto_analysis_error(self, error_msg):
        if self.progress_dialog:
            self.progress_dialog.close()
            self.progress_dialog = None
        self.view.show_message("Analysis Error", error_msg, QMessageBox.Critical)

    def chain_fit(self):
        if not self.model.file_path:
            self.view.show_message("Error", "No file selected.")
            return
            
        self.chain_worker = ChainFitWorker(self.model, 3, self.dlimit, self.hlimit)
        self.chain_worker.progress.connect(self.on_chain_fit_progress)
        self.chain_worker.finished.connect(self.on_chain_fit_finished)
        
        self.progress_dialog = QProgressDialog("Running Chain Fit...", "Cancel", 0, 100, self.view)
        self.progress_dialog.setWindowModality(Qt.WindowModal)
        self.progress_dialog.setCancelButton(None)
        self.progress_dialog.show()
        
        self.chain_worker.start()

    def on_chain_fit_progress(self, idx, total, temp):
        if self.progress_dialog:
            self.progress_dialog.setLabelText(f"Fitting temperature {temp} °C...")
            self.progress_dialog.setValue(int(100 * idx / max(1, total)))

    def on_chain_fit_finished(self, success, result):
        if self.progress_dialog:
            self.progress_dialog.close()
            self.progress_dialog = None
            
        if success:
            df = result
            if df.empty:
                self.view.show_message("Error", "Chain fit did not produce any results.")
                return
                
            # Save to Excel automatically
            try:
                base_name = os.path.splitext(self.model.file_path)[0]
                export_path = f"{base_name}_chain_fit_results.xlsx"
                df.to_excel(export_path, index=False)
            except Exception as e:
                print(f"Failed to export Excel: {e}")

    def global_fit(self):
        """Starts global 3D fitting and displays the results."""
        if not self.model.file_path:
            QMessageBox.warning(self.view, "Warning", "Select a data file first.")
            return

        n_peaks = self.view.spin_peaks.value()
        
        # Display confirmation dialog (fit may take longer)
        reply = QMessageBox.question(self.view, 'Global 3D Fit', 
                                    f"Start global fit for {n_peaks} peaks on the entire dataset?\n\n"
                                    f"⚠ Fit now runs in 2 phases (differential evolution + refinement).\n"
                                    f"Calculation may take tens of seconds to minutes.\n"
                                    f"The application will be unresponsive during the fit.",
                                    QMessageBox.Yes | QMessageBox.No, QMessageBox.No)
        
        if reply == QMessageBox.No:
            return

        QApplication.setOverrideCursor(Qt.WaitCursor)
        try:
            res = self.model.run_global_fit(max_peaks=n_peaks, dlimit=self.dlimit, hlimit=self.hlimit)
            QApplication.restoreOverrideCursor()

            if res and res.success:
                # Compose result message
                msg = "Global 3D Fit was successful!\n\n"
                msg += f"Redchi: {res.redchi:.3e}\n"
                msg += f"BIC: {res.bic:.2f}\n\n"

                # Conductivity (Arrhenius)
                msg += "── Conductivity (Arrhenius) ───────────\n"
                msg += f"  sigma_0: {res.params['sigma_0'].value:.3e}\n"
                msg += f"  E_a:     {res.params['E_cond'].value:.3f} eV\n"
                msg += f"  s (exponent): {res.params['s'].value:.3f}\n"
                msg += f"  eps_inf: {res.params['eps_inf'].value:.3f}\n\n"

                for i in range(1, n_peaks + 1):
                    VFT_B_i = res.params[f'VFT_B_{i}'].value
                    msg += f"── Peak {i} ({'VFT' if VFT_B_i > 0 else 'Arrhenius'}) ──────────\n"
                    msg += f"  delta_eps: {res.params[f'delta_eps_{i}'].value:.3f}\n"
                    msg += f"  log_tau_0: {res.params[f'log_tau_0_{i}'].value:.3f}\n"
                    if VFT_B_i > 0:
                        msg += f"  VFT_B: {VFT_B_i:.1f} K,  T₀: {res.params[f'VFT_T0_{i}'].value:.1f} K\n"
                    else:
                        msg += f"  Ea: {res.params[f'Ea_{i}'].value:.3f} eV\n"
                    msg += f"  alpha: {res.params[f'alpha_{i}'].value:.3f}\n"
                    msg += f"  beta:  {res.params[f'beta_{i}'].value:.3f}\n\n"

                QMessageBox.information(self.view, "Global Fit Success", msg)
                self.view.write_to_terminal(msg)

                # --- 3D visualization of model comparison with data ---
                try:
                    success_data, all_data = self.model.load_all_data(self.model.file_path)
                    if success_data:
                        import numpy as np
                        data_arr = all_data  # numpy array [Freq, Temp_C, Eps', Eps'']
                        # Apply frequency limits same as during fit
                        if self.dlimit is not None:
                            data_arr = data_arr[data_arr[:, 0] >= self.dlimit]
                        if self.hlimit is not None:
                            data_arr = data_arr[data_arr[:, 0] <= self.hlimit]
                        if len(data_arr) > 0:
                            self.view.plot_global_fit_3d(data_arr, res, n_peaks)
                except Exception as e_3d:
                    print(f"3D visualization of global fit failed: {e_3d}")

            else:
                QMessageBox.warning(self.view, "Global Fit Failed", "Optimization did not converge to a solution.")
        except Exception as e:
            QApplication.restoreOverrideCursor()
            QMessageBox.critical(self.view, "Error", f"An error occurred during global fit:\n{str(e)}")

    def save_params(self):
        if not self.model.cparams: return
        
        dir_name = os.path.dirname(self.model.file_path)
        base_name = os.path.splitext(os.path.basename(self.model.file_path))[0]
        temp_str = f"{self.model.temperature:.1f}".replace('.', 'p').replace(' ', '')
        output_filename = os.path.join(dir_name, f"{base_name}_T{temp_str}_coleparams.txt")
        
        try:
            with open(output_filename, "w", encoding="utf-8") as f:
                f.write(f"# Parameters for {base_name}\n")
                f.write(f"# Temperature: {self.model.temperature}\n")
                f.write("# ε_stat ε_inf τ α β σ_DC s\n")
                f.write(self.model.cparams)
            self.view.show_message("Saved", f"Saved to {output_filename}")
        except Exception as e:
            self.view.show_message("Save Error", str(e), QMessageBox.Critical)

    def show_error_map(self):
        """
        Starts 2D error landscape calculation and passes data to view for plotting.

        Workflow:
          1. Verifies existence of fit result and 2D data.
          2. Asks the user which two parameters they want to visualize.
          3. Runs grid-scan (model.calculate_error_landscape) under WaitCursor.
          4. Calls view.plot_error_landscape to display the result.
        """
        # Verification: fit result must exist
        if self.model.fit_result is None:
            self.view.show_message(
                "Error Map",
                "No fit result available.\n"
                "Perform fitting first (Make Fit or Automatic Analysis).",
                QMessageBox.Warning
            )
            return

        # Verification: data must be loaded for residual calculation
        if len(self.model.frequency) == 0:
            self.view.show_message(
                "Error Map",
                "Frequency data not loaded.\n"
                "Select a file and load data for the requested temperature.",
                QMessageBox.Warning
            )
            return

        # Get available fit parameters for user hint
        available_params = list(self.model.fit_result.params.keys())
        shape_params = [p for p in available_params if p.startswith('alpha_') or p.startswith('beta_')]
        default_hint = ', '.join(shape_params[:4]) if shape_params else ', '.join(available_params[:4])

        # Dialog: parameter X choice
        default_x = 'alpha_1' if 'alpha_1' in available_params else available_params[0]
        param_x, ok_x = QInputDialog.getItem(
            self.view,
            "Error Map – X axis",
            f"Select parameter for X axis:\n(available: {default_hint})",
            available_params,
            available_params.index(default_x) if default_x in available_params else 0,
            False
        )
        if not ok_x:
            return

        # Dialog: parameter Y choice
        default_y = 'beta_1' if 'beta_1' in available_params else available_params[min(1, len(available_params)-1)]
        param_y, ok_y = QInputDialog.getItem(
            self.view,
            "Error Map – Y axis",
            f"Select parameter for Y axis:\n(available: {default_hint})",
            available_params,
            available_params.index(default_y) if default_y in available_params else 1,
            False
        )
        if not ok_y:
            return

        if param_x == param_y:
            self.view.show_message(
                "Error Map",
                "Parameters X and Y must be different.",
                QMessageBox.Warning
            )
            return

        # Calculation under WaitCursor (30x30 = 900 model evaluations)
        QApplication.setOverrideCursor(Qt.WaitCursor)
        try:
            X, Y, Z, opt_x, opt_y = self.model.calculate_error_landscape(
                param_x_name=param_x,
                param_y_name=param_y,
                grid_size=30,
                range_pct=0.20
            )
        except ValueError as e:
            QApplication.restoreOverrideCursor()
            self.view.show_message("Error Map", str(e), QMessageBox.Critical)
            return
        except Exception as e:
            QApplication.restoreOverrideCursor()
            self.view.show_message(
                "Error Map",
                f"An error occurred while calculating the error landscape:\n{e}",
                QMessageBox.Critical
            )
            return
        finally:
            QApplication.restoreOverrideCursor()

        # Pass data to view for visualization
        self.view.plot_error_landscape(X, Y, Z, opt_x, opt_y, param_x, param_y)

    def show_3d(self):
        if not self.model.file_path:
            self.view.show_message("Error", "No file selected.")
            return
            
        success, result = self.model.load_all_data(self.model.file_path)
        if success:
            self.view.plot_3d(result)
        else:
            self.view.show_message("Error", f"Could not load 3D data: {result}", QMessageBox.Critical)

    def show_loglog(self):
        if not self.model.file_path:
            self.view.show_message("Error", "No file selected.")
            return
            
        success, result = self.model.load_all_data(self.model.file_path)
        if success:
            self.view.plot_loglog(result)
        else:
            self.view.show_message("Error", f"Could not load data: {result}", QMessageBox.Critical)

    def show_help(self):
        if self.help_window is None:
            self.help_window = HelpWindow()
        self.help_window.show()

    def save_log(self):
        text = self.view.get_terminal_text()
        if not text.strip():
            self.view.show_message("Info", "Terminal is empty.")
            return

        options = QFileDialog.Options()
        file_path, _ = QFileDialog.getSaveFileName(self.view, "Save Terminal Log", "", 
                                                 "Text Files (*.txt);;All Files (*)", options=options)
        if file_path:
            try:
                with open(file_path, "w", encoding="utf-8") as f:
                    f.write(text)
                self.view.show_message("Saved", f"Log saved to {file_path}")
            except Exception as e:
                self.view.show_message("Error", f"Could not save log: {e}", QMessageBox.Critical)

    def clear_log(self):
        self.view.clear_terminal()
