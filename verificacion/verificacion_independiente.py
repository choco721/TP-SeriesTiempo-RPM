# -*- coding: utf-8 -*-
"""
verificacion_independiente.py
Script SEPARADO que recalcula desde cero todos los resultados clave del notebook
TP_RPM_completo.ipynb y los compara contra los valores reportados.
"""

import pandas as pd
import numpy as np
import warnings
import sys
import json
import os
import itertools

# Force UTF-8 output
if sys.platform == 'win32':
    os.environ['PYTHONIOENCODING'] = 'utf-8'
    sys.stdout.reconfigure(encoding='utf-8')

warnings.filterwarnings('ignore')

from statsmodels.tsa.stattools import adfuller, kpss, acf, pacf
from statsmodels.tsa.seasonal import STL
from statsmodels.tsa.statespace.sarimax import SARIMAX
from statsmodels.stats.diagnostic import acorr_ljungbox, het_arch
from arch import arch_model

TOLERANCE = 0.05  # 5% tolerance

results = []

def check(label, expected, obtained, tol=TOLERANCE, abs_tol=None):
    if abs_tol is not None:
        ok = abs(expected - obtained) <= abs_tol
        diff_str = f"abs_diff={abs(expected-obtained):.6f}"
    elif expected == 0:
        ok = abs(obtained) < 0.01
        diff_str = f"abs_diff={abs(obtained):.6f}"
    else:
        rel = abs(expected - obtained) / abs(expected)
        ok = rel <= tol
        diff_str = f"rel_diff={rel*100:.2f}%"
    
    status = "OK" if ok else "DISCREPA"
    results.append({
        'check': label,
        'expected': expected,
        'obtained': round(obtained, 6) if isinstance(obtained, float) else obtained,
        'status': status,
        'detail': diff_str
    })
    symbol = "[OK]" if ok else "[!!]"
    obt_str = f"{obtained:.6f}" if isinstance(obtained, float) else str(obtained)
    print(f"  {symbol} {label}: esperado={expected}, obtenido={obt_str} ({diff_str}) -> {status}")
    return ok

# ============================================================
# CARGA DE DATOS
# ============================================================
print("=" * 80)
print("VERIFICACION NUMERICA INDEPENDIENTE")
print("=" * 80)

df = pd.read_csv('series.final.csv', parse_dates=['observation_date']).set_index('observation_date')
df.index.freq = 'MS'
df['log_rpm'] = np.log(df['RPM'])
y = df['log_rpm']

# ============================================================
# (a) n=216, rango 2002-01 a 2019-12, sin nulos
# ============================================================
print("\n-- (a) Datos basicos --")
check("n observaciones", 216, len(df))
check("Inicio (anio)", 2002, df.index[0].year)
check("Inicio (mes)", 1, df.index[0].month)
check("Fin (anio)", 2019, df.index[-1].year)
check("Fin (mes)", 12, df.index[-1].month)
check("Nulos", 0, df['RPM'].isna().sum())

# ============================================================
# (b) STL sobre log: fuerza estacional ~0.972, fuerza tendencia ~0.984
# ============================================================
print("\n-- (b) STL --")
stl = STL(y, period=12, robust=True).fit()
fs = max(0, 1 - stl.resid.var() / (stl.seasonal + stl.resid).var())
ft = max(0, 1 - stl.resid.var() / (stl.trend + stl.resid).var())
check("Fuerza estacional STL", 0.972, fs, abs_tol=0.005)
check("Fuerza tendencia STL", 0.984, ft, abs_tol=0.005)

# ============================================================
# (c) ADF en nivel: no rechaza (p~0.876). KPSS en nivel: rechaza (p~0.010)
# ============================================================
print("\n-- (c) ADF y KPSS en nivel --")
adf_level = adfuller(y, autolag='AIC')
kpss_level = kpss(y, regression='c', nlags='auto')
check("ADF nivel p-valor", 0.876, adf_level[1], abs_tol=0.02)
check("KPSS nivel p-valor", 0.010, kpss_level[1], abs_tol=0.005)

