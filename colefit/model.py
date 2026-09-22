import numpy as np
import pandas as pd
from lmfit import Parameters, minimize, fit_report
from scipy.optimize import curve_fit
from scipy.constants import epsilon_0, k as k_B, e as e_charge
from typing import Optional, Any, Tuple

class BDSModel:
    """
    Class encapsulating physical models and logic for fitting BDS data
    (Broadband Dielectric Spectroscopy) using MVC architecture.
    """

    def __init__(self):
        self.frequency: np.ndarray = np.array([])
        self.real_part: np.ndarray = np.array([])
        self.imag_part: np.ndarray = np.array([])
        self.temperature: Optional[float] = None
        self.file_path: str = ""
        self.fit_result: Any = None
        self.cparams: str = ""
        self.fit_history: list = []

    def load_data(self, filepath: str, target_temp: float) -> bool:
        """
        Loads data from a file using pandas and filters it according to the requested temperature.
        Expected columns (logically): Freq. [Hz], Temp. [°C], Eps', Eps''

        Args:
            filepath (str): Path to the data file (.txt or .csv).
            target_temp (float): Target temperature for data filtration.

        Returns:
            bool: True if data loaded successfully, otherwise False.
        """
        try:
            self.file_path = filepath
            self.temperature = target_temp
            
            # Robust loading using pandas. Data can use semicolons, commas, or spaces
            # and Czech formatting with decimal commas.
            # First load as strings with a regex for delimiters.
            df = pd.read_csv(
                filepath, 
                sep=r'[;\t\s]+',  # Delimiter can be semicolon, tab, or multiple spaces
                engine='python', 
                encoding='cp1250', 
                skiprows=3,       # Skips initial meta-header
                header=None       # Columns named manually
            )
            
            # If there are more columns, trim to the first 4
            df = df.iloc[:, :4]
            df.columns = ['Freq. [Hz]', 'Temp. [°C]', "Eps'", "Eps''"]
            
            # Replacement of any decimal commas with dots and conversion to float
            for col in df.columns:
                if df[col].dtype == object:
                    df[col] = df[col].str.replace(',', '.').astype(float)
                    
            # Filtration by temperature with 0.1 °C tolerance
            df_filtered = df[np.isclose(df['Temp. [°C]'], target_temp, atol=0.1)].copy()
            
            if df_filtered.empty:
                return False
                
            # Sorting by frequency (important for correct plotting)
            
            # Saving to Numpy arrays
            self.frequency = df_filtered['Freq. [Hz]'].values
            self.real_part = df_filtered["Eps'"].values
            self.imag_part = df_filtered["Eps''"].values
            
            return True
        except Exception as e:
            print(f"Error loading data: {e}")
            return False

    def load_all_data(self, filepath: str) -> tuple[bool, Any]:
        """Loads all data from the file for 3D/Log-Log plotting."""
        try:
            df = pd.read_csv(
                filepath, 
                sep=r'[;\t\s]+',
                engine='python', 
                encoding='cp1250', 
                skiprows=3,
                header=None
            )
            df = df.iloc[:, :4]
            df.columns = ['Freq. [Hz]', 'Temp. [°C]', "Eps'", "Eps''"]
            for col in df.columns:
                if df[col].dtype == object:
                    df[col] = df[col].str.replace(',', '.').astype(float)
            
            data = df.values
            if len(data) == 0:
                return False, "No data found."
            return True, data
        except Exception as e:
            return False, str(e)

    @staticmethod
    def calc_omega(f: np.ndarray) -> np.ndarray:
        """Calculation of angular frequency from frequency."""
        return 2 * np.pi * f

    @staticmethod
    def eps_hn(omega: np.ndarray, eps_inf: float, delta_eps: float, 
               tau: float, alpha: float, beta: float) -> np.ndarray:
        """
        Havriliak-Negami (HN) relaxation in the complex domain.
        
        Equation: Eps*_HN(omega) = Eps_inf + (Delta_Eps) / (1 + (i * omega * tau)^alpha)^beta
        """
        i_omega_tau = 1j * omega * tau
        # Important to ensure correct calculation of complex power
        denominator = (1.0 + (i_omega_tau)**alpha)**beta
        return eps_inf + (delta_eps / denominator)

    @staticmethod
    def eps_cond(omega: np.ndarray, sigma_dc: float, s: float) -> np.ndarray:
        """
        Conductivity term in the complex domain.
        (Also includes electrode polarization effects when s < 1)
        
        Equation: Eps*_cond(omega) = -1j * (sigma_DC / (epsilon_0 * omega^s))
        """
        return -1j * (sigma_dc / (epsilon_0 * (omega**s)))

    @staticmethod
    def eps_total(omega: np.ndarray, params: Parameters, n_peaks: int = 1) -> np.ndarray:
        """
        Total dielectric response model: Eps*_total = Sum(Eps*_HN) + Eps*_cond
        Consists of conductivity background and an optional number of relaxation (HN) peaks.
        """
        eps_inf = params['eps_inf'].value
        sigma_dc = params['sigma_dc'].value
        s = params['s'].value
        
        # Initialization of complex array with zeros
        eps_star = np.zeros_like(omega, dtype=np.complex128)
        
        # Adding all defined relaxation processes
        for i in range(1, n_peaks + 1):
            delta_eps = params[f'delta_eps_{i}'].value
            tau = params[f'tau_{i}'].value
            alpha = params[f'alpha_{i}'].value
            beta = params[f'beta_{i}'].value
            
            # Add Eps_inf only to the first relaxation process (to avoid N-fold counting)
            current_eps_inf = eps_inf if i == 1 else 0.0
            
            eps_star += BDSModel.eps_hn(omega, current_eps_inf, delta_eps, tau, alpha, beta)
            
        # Adding conductivity contribution (dominating at low frequencies)
        eps_star += BDSModel.eps_cond(omega, sigma_dc, s)
        
        return eps_star

    @staticmethod
    def global_eps_total(omega: np.ndarray, T_K: np.ndarray, params: Parameters, n_peaks: int = 1) -> np.ndarray:
        """
        Total 3D dielectric response model: Eps*_total(omega, T_K).

        Conductivity: Arrhenius sigma(T) = sigma_0 * exp(-E_cond/kT)
        Relaxation: Arrhenius (VFT_B = 0) or VFT (VFT_B > 0)
        """
        eps_inf = params['eps_inf'].value
        s       = params['s'].value

        # ---- DC conductivity – Arrhenius ----
        sigma_0 = params['sigma_0'].value
        E_cond  = params['E_cond'].value
        exp_arg = np.minimum(E_cond * e_charge / (k_B * T_K), 500.0)   # anti-overflow
        sigma_dc = sigma_0 * np.exp(-exp_arg)

        eps_star = np.zeros_like(omega, dtype=np.complex128)

        # ---- Relaxation processes ----
        for i in range(1, n_peaks + 1):
            # Temperature-dependent amplitude
            delta_eps_ref     = params[f'delta_eps_{i}'].value
            C_eps             = params[f'C_eps_{i}'].value
            current_delta_eps = np.maximum(delta_eps_ref + C_eps * (1000.0 / T_K), 0.0)

            alpha = params[f'alpha_{i}'].value
            beta  = params[f'beta_{i}'].value

            log_tau_0 = params[f'log_tau_0_{i}'].value
            VFT_B     = float(params[f'VFT_B_{i}'].value)

            if VFT_B > 0:
                # VFT for relaxation (alpha relaxation in polymers)
                T_0     = params[f'VFT_T0_{i}'].value
                T_diff  = np.maximum(T_K - T_0, 1.0)
                exp_vft = np.minimum(VFT_B / T_diff, 500.0)
                tau = (10.0 ** log_tau_0) * np.exp(exp_vft)
            else:
                # Arrhenius relaxation (beta relaxation)
                Ea      = params[f'Ea_{i}'].value
                exp_arr = np.minimum(Ea * e_charge / (k_B * T_K), 500.0)
                tau = (10.0 ** log_tau_0) * np.exp(exp_arr)

            current_eps_inf = eps_inf if i == 1 else 0.0
            eps_star += BDSModel.eps_hn(omega, current_eps_inf, current_delta_eps, tau, alpha, beta)

        eps_star += BDSModel.eps_cond(omega, sigma_dc, s)
        return eps_star

    def global_residual(self, params: Parameters, f: np.ndarray, T_K: np.ndarray,
                        eps_real_data: np.ndarray, eps_imag_data: np.ndarray,
                        n_peaks: int = 1) -> np.ndarray:
        """
        Residual function for global 3D fitting.
        Uses stable relative weighting to suppress conductivity dominance and prevent crashes.
        """
        omega = self.calc_omega(f)
        eps_model = self.global_eps_total(omega, T_K, params, n_peaks)
        
        eps_real_model = np.real(eps_model)
        eps_imag_model = -np.imag(eps_model)
        
        # Safe relative error weighting (same as 2D fit)
        weights_real = np.where(np.abs(eps_real_data) < 1e-12, 1e-12, np.abs(eps_real_data))
        weights_imag = np.where(np.abs(eps_imag_data) < 1e-12, 1e-12, np.abs(eps_imag_data))
        
        res_real = (eps_real_data - eps_real_model) / weights_real
        res_imag = (eps_imag_data - eps_imag_model) / weights_imag
        
        return np.concatenate([res_real, res_imag])

    def residual(self, params: Parameters, f: np.ndarray, 
                 eps_real_data: np.ndarray, eps_imag_data: np.ndarray, 
                 n_peaks: int = 1) -> np.ndarray:
        """
        Residual function designed specifically for lmfit.minimize.
        Since lmfit cannot handle complex numbers directly, the function separates
        real and imaginary parts and joins them into a single long 1D array.
        
        Additionally applies necessary weighting by the data value itself,
        to balance order-of-magnitude differences (otherwise dominant conductivity would wipe out relaxations).
        """
        omega = self.calc_omega(f)
        
        # Get the total computed complex profile
        eps_model = self.eps_total(omega, params, n_peaks)
        
        # Split into real and imaginary parts (convention Eps* = Eps' - i*Eps'')
        eps_real_model = np.real(eps_model)
        eps_imag_model = -np.imag(eps_model)
        
        # ---- WEIGHTING ----
        # Weight corresponds to the data value itself (creates relative error).
        # Set a lower limit (1e-12) to prevent division by zero.
        weights_real = np.where(np.abs(eps_real_data) < 1e-12, 1e-12, np.abs(eps_real_data))
        weights_imag = np.where(np.abs(eps_imag_data) < 1e-12, 1e-12, np.abs(eps_imag_data))
        
        # Calculate weighted residuals
        res_real = (eps_real_data - eps_real_model) / weights_real
        res_imag = (eps_imag_data - eps_imag_model) / weights_imag
        
        # lmfit requires a single concatenated 1D array as a return value
        return np.concatenate([res_real, res_imag])

    def setup_parameters(self, n_peaks: int = 1) -> Parameters:
        """
        Defines fitting parameters and their physical bounds.
        """
        params = Parameters()
        
        # Eps_inf: guessed from minimum real part values (typically at high frequencies)
        eps_inf_guess = np.min(self.real_part) if len(self.real_part) > 0 else 2.0
        params.add('eps_inf', value=eps_inf_guess, min=0.0)
        
        # Conductivity parameters
        # Sigma_DC is very small (S/cm), start at a very small value. Bounds: >0
        # s (exponent for electrode effects/actual conductivity): Bounds: <0.5, 1.2>
        params.add('sigma_dc', value=1e-14, min=0.0)
        params.add('s', value=1.0, min=0.5, max=1.2)
        
        # Parameters for N Havriliak-Negami relaxations
        for i in range(1, n_peaks + 1):
            # Intelligent tau guess for the first peak based on imaginary part maximum
            if i == 1 and len(self.imag_part) > 0:
                peak_idx = np.argmax(self.imag_part)
                tau_guess = 1.0 / (2 * np.pi * self.frequency[peak_idx])
            else:
                tau_guess = tau_guess / 100.0 if 'tau_guess' in locals() else 1e-4
                
            delta_eps_guess = np.max(self.real_part) - eps_inf_guess if len(self.real_part) > 0 else 1.0
            
            # Initial parameter definition with bounds as specified
            params.add(f'delta_eps_{i}', value=max(0.1, delta_eps_guess / n_peaks), min=0.0)
            params.add(f'tau_{i}',       value=tau_guess, min=1e-10, max=1e5)
            params.add(f'alpha_{i}',     value=0.8,       min=0.1, max=1.0)
            params.add(f'beta_{i}',      value=0.8,       min=0.1, max=1.0)
            
        return params

    def fit_data(self, n_peaks: int = 1, dlimit: Optional[float] = None, hlimit: Optional[float] = None, initial_params: Optional[Parameters] = None) -> Any:
        """
        Main function to run robust Levenberg-Marquardt fit via lmfit.
        
        Args:
            n_peaks: Number of Havriliak-Negami relaxation processes.
            dlimit: Lower frequency limit for fitting (Hz).
            hlimit: Upper frequency limit for fitting (Hz).
            initial_params: Initial parameter set (optional, for global fit).
            
        Returns:
            MinimizerResult containing fitting results.
        """
        if len(self.frequency) == 0:
            raise ValueError("No data loaded for fitting.")
            
        # Fit range restriction
        mask = np.ones(len(self.frequency), dtype=bool)
        if dlimit is not None:
            mask &= (self.frequency >= dlimit)
        if hlimit is not None:
            mask &= (self.frequency <= hlimit)
            
        fit_freq = self.frequency[mask]
        fit_real = self.real_part[mask]
        fit_imag = self.imag_part[mask]
        
        if len(fit_freq) < 5:
            raise ValueError("Not enough data for fitting in the given range.")
            
        if initial_params is not None:
            params = initial_params.copy()
            # Ensure the number of peaks matches
            actual_peaks = sum(1 for name in params if name.startswith('tau_'))
            if actual_peaks != n_peaks:
                params = self.setup_parameters(n_peaks)
        else:
            params = self.setup_parameters(n_peaks)
        
        self.fit_result = minimize(
            self.residual,
            params,
            args=(fit_freq, fit_real, fit_imag, n_peaks),
            method='least_squares',
            ftol=1e-13, xtol=1e-13, gtol=1e-13
        )
        
        self.fit_result.n_peaks = n_peaks # Save for later use
        return self.fit_result

    def calculate_error_landscape(
        self,
        param_x_name: str = 'alpha_1',
        param_y_name: str = 'beta_1',
        grid_size: int = 30,
        range_pct: float = 0.20
    ):
        """
        Calculates 2D error landscape as a function of two selected parameters around their found optimum.

        Method is intended for parameter correlation visualization and stability assessment
        (valley width/shape in parameter space) for scientific publications.

        Args:
            param_x_name (str): Name of the first parameter (X axis), e.g., 'alpha_1'.
            param_y_name (str): Name of the second parameter (Y axis), e.g., 'beta_1'.
            grid_size    (int): Number of points per grid axis (grid_size x grid_size).
            range_pct  (float): Relative range around optimum (0.20 = +/- 20%).

        Returns:
            tuple: (X, Y, Z, opt_x, opt_y)
                - X   (ndarray): Matrix of X parameter values (grid_size x grid_size)
                - Y   (ndarray): Matrix of Y parameter values (grid_size x grid_size)
                - Z   (ndarray): Matrix of RSS (sum of squared residuals)
                - opt_x (float): Optimal param_x value (center of the grid)
                - opt_y (float): Optimal param_y value (center of the grid)

        Raises:
            ValueError: If no fit result exists or parameters are not found.
        """
        if self.fit_result is None:
            raise ValueError(
                "No fit result available. "
                "Run fitting first (fit_data / auto_fit)."
            )

        # Get the number of peaks saved during fitting
        n_peaks = getattr(self.fit_result, 'n_peaks', 1)

        # Verify that both parameters actually exist in the parameter set
        opt_params = self.fit_result.params
        if param_x_name not in opt_params:
            raise ValueError(
                f"Parameter '{param_x_name}' was not found in the fit result. "
                f"Available parameters: {list(opt_params.keys())}"
            )
        if param_y_name not in opt_params:
            raise ValueError(
                f"Parameter '{param_y_name}' was not found in the fit result. "
                f"Available parameters: {list(opt_params.keys())}"
            )

        opt_x = opt_params[param_x_name].value
        opt_y = opt_params[param_y_name].value

        # --- Grid Range Definition ---
        # Range is +/- range_pct from optimum, clipped to physically allowed parameter limits.
        p_x = opt_params[param_x_name]
        p_y = opt_params[param_y_name]

        # Lower and upper bounds from the Parameter object itself (or fallback 0.001/1.0)
        x_hard_min = p_x.min if (p_x.min is not None and np.isfinite(p_x.min)) else 0.001
        x_hard_max = p_x.max if (p_x.max is not None and np.isfinite(p_x.max)) else 1.0
        y_hard_min = p_y.min if (p_y.min is not None and np.isfinite(p_y.min)) else 0.001
        y_hard_max = p_y.max if (p_y.max is not None and np.isfinite(p_y.max)) else 1.0

        x_lo = max(x_hard_min, opt_x * (1.0 - range_pct))
        x_hi = min(x_hard_max, opt_x * (1.0 + range_pct))
        y_lo = max(y_hard_min, opt_y * (1.0 - range_pct))
        y_hi = min(y_hard_max, opt_y * (1.0 + range_pct))

        # Safety fallback – if the range is degenerate, expand it fixedly
        if x_hi <= x_lo:
            x_lo, x_hi = max(x_hard_min, opt_x - 0.05), min(x_hard_max, opt_x + 0.05)
        if y_hi <= y_lo:
            y_lo, y_hi = max(y_hard_min, opt_y - 0.05), min(y_hard_max, opt_y + 0.05)

        x_vals = np.linspace(x_lo, x_hi, grid_size)
        y_vals = np.linspace(y_lo, y_hi, grid_size)
        X, Y = np.meshgrid(x_vals, y_vals)   # both matrices have shape (grid_size, grid_size)
        Z = np.zeros_like(X, dtype=np.float64)

        # --- RSS Calculation at Every Grid Point ---
        # Create a copy of optimal parameters; both scanned parameters temporarily
        # freed from fit constraints (vary=False, fixed value).
        scan_params = opt_params.copy()
        scan_params[param_x_name].vary = False
        scan_params[param_y_name].vary = False

        for row in range(grid_size):
            for col in range(grid_size):
                scan_params[param_x_name].value = X[row, col]
                scan_params[param_y_name].value = Y[row, col]

                try:
                    residuals = self.residual(
                        scan_params,
                        self.frequency,
                        self.real_part,
                        self.imag_part,
                        n_peaks
                    )
                    # RSS = residual sum of squares (corresponds to chi2 in lmfit without normalization)
                    Z[row, col] = float(np.sum(residuals ** 2))
                except Exception:
                    # If calculation fails (e.g., numerical instability), store NaN
                    Z[row, col] = np.nan

        return X, Y, Z, opt_x, opt_y

    def auto_fit(self, max_peaks: int = 3, dlimit: Optional[float] = None, hlimit: Optional[float] = None) -> Any:
        """
        Tries fitting for 1 to max_peaks peaks and selects the best one according to BIC criterion.
        """
        best_result = None
        best_bic = float('inf')
        
        for n_peaks in range(1, max_peaks + 1):
            try:
                result = self.fit_data(n_peaks, dlimit, hlimit)
                if result.success and result.bic < best_bic:
                    best_bic = result.bic
                    best_result = result
            except Exception as e:
                print(f"Error fitting {n_peaks} peaks: {e}")
                
        self.fit_result = best_result
        return best_result

    def get_components(self, params, n_peaks: int):
        """
        Returns a dictionary with all components (Conductivity, Peak 1, etc.) 
        generated from given parameters for the given frequency axis.
        Format: list of tuples (name, real, imag)
        """
        omega = self.calc_omega(self.frequency)
        eps_inf = params['eps_inf'].value
        sigma_dc = params['sigma_dc'].value
        s = params['s'].value
        
        components = []
        if sigma_dc > 1e-15:
            comp_cond = self.eps_cond(omega, sigma_dc, s)
            c_real = np.full_like(self.frequency, eps_inf, dtype=float) + np.real(comp_cond)
            c_imag = -np.imag(comp_cond)
            components.append(("Conductivity", c_real, c_imag))
            
        for i in range(1, n_peaks + 1):
            de = params[f'delta_eps_{i}'].value
            a = params[f'alpha_{i}'].value
            b = params[f'beta_{i}'].value
            t = params[f'tau_{i}'].value
            
            comp_peak = self.eps_hn(omega, eps_inf, de, t, a, b)
            components.append((f"Peak {i}", np.real(comp_peak), -np.imag(comp_peak)))
            
        return components

    def chain_fit(self, max_peaks: int = 3, dlimit: Optional[float] = None, hlimit: Optional[float] = None, progress_callback=None) -> pd.DataFrame:
        """
        Batch processing across all temperatures from lowest upwards.
        First temperature finds the best number of peaks via auto_fit.
        Subsequent ones use the same number of peaks and parameters from the previous temperature with DYNAMIC BOUNDS and SORTING.
        """
        success, all_data = self.load_all_data(self.file_path)
        if not success:
            raise ValueError(f"Failed to load data for chain fit: {all_data}")
            
        df_all = pd.DataFrame(all_data, columns=['Freq. [Hz]', 'Temp. [°C]', "Eps'", "Eps''"])
        temps = sorted(df_all['Temp. [°C]'].unique())
        
        results_list = []
        history_params = [] # List of successful parameters for trend
        optimal_peaks = None
        prev_redchi = None
        
        for i, temp in enumerate(temps):
            if progress_callback:
                progress_callback(i, len(temps), temp)
                
            df_t = df_all[np.isclose(df_all['Temp. [°C]'], temp, atol=0.1)].sort_values(by='Freq. [Hz]')
            if df_t.empty:
                continue
                
            self.frequency = df_t['Freq. [Hz]'].values
            self.real_part = df_t["Eps'"].values
            self.imag_part = df_t["Eps''"].values
            self.temperature = temp
            
            try:
                if not history_params:
                    # First temperature - find optimal number of peaks
                    res = self.auto_fit(max_peaks, dlimit, hlimit)
                    if res and res.success:
                        optimal_peaks = getattr(res, 'n_peaks', 1)
                else:
                    # DYNAMIC BOUNDS AND TREND EXTRAPOLATION
                    current_guess = history_params[-1].copy()
                    
                    for p in range(1, optimal_peaks + 1):
                        t_name = f'tau_{p}'
                        de_name = f'delta_eps_{p}'
                        
                        # Shift extrapolation
                        if len(history_params) > 1 and t_name in history_params[-2]:
                            shift = history_params[-1][t_name].value / history_params[-2][t_name].value
                            shift = np.clip(shift, 0.1, 10.0) # Safety shift limit
                        else:
                            shift = 0.8 # Assume slight acceleration (shift to lower tau)

                        # Set new guess
                        pred_tau = current_guess[t_name].value * shift
                        current_guess[t_name].value = pred_tau
                        
                        # HARD BOUNDS for tau (relaxed from 50x to 1000x for non-linear jumps)
                        current_guess[t_name].min = max(1e-10, pred_tau / 1000.0)
                        current_guess[t_name].max = min(1e5, pred_tau * 1000.0)
                        
                        # Amplitude protection against overshooting
                        pred_de = current_guess[de_name].value
                        if pred_de > 1e-5:
                            current_guess[de_name].min = pred_de / 10.0
                            current_guess[de_name].max = pred_de * 10.0

                    # Conductivity bounds
                    prev_sigma = current_guess['sigma_dc'].value
                    if prev_sigma > 1e-15:
                        current_guess['sigma_dc'].max = prev_sigma * 100.0

                    # Fitting with locked bounds
                    res = self.fit_data(optimal_peaks, dlimit, hlimit, initial_params=current_guess)
                    
                    # --- QUALITY CONTROL AND NEW/DISAPPEARING PEAK DETECTION ---
                    # Reevaluation is triggered not only when fit worsens, but primarily if fit COMPLETELY CRASHED (not res.success)
                    if not res or not res.success or (prev_redchi is not None and res.redchi > 1.5 * prev_redchi):
                        reason = "crashed" if not res or not res.success else f"worsened from {prev_redchi:.2e} to {res.redchi:.2e}"
                        print(f"Fit at temp {temp} °C {reason}. Starting free reevaluation via auto_fit...")
                        
                        # Let the algorithm freely select the ideal number of peaks (from 1 to max_peaks)
                        res_new = self.auto_fit(max_peaks, dlimit, hlimit)
                        
                        if res_new and res_new.success:
                            # New solution found. Is it better than the crashed/worsened one?
                            if not res or not res.success or res_new.bic < res.bic:
                                print(f"Reevaluation accepted! Number of peaks changing from {optimal_peaks} to {res_new.n_peaks}")
                                res = res_new
                                optimal_peaks = res_new.n_peaks
                                history_params.clear() # Reset history due to parameter structure change
                                prev_redchi = None
                                
                if res and res.success:
                    prev_redchi = getattr(res, 'redchi', prev_redchi)
                    
                    # --- FORCED PEAK SORTING (Prevents column swapping) ---
                    peaks_data = []
                    for p in range(1, optimal_peaks + 1):
                        peaks_data.append({
                            'de': res.params[f'delta_eps_{p}'].value,
                            'tau': res.params[f'tau_{p}'].value,
                            'a': res.params[f'alpha_{p}'].value,
                            'b': res.params[f'beta_{p}'].value
                        })
                    
                    # Sort by relaxation time ascending (fastest to slowest)
                    peaks_data.sort(key=lambda x: x['tau'])
                    
                    # Insert sorted values back into parameters
                    for p in range(1, optimal_peaks + 1):
                        res.params[f'delta_eps_{p}'].value = peaks_data[p-1]['de']
                        res.params[f'tau_{p}'].value = peaks_data[p-1]['tau']
                        res.params[f'alpha_{p}'].value = peaks_data[p-1]['a']
                        res.params[f'beta_{p}'].value = peaks_data[p-1]['b']

                    history_params.append(res.params.copy())
                    if len(history_params) > 5:
                        history_params.pop(0)

                    # Record results
                    row = {'Temp. [°C]': temp, 'n_peaks': optimal_peaks, 'eps_inf': res.params['eps_inf'].value, 
                           'sigma_dc': res.params['sigma_dc'].value, 's': res.params['s'].value}
                    for p in range(1, optimal_peaks + 1):
                        row[f'delta_eps_{p}'] = res.params[f'delta_eps_{p}'].value
                        row[f'tau_{p}'] = res.params[f'tau_{p}'].value
                        row[f'alpha_{p}'] = res.params[f'alpha_{p}'].value
                        row[f'beta_{p}'] = res.params[f'beta_{p}'].value
                    results_list.append(row)
                else:
                    print(f"Warning: Fit failed for temp {temp} °C")
            except Exception as e:
                print(f"Error in chain fit at {temp} °C: {e}")
                
        return pd.DataFrame(results_list)

    def run_global_fit(self, max_peaks: int = 1, dlimit: Optional[float] = None, hlimit: Optional[float] = None) -> Any:
        """
        Performs a global 3D fit on the entire dataset with VFT and Arrhenius support.

        Two-phase strategy:
          1. Differential Evolution – searches global space, doesn't stick in local minima
          2. Least-squares         – fine-tunes DE result to high precision
        """
        success, all_data = self.load_all_data(self.file_path)
        if not success:
            raise ValueError("Failed to load data for global fit.")

        df_all = pd.DataFrame(all_data, columns=['Freq. [Hz]', 'Temp. [°C]', "Eps'", "Eps''"])

        # Applying frequency limits
        if dlimit is not None:
            df_all = df_all[df_all['Freq. [Hz]'] >= dlimit]
        if hlimit is not None:
            df_all = df_all[df_all['Freq. [Hz]'] <= hlimit]

        if df_all.empty:
            raise ValueError("No data left after applying frequency limits.")

        f_flat      = df_all['Freq. [Hz]'].values
        T_C_flat    = df_all['Temp. [°C]'].values
        T_K_flat    = T_C_flat + 273.15
        eps_real_data = df_all["Eps'"].values
        eps_imag_data = df_all["Eps''"].values

        # ----- Parameter Initialization -----
        params = Parameters()

        # Robust eps_inf estimate (2nd percentile of real component)
        eps_inf_guess = max(0.5, float(np.percentile(eps_real_data, 2)))
        params.add('eps_inf', value=eps_inf_guess, min=0.0, max=20.0)
        params.add('s',       value=1.0,           min=0.5, max=1.2)

        # Conductivity – Arrhenius: sigma(T) = sigma_0 * exp(-E_cond/kT)
        # (VFT for conductivity is not added – the optimizer would select it mathematically,
        #  not physically, which led to a worse result)
        params.add('sigma_0', value=1e-6, min=1e-20, max=1e6)
        params.add('E_cond',  value=0.5,  min=0.01,  max=3.0)

        # Total amplitude and minimum share for one peak
        total_amp    = max(1.0, float(np.percentile(eps_real_data, 95)) - eps_inf_guess)
        amp_per_peak = total_amp / max_peaks
        min_amp      = max(0.05, amp_per_peak * 0.10)   # prevents collapse to zero

        # Predefined SIGNIFICANTLY DISTINCT initial values for up to 3 peaks
        # (beta relaxation – fast; alpha relaxation – medium/slow)
        Ea_init       = [0.25,  0.60,  1.00]   # [eV]
        log_tau0_init = [-10.0, -13.5, -17.0]  # log10(τ₀ [s])

        min_temp = float(np.min(T_K_flat))

        for i in range(1, max_peaks + 1):
            idx = i - 1
            params.add(f'delta_eps_{i}',  value=amp_per_peak,       min=min_amp, max=total_amp * 3)
            params.add(f'C_eps_{i}',      value=0.0,                min=-50.0, max=50.0)
            params.add(f'alpha_{i}',      value=0.7,                min=0.001, max=1.0)
            params.add(f'beta_{i}',       value=0.8,                min=0.001, max=1.0)
            params.add(f'log_tau_0_{i}',  value=log_tau0_init[idx], min=-20.0, max=-5.0)
            params.add(f'Ea_{i}',         value=Ea_init[idx],       min=0.01,  max=2.5)
            params.add(f'VFT_B_{i}',      value=0.0,                min=0.0,   max=5000.0)
            params.add(f'VFT_T0_{i}',     value=min_temp - 50.0,    min=0.0,   max=min_temp - 5.0)

        residual_args = (f_flat, T_K_flat, eps_real_data, eps_imag_data, max_peaks)

        # ===== PHASE 1: Differential Evolution (global search) =====
        # Avoids local minima where one peak collapses
        print(f"Global 3D Fit – {max_peaks} peak(s)  |  Phase 1/2: Differential Evolution...")
        res_de = minimize(
            self.global_residual,
            params,
            args=residual_args,
            method='differential_evolution',
            nan_policy='omit',
            max_nfev=80_000,              # practical limit for reasonable time
        )
        print(f"  DE done.  redchi = {res_de.redchi:.3e}")

        # ===== PHASE 2: Local Refinement (least_squares) =====
        print("  Phase 2/2: Local Refinement (least_squares)...")
        self.fit_result = minimize(
            self.global_residual,
            res_de.params,
            args=residual_args,
            method='least_squares',
            nan_policy='omit',
            ftol=1e-10, xtol=1e-10, gtol=1e-10,
        )
        self.fit_result.n_peaks = max_peaks
        print(f"Global fit finished. Success: {self.fit_result.success}, Redchi: {self.fit_result.redchi:.3e}")
        return self.fit_result

