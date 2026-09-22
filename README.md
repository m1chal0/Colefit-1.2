# ColeFIT 1.2: Broadband Dielectric Spectroscopy Analysis Software

This software was presented on the 2026 IEEE International Conference on High Voltage Engineering and Application (ICHVE 2026) in the paper titled **Broadband Dielectric Spectroscopy Analysis of Nanocomposites using ColeFIT Automation Software** - Ondřej Michal, Zdeněk Frána, Pavel Trnka, Jaroslav Hornak

## 1. Overview
**ColeFIT** is a specialized, open-source scientific software tool designed for the automated analysis and deconvolution of Broadband Dielectric Spectroscopy (BDS) data. It replaces manual, bias-prone curve-fitting with a fast, repeatable algorithmic process. 

The software fits a generalized **Havriliak-Negami (HN) model combined with a DC conductivity term** to complex dielectric permittivity spectra. It is explicitly designed to handle complex overlapping secondary relaxations heavily convoluted with conductivity backgrounds, making it an essential tool for materials science, high-voltage engineering, and polymer physics.

## 2. Key Features
- **Data Import**: Seamless loading of `.txt` and `.csv` files (fully compatible with Novocontrol Alpha A spectrometers).
- **Advanced Visualization**:
  - Frequency vs. Imaginary Permittivity ($\varepsilon''$)
  - Frequency vs. Real Permittivity ($\varepsilon'$)
  - Cole-Cole plot ($\varepsilon'$ vs. $\varepsilon''$)

![image](https://github.com/m1chal0/Colefit-1.2/blob/main/colefit.jpg)

- **Intelligent Fitting & Deconvolution**:
  - **Automatic Model Selection**: Automatically determines the true physical number of relaxation peaks (1 to 3) using the Bayesian Information Criterion (BIC) to strictly prevent mathematical overfitting.
  - **Robust Optimization**: Utilizes a combination of Genetic Algorithms (Differential Evolution) for global parameter searching and Non-Linear Least Squares (Levenberg-Marquardt) for high-precision polishing.
  - **Relative Error Weighting**: Prevents massive low-frequency conductivity tails from statistically erasing small-scale dipolar relaxations.
- **Physical Boundaries**: Strict enforcement of physical limits on fitting parameters (e.g., $s \ge 0.5$) to prevent non-physical background compensation.

## 3. Mathematical & Physical Model
ColeFIT evaluates the complex permittivity $\varepsilon^*(\omega)$ using a superposition of $N$ Havriliak-Negami (HN) relaxations alongside an explicit DC conductivity term:

$$\varepsilon^*(\omega) = \varepsilon_\infty + \sum_{k=1}^{N} \frac{\Delta\varepsilon_k}{\left[1 + (i\omega\tau_k)^{\alpha_k}\right]^{\beta_k}} - i \frac{\sigma_{DC}}{\varepsilon_0 \omega^s}$$

### Parameter Definitions & Conventions:
- **$N$**: Number of distinct relaxation processes.
- **$\varepsilon_\infty$**: High-frequency (optical) permittivity limit.
- **$\Delta\varepsilon_k$**: Dielectric relaxation strength of the $k$-th process.
- **$\tau_k$**: Characteristic relaxation time.
- **$\alpha_k, \beta_k$**: Shape parameters describing symmetric and asymmetric broadening. 
  - *Note on Notation*: ColeFIT uses the **direct exponent convention**, strictly bounded by $0 < \alpha_k \le 1$ and $0 < \beta_k \le 1$. In this notation, $\alpha_k = 1$ and $\beta_k = 1$ represents an ideal Debye relaxation. This is mathematically equivalent to the $(1-\alpha_{KS})$ notation found in classical texts (e.g., Kremer & Schönhals).
- **$\sigma_{DC}$**: Direct current conductivity.
- **$s$**: Fractional conductivity exponent. ColeFIT enforces a physical lower bound of $s \ge 0.5$ (the Warburg diffusion limit) to ensure the optimizer does not misinterpret flat instrumental noise or purely capacitive regimes as macroscopic charge transport.

## 4. Optimization Engine & Algorithm Design
The core of the automated analysis utilizes a **Differential Evolution (DE)** stochastic method combined with data-driven deterministic initialization to find the global minimum in the complex multi-modal landscape of dielectric spectra.

### 4.1 Relative Error Weighting (Fitness Function)
A notorious issue in BDS fitting is magnitude disparity. At high temperatures, $\varepsilon''$ values driven by DC conductivity can reach $10^4$, while secondary relaxations may exhibit amplitudes of $10^{-1}$. Standard absolute error minimization would ignore the small peaks. 

ColeFIT implements a **relative error weighting strategy** with a safety floor to prevent division-by-zero singularities:

$$Res_{real} = \frac{\varepsilon'_{exp} - \varepsilon'_{model}}{\max(\vert{}\varepsilon'_{exp}\vert{}, 10^{-12})}$$
$$Res_{imag} = \frac{\varepsilon''_{exp} - \varepsilon''_{model}}{\max(\vert{}\varepsilon''_{exp}\vert{}, 10^{-12})}$$

### 4.2 How It Works
1.  **Data-Driven Initialization**: Initial guesses are derived dynamically from the raw data (e.g., initial $\tau$ is estimated from $f_{max}$ of the primary loss peak).
2.  **Genetic Algorithm (DE)**: A population of candidate solutions is mutated and recombined to explore the parameter space avoiding local traps.
3.  **Model Selection (BIC)**: The algorithm fits 1, 2, and 3-peak models sequentially. The Bayesian Information Criterion is calculated to balance goodness-of-fit with model simplicity:
    $$BIC = n \cdot \ln(RSS/n) + k \cdot \ln(n)$$
    *(Where $n$ is data points, $k$ is free parameters).*
4.  **Polishing**: A local optimizer (L-BFGS-B / Levenberg-Marquardt) refines the DE solution to high mathematical precision.

## 5. Performance & Algorithmic Optimizations
ColeFIT is optimized for modern multi-core architectures to handle large datasets efficiently.

### A. Parallelization
The Differential Evolution algorithm utilizes all available CPU cores (`workers=-1`), yielding significant speedups on multi-core processors.

### B. JIT Compilation (Numba)
Key mathematical functions (`eps_hn`, `eps_cond`, and the relative residual arrays) are Just-In-Time (JIT) compiled using **Numba** directly to native machine code. This effectively eliminates Python interpreter overhead for millions of function evaluations during optimization.

### C. Early Stopping Protocol
If a simpler model achieves an exceptional fit ($R^2 > 0.999$), the search space is truncated, and the evaluation of highly complex multi-peak models is halted to save computational resources.

## 6. Installation & Usage
### Requirements
- Python 3.8+
- `numpy`, `scipy`, `matplotlib`, `PyQt5`, `numba`, `lmfit` (if applicable)

This software is still in a development. It contains some experimental data evaluation techniques which function are not fully optimized (Globat Fit, Chain Fit and Error Map)