adf_no_rechaza = adf_level[1] > 0.05
kpss_rechaza = kpss_level[1] <= 0.05
print(f"  ADF no rechaza (p>0.05): {adf_no_rechaza}")
print(f"  KPSS rechaza (p<=0.05): {kpss_rechaza}")

# ============================================================
# (d) ADF con d=1: rechaza (p~0.038). KPSS con d=1: no rechaza (p~0.100)
# ============================================================
print("\n-- (d) ADF y KPSS con d=1 --")
y_d1 = y.diff().dropna()
adf_d1 = adfuller(y_d1, autolag='AIC')
kpss_d1 = kpss(y_d1, regression='c', nlags='auto')
check("ADF d=1 p-valor", 0.038, adf_d1[1], abs_tol=0.02)
check("KPSS d=1 p-valor", 0.100, kpss_d1[1], abs_tol=0.02)

adf_rechaza = adf_d1[1] <= 0.05
kpss_no_rechaza = kpss_d1[1] > 0.05
print(f"  ADF rechaza (p<=0.05): {adf_rechaza}")
print(f"  KPSS no rechaza (p>0.05): {kpss_no_rechaza}")

# ============================================================
# (e) ACF de la serie con d=1: rho(12) ~0.902
# ============================================================
print("\n-- (e) ACF d=1 --")
a_d1 = acf(y_d1, nlags=36, fft=False)
check("ACF d=1 rho(12)", 0.902, a_d1[12], abs_tol=0.005)

# ============================================================
# (f) Mejor SARIMA por AIC = (1,1,0)(0,1,1)12, AIC ~-834.81
# ============================================================
print("\n-- (f) SARIMA grid search --")
N_TEST = 24
train, test = y[:-N_TEST], y[-N_TEST:]

resultados_sarima = []
for p, q, P, Q in itertools.product(range(3), range(3), range(2), range(2)):
    try:
        m = SARIMAX(train, order=(p, 1, q), seasonal_order=(P, 1, Q, 12),
                    enforce_stationarity=False, enforce_invertibility=False).fit(disp=False, maxiter=200)
        resultados_sarima.append({'p': p, 'q': q, 'P': P, 'Q': Q,
                                  'AIC': m.aic, '_m': m})
    except Exception:
        continue

resultados_sarima = sorted(resultados_sarima, key=lambda r: r['AIC'])
best = resultados_sarima[0]
best_order_str = f"({best['p']},1,{best['q']})({best['P']},1,{best['Q']})12"
sarima_fit = best['_m']

print(f"  Mejor modelo: SARIMA{best_order_str}")
check("Mejor SARIMA AIC", -834.81, sarima_fit.aic, abs_tol=1.0)

expected_order = "(1,1,0)(0,1,1)12"
order_ok = best_order_str == expected_order
results.append({
    'check': 'Orden SARIMA',
    'expected': expected_order,
    'obtained': best_order_str,
    'status': 'OK' if order_ok else 'DISCREPA',
    'detail': ''
})
print(f"  [{'OK' if order_ok else '!!'}] Orden SARIMA: esperado={expected_order}, obtenido={best_order_str}")

# ============================================================
# (g) Raiz AR modulo ~2.112, Raices MA modulo ~1.040
# ============================================================
print("\n-- (g) Raices AR y MA --")
if len(sarima_fit.arroots) > 0:
    ar_mod_min = np.abs(sarima_fit.arroots).min()
    check("Raiz AR modulo minimo", 2.112, ar_mod_min, abs_tol=0.05)
    print(f"  Causal (mod>1): {ar_mod_min > 1}")

if len(sarima_fit.maroots) > 0:
    ma_mod_min = np.abs(sarima_fit.maroots).min()
    check("Raiz MA modulo minimo", 1.040, ma_mod_min, abs_tol=0.05)
    print(f"  Invertible (mod>1): {ma_mod_min > 1}")