class PhysicsEvaluator:
    """Class for evaluating relaxation maps (Arrhenius / VFT)."""
    
    @staticmethod
    def arrhenius_eqn(inv_T, log_tau_0, E_a):
        """
        Linearized Arrhenius equation.
        X-axis: 1000/T [K^-1]
        Y-axis: log10(tau)
        Equation: log10(tau) = log10(tau_0) + (E_a / (k_B * ln(10))) * (1/T)
        Here inv_T is already (1000/T), so (1/T) = inv_T / 1000.
        E_a is in eV. k_B is in J/K, so e_charge converts eV to Joules.
        """
        # E_a in Joules
        E_a_J = E_a * e_charge
        return log_tau_0 + (E_a_J / (k_B * np.log(10))) * (inv_T / 1000.0)
        
    @staticmethod
    def vft_eqn(inv_T, log_tau_0, B, T_0):
        """
        VFT equation.
        X-axis: 1000/T [K^-1]  --> T = 1000 / inv_T
        Y-axis: log10(tau)
        Equation: log10(tau) = log10(tau_0) + B / (ln(10) * (T - T_0))
        """
        T = 1000.0 / inv_T
        return log_tau_0 + B / (np.log(10) * (T - T_0))
        
    @classmethod
    def fit_arrhenius(cls, T_C: np.ndarray, tau: np.ndarray) -> Tuple[np.ndarray, np.ndarray, float, float]:
        """Fits log10(tau) against 1000/T_K using Arrhenius."""
        T_K = T_C + 273.15
        inv_T = 1000.0 / T_K
        log_tau = np.log10(tau)
        
        # Popt: log_tau_0, E_a [eV]
        # Guesses: E_a around 0.5 eV, log_tau_0 around -14
        popt, _ = curve_fit(cls.arrhenius_eqn, inv_T, log_tau, p0=[-14.0, 0.5])
        
        inv_T_fit = np.linspace(min(inv_T), max(inv_T), 100)
        log_tau_fit = cls.arrhenius_eqn(inv_T_fit, *popt)
        
        return inv_T, log_tau, inv_T_fit, log_tau_fit, popt[1], popt[0]
        
    @classmethod
    def fit_vft(cls, T_C: np.ndarray, tau: np.ndarray) -> Tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray, float, float]:
        """Fits log10(tau) against 1000/T_K using VFT."""
        T_K = T_C + 273.15
        inv_T = 1000.0 / T_K
        log_tau = np.log10(tau)
        
        # Popt: log_tau_0, B, T_0
        # Guesses: T_0 below lowest temperature
        min_T = np.min(T_K)
        p0 = [-14.0, 1000.0, min_T - 50.0]
        bounds = ([-20, 0, 0], [0, 10000, min_T - 5.0])
        
        popt, _ = curve_fit(cls.vft_eqn, inv_T, log_tau, p0=p0, bounds=bounds)
        
        inv_T_fit = np.linspace(min(inv_T), max(inv_T), 100)
        log_tau_fit = cls.vft_eqn(inv_T_fit, *popt)
        
        # Returns: T_0, B. For VFT, usually T_0 and Fragility or just B are given.
        # Here we return T_0 and parameter B.
        return inv_T, log_tau, inv_T_fit, log_tau_fit, popt[2], popt[1]
