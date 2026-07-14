# Análisis y Predicción de Series de Tiempo — Tráfico aéreo de pasajeros en EE.UU.

Trabajo final de la materia **Análisis y Predicción en Series de Tiempo**
Licenciatura en Ciencia de Datos — Universidad Católica Argentina (Rosario)

---

## Descripción

Análisis completo de la serie **Revenue Passenger Miles (RPM)** del transporte aéreo
de pasajeros en Estados Unidos, integrando los cinco trabajos prácticos de la cursada
en un único notebook.

**Variable:** RPM = pasajeros pagos × millas voladas. Vuelos regulares de aerolíneas
estadounidenses, domésticos e internacionales. Serie mensual, sin ajuste estacional.

**Fuente:** U.S. Bureau of Transportation Statistics, vía FRED (Federal Reserve Bank
of St. Louis), ticker [`RPM`](https://fred.stlouisfed.org/series/RPM).

**Período:** enero 2002 – diciembre 2019 (216 observaciones).

---

## Selección de la ventana temporal

La serie está disponible desde 2000, pero contiene dos shocks exógenos de magnitud
extrema que invalidan los supuestos de los modelos. Se evaluaron empíricamente tres
ventanas:

| Ventana | n | Fuerza estacional | Efecto ARCH (p) | Diagnóstico |
|---|---|---|---|---|
| 2001–2019 (incluye 11-S) | 217 | 0.895 | 0.507 | Sin efecto ARCH → TP5 inviable |
| 2002–2026 (incluye COVID) | 291 | 0.071 | 0.981 | Sin estacionalidad ni ARCH |
| **2002–2019 (seleccionada)** | **216** | **0.972** | **0.0005** | **Viable** |

La caída del tráfico aéreo durante el COVID-19 fue del **97.1%**. Un valor atípico de
esa magnitud relega la componente estacional a la categoría de ruido y elimina la
heterocedasticidad condicional. El truncamiento es una consecuencia medida de la
violación de los supuestos, no una decisión arbitraria.

---

## Contenido

| Sección | Contenido | TP |
|---|---|---|
| 3 | Funciones de momento: γ(k), ρ(k), estacionariedad en media y varianza | TP1 |
| 4 | Análisis exploratorio, seasonal plot, identificación de eventos | TP1 |
| 5 | Modelos de descomposición (aditivo vs. multiplicativo), STL | TP1 |
| 6 | Filtrado (promedio móvil centrado) y suavizado (Holt-Winters) | TP1 |
| 7 | Estacionariedad: pruebas ADF y KPSS conjuntas | TP2 |
| 8 | ACF, PACF, prueba de ruido blanco, contraste de camino aleatorio | TP1–2 |
| 9 | Modelos AR(p), MA(q) y ARMA(p,q) | TP2 |
| 10 | ARIMA, comparación de métodos de estimación y criterios de información | TP3 |
| 11 | SARIMA, modelos estacionales puros (SAR, SMA, SARMA), causalidad e invertibilidad | TP4 |
| 12 | REGARMA con dummies y regresión estacional armónica | TP4 |
| 13 | Comparación de modelos de media | TP3–4 |
| 14 | Modelos de volatilidad: ARCH, GARCH, EGARCH, TGARCH (GJR) | TP5 |
| 15 | Pronóstico final | TP3–5 |

---

## Resultados principales

### Modelo de media: SARIMA(1,1,0)(0,1,1)₁₂

| Criterio | Valor |
|---|---|
| AIC | −834.81 |
| Causalidad | ✓ (raíz AR, módulo 2.112 > 1) |
| Invertibilidad | ✓ (raíces MA, módulo 1.040 > 1) |
| Residuos ruido blanco | ✓ (Ljung-Box lag 12, p = 0.977) |
| **MAPE fuera de muestra (24 meses)** | **1.40%** |
| Benchmark naive estacional | 4.41% |

El modelo reduce el error de predicción en un **68%** respecto de la regla ingenua.

**Hallazgo central:** los cuatro modelos sin componente estacional (AR, MA, ARMA,
ARIMA) fallan el diagnóstico de residuos y **ninguno supera al benchmark naive**.
La estacionalidad es la estructura dominante de la serie.

### Modelo de volatilidad: EGARCH(1,1,1)

Efecto ARCH confirmado sobre los residuos del SARIMA (ARCH-LM de Engle, p = 0.004).

- **β₁ = 0.986** → persistencia alta: la volatilidad tiene memoria larga.
- **γ₁ = −0.110** → **efecto apalancamiento**: los shocks negativos incrementan la
  volatilidad futura más que los positivos de igual magnitud.
- Efecto ARCH completamente capturado (Ljung-Box sobre residuos estandarizados², p = 0.229).

La volatilidad condicional estimada **identifica de forma autónoma** los tres episodios
señalados por el análisis de dominio, sin haber recibido información alguna sobre ellos:

| Episodio | Período | z máx. (residuos STL) |
|---|---|---|
| Guerra de Irak + SARS | mar–jun 2003 | −4.80 |
| Shock petrolero (WTI USD 147) | 2008 | +4.51 |
| Crisis financiera global | sep 2008 – jun 2009 | −2.48 |

---

## Reproducción

### Requisitos

```bash
pip install pandas numpy matplotlib scipy statsmodels arch jupyter
```

### Ejecución

```bash
jupyter notebook TP_RPM_completo.ipynb
```

Ejecutar todas las celdas en orden. El notebook carga `rpm.csv` desde el mismo
directorio.

---

## Estructura

```
.
├── TP_RPM_completo.ipynb    # Notebook integrado (TP1–TP5)
├── rpm.csv                  # Serie RPM 2002-01 a 2019-12 (216 obs)
└── README.md
```

---

## Limitaciones

El modelo es **univariado**: no incorpora precio del combustible, capacidad instalada
ni condiciones macroeconómicas. Por construcción, **no puede anticipar shocks exógenos**
del tipo de los identificados. El pronóstico es válido bajo el supuesto de continuidad
del régimen observado en 2002–2019 — supuesto violado de forma extrema en 2020.

---

## Bibliografía

- Quintero-Rincón, A. *Notas de cátedra: Análisis y Predicción en Series de Tiempo*. UCA.
- Box, G. E. P., Jenkins, G. M., Reinsel, G. C., & Ljung, G. M. (2015). *Time Series Analysis: Forecasting and Control* (5th ed.). Wiley.
- Engle, R. F. (1982). Autoregressive Conditional Heteroscedasticity with Estimates of the Variance of United Kingdom Inflation. *Econometrica*, 50(4), 987–1007.
- Bollerslev, T. (1986). Generalized Autoregressive Conditional Heteroskedasticity. *Journal of Econometrics*, 31(3), 307–327.
- Nelson, D. B. (1991). Conditional Heteroskedasticity in Asset Returns: A New Approach. *Econometrica*, 59(2), 347–370.
- Glosten, L. R., Jagannathan, R., & Runkle, D. E. (1993). On the Relation between the Expected Value and the Volatility of the Nominal Excess Return on Stocks. *Journal of Finance*, 48(5), 1779–1801.
- Hyndman, R. J., & Athanasopoulos, G. (2021). *Forecasting: Principles and Practice* (3rd ed.). OTexts.
- U.S. Bureau of Transportation Statistics. *Revenue Passenger Miles* [RPM]. FRED. https://fred.stlouisfed.org/series/RPM