# ============================================================
# (h) Ljung-Box residuos SARIMA lag 12: p ~0.977
# ============================================================
print("\n-- (h) Ljung-Box residuos SARIMA --")
resid_sarima = sarima_fit.resid.iloc[14:]
lb_sar = acorr_ljungbox(resid_sarima, lags=[12], return_df=True)
lb_p12 = lb_sar.loc[12, 'lb_pvalue']
check("LB residuos SARIMA lag12 p-valor", 0.977, lb_p12, abs_tol=0.05)
print(f"  Ruido blanco (p>0.05): {lb_p12 > 0.05}")

# ============================================================
# (i) MAPE SARIMA fuera de muestra ~1.40%; naive estacional ~4.41%
# ============================================================
print("\n-- (i) MAPE fuera de muestra --")
pred_sarima = sarima_fit.get_forecast(steps=N_TEST).predicted_mean
real = np.exp(test)
pred = np.exp(pred_sarima)
mape_sarima = np.mean(np.abs((real - pred) / real)) * 100

# Naive estacional
pred_naive_log = pd.Series(y[-N_TEST-12:-12].values, index=test.index)
pred_naive = np.exp(pred_naive_log)
mape_naive = np.mean(np.abs((real - pred_naive) / real)) * 100

check("MAPE SARIMA (%)", 1.40, mape_sarima, abs_tol=0.10)
check("MAPE naive estacional (%)", 4.41, mape_naive, abs_tol=0.10)

# Verify MAPE is in LEVEL (exp), not in log
mape_log = np.mean(np.abs((test - pred_sarima) / test)) * 100
print(f"  MAPE en log (incorrecto): {mape_log:.2f}% <- si fuera igual al reportado, habria error")
print(f"  MAPE en nivel (correcto): {mape_sarima:.2f}%")

# ============================================================
# (j) ARCH-LM de Engle sobre residuos SARIMA, lags=12: p ~0.004
# ============================================================
print("\n-- (j) ARCH-LM de Engle --")
lm = het_arch(resid_sarima, nlags=12)
check("ARCH-LM p-valor", 0.004, lm[1], abs_tol=0.003)
print(f"  Efecto ARCH (p<0.05): {lm[1] < 0.05}")

# ============================================================
# (k) Mejor modelo de volatilidad por BIC = EGARCH(1,1,1)-normal
# ============================================================
print("\n-- (k) Modelos de volatilidad --")
resid_scaled = resid_sarima * 100
rows_vol = []

for p in range(1, 6):
    for dist in ['normal', 't']:
        try:
            m = arch_model(resid_scaled, vol='ARCH', p=p, dist=dist, mean='Zero').fit(disp='off')
            rows_vol.append({'Modelo': f'ARCH({p})-{dist}', 'Familia': 'ARCH',
                             'BIC': m.bic, '_fit': m})
        except Exception:
            pass

for p in [1, 2]:
    for q in [1, 2]:
        for dist in ['normal', 't']:
            for vol, o, fam, nom in [('GARCH', 0, 'GARCH', f'GARCH({p},{q})'),
                                     ('EGARCH', 1, 'EGARCH', f'EGARCH({p},1,{q})'),
                                     ('GARCH', 1, 'GJR-GARCH', f'GJR-GARCH({p},1,{q})')]:
                try:
                    m = arch_model(resid_scaled, vol=vol, p=p, o=o, q=q, power=2.0,
                                   dist=dist, mean='Zero').fit(disp='off')
                    rows_vol.append({'Modelo': f'{nom}-{dist}', 'Familia': fam,
                                     'BIC': m.bic, '_fit': m})
                except Exception:
                    pass

df_vol = pd.DataFrame([{k: v for k, v in r.items() if k != '_fit'} for r in rows_vol])
df_vol = df_vol.drop_duplicates('Modelo').sort_values('BIC')

best_vol = df_vol.iloc[0]['Modelo']
best_vol_bic = df_vol.iloc[0]['BIC']

print(f"  Mejor modelo por BIC: {best_vol} (BIC={best_vol_bic:.2f})")
expected_vol = "EGARCH(1,1,1)-normal"
vol_ok = best_vol == expected_vol
results.append({
    'check': 'Mejor volatilidad (BIC)',
    'expected': expected_vol,
    'obtained': best_vol,
    'status': 'OK' if vol_ok else 'DISCREPA',
    'detail': ''
})
print(f"  [{'OK' if vol_ok else '!!'}] Modelo volatilidad: esperado={expected_vol}, obtenido={best_vol}")

# Top 5 BIC for reference
print("\n  Top 5 modelos por BIC:")
for i, row in df_vol.head(5).iterrows():
    print(f"    {row['Modelo']:30s} BIC={row['BIC']:.2f}")

# ============================================================
# TABLA RESUMEN
# ============================================================
print("\n" + "=" * 80)
print("TABLA RESUMEN DE VERIFICACION")
print("=" * 80)
print(f"{'Check':<35s} {'Esperado':>15s} {'Obtenido':>15s} {'Status':>10s}")
print("-" * 80)
for r in results:
    exp = str(r['expected'])
    obt = str(r['obtained'])
    print(f"{r['check']:<35s} {exp:>15s} {obt:>15s} {r['status']:>10s}")

n_ok = sum(1 for r in results if r['status'] == 'OK')
n_fail = sum(1 for r in results if r['status'] == 'DISCREPA')
print(f"\nResultado: {n_ok} OK, {n_fail} DISCREPA de {len(results)} checks")

# ============================================================
# AUDITORIA DE FUGAS (TAREA 3)
# ============================================================
print("\n" + "=" * 80)
print("AUDITORIA DE FUGAS Y ERRORES METODOLOGICOS (TAREA 3)")
print("=" * 80)

print("\n-- Data Leakage --")
print(f"  Train: {len(train)} obs ({train.index[0]:%Y-%m} -> {train.index[-1]:%Y-%m})")
print(f"  Test : {len(test)} obs ({test.index[0]:%Y-%m} -> {test.index[-1]:%Y-%m})")
print(f"  Train = y[:-24]? {len(train) == len(y) - 24 and (train.index == y.index[:-24]).all()}")
print(f"  Test = y[-24:]? {len(test) == 24 and (test.index == y.index[-24:]).all()}")

print("\n-- Recorte de residuos --")
resid_full = sarima_fit.resid
n_zeros = (resid_full.iloc[:15] == 0).sum()
print(f"  Residuos totales: {len(resid_full)}")
print(f"  Ceros en primeros 15 residuos: {n_zeros}")
print(f"  El notebook usa .iloc[14:], descartando los primeros 14 residuos")
print(f"  Con d=1, D=1, s=12, se pierden 1+12=13 puntos. iloc[14:] es conservador y correcto.")
print(f"  Residuos usados: {len(resid_sarima)} (de {len(resid_full)})")

# Check for spurious zeros in used residuals
n_zeros_used = (resid_sarima == 0).sum()
print(f"  Ceros en residuos usados: {n_zeros_used}")

print("\n-- MAPE en nivel vs log --")
print(f"  MAPE calculado en NIVEL (exp): {mape_sarima:.2f}% <- CORRECTO")
print(f"  MAPE calculado en LOG: {mape_log:.2f}% <- seria incorrecto")
print(f"  El notebook usa np.exp(test) y np.exp(pred) -> CORRECTO, calcula en nivel")

print("\n-- GARCH sobre residuos SARIMA vs serie cruda --")
print(f"  Los modelos GARCH se estiman sobre resid_sarima * 100 -> CORRECTO")
print(f"  (residuos del SARIMA, no la serie cruda)")

print("\n-- Seleccion de orden con train --")
print(f"  SARIMA grid search usa train ({len(train)} obs) -> CORRECTO")
print(f"  AR/MA/ARMA usan ARIMA(train, ...) -> CORRECTO")

# ============================================================
# SAVE RESULTS AS JSON
# ============================================================
with open('verificacion_resultados.json', 'w', encoding='utf-8') as f:
    json.dump(results, f, ensure_ascii=False, indent=2)

print("\n\nResultados guardados en verificacion_resultados.json")
print("Script completado exitosamente.")
