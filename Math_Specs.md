# Math Specifications — Quant Dashboard v9

> **Amaç**: Sistemin tüm quantitatif çekirdek modüllerinin matematiksel
> formülasyonlarını LaTeX notasyonuyla, akademik referanslarıyla birlikte
> tek bir dosyada toplamak. "Algoritma neyi neden yapıyor?" sorusuna
> cevap. Her formülün altında `module.function_name` referansı vardır.

---

## 0. Notasyon

| Sembol | Anlam |
|---|---|
| $P_t$ | t anındaki fiyat |
| $r_t = \ln(P_t / P_{t-1})$ | logaritmik getiri |
| $\mu$ | yıllık beklenen getiri (drift) |
| $\sigma$ | yıllık volatilite (std) |
| $\sigma_d$ | günlük volatilite, $\sigma_d = \sigma / \sqrt{252}$ |
| $r_f$ | risk-free oran (varsayılan %2) |
| $T$ | yatırım ufku (yıl) |
| $\Phi(\cdot)$ | standart normal CDF |

---

## 1. Master Score (Hibrit Güven Endeksi)

**Akademik Referans**: Hibrit faktör modeli (Fama-French extension) + Lopez de Prado meta-labeling.

### 1.1 Toplu Formülasyon

$$
\boxed{
\text{Master\_Score} \;=\; \mathrm{clip}_{[0,100]}\Big( B \cdot \kappa \;+\; M \Big)
}
$$

| Terim | Açıklama | Aralık |
|---|---|---|
| $B$ | Taban skor (4 ana faktörün ağırlıklı toplamı) | $[0, 100]$ |
| $\kappa$ | Research-Agent dinamik katsayısı (Lopez de Prado MDA) | $[0.5, 1.5]$ |
| $M$ | Modifier toplamı (sektör, makro, stratejik, jeopolitik) | $[-60, +60]$ |

### 1.2 Taban Skor $B$

Dört temel boyutun toplamı:

$$
B \;=\; \underbrace{T}_{\text{teknik 30p}} \;+\; \underbrace{V}_{\text{vizyon 30p}} \;+\; \underbrace{F}_{\text{temel 20p}} \;+\; \underbrace{S}_{\text{sentiment 20p}}
$$

**Teknik bileşeni $T$** ($0\text{-}30$ puan):

$$
T = T_{\text{RSI}} + T_{\text{MACD}} + T_{\text{SMA}} + T_{\text{ML}}
$$

| Alt-bileşen | Kural | Puan |
|---|---|---|
| $T_{\text{RSI}}$ | $35 \le \text{RSI} \le 65$ | 9 |
| $T_{\text{RSI}}$ | $30 \le \text{RSI} < 35$ veya $65 < \text{RSI} \le 70$ | 6 |
| $T_{\text{RSI}}$ | $\text{RSI} < 30$ veya $\text{RSI} > 75$ | 2 |
| $T_{\text{MACD}}$ | MACD signal bullish | 9 |
| $T_{\text{SMA}}$ | $P > \text{SMA}_{20}$ +3, $P > \text{SMA}_{50}$ +3 | 0-6 |
| $T_{\text{ML}}$ | $\max(0, \min(6,\; \frac{p_{\uparrow} - 0.35}{0.30} \cdot 6))$ | 0-6 |

**Vizyon bileşeni $V$** ($0\text{-}30$ puan):

$$
V \;=\; \mathrm{scale}_{[-15, +20] \to [0, 30]}\big( v_{\text{bonus}} \big)
$$

Burada $v_{\text{bonus}}$ moonshot detector + visionary milestone hit puanı.

**Modifier toplamı $M$**:

$$
\begin{aligned}
M \;=\; & \underbrace{w_s}_{\pm 5,\;\text{sektör zinciri}} + \underbrace{w_c}_{\pm 5,\;\text{capex}} + \underbrace{w_{cr}}_{\pm 10,\;\text{kritik haber}} \\[4pt]
& + \underbrace{w_f}_{-5..0,\;\text{korku}} + \underbrace{w_m}_{-5..0,\;\text{moat}} + \underbrace{w_p}_{0..+5,\;\text{patent}} \\[4pt]
& + \underbrace{w_g}_{-15..+10,\;\text{jeopolitik}} + \underbrace{w_{cy}}_{\pm 3,\;\text{cycle phase}} \\[4pt]
& + \underbrace{w_{ma}}_{\pm 10,\;\text{makro tailwind}} + \underbrace{\Omega}_{\pm 30,\;\text{stratejik overlay}} \\[4pt]
& + \underbrace{w_{rw}}_{-20..0,\;\text{cash runway}} + \underbrace{w_{ms}}_{-5..+20,\;\text{moonshot J-curve}}
\end{aligned}
$$

**Reating** ($\text{Master\_Score}$'a göre):

$$
\text{Rating} = \begin{cases} \text{KRİTİK ALIM} & \text{eğer } \ge 85 \\
\text{GÜÇLÜ AL} & 70 \le \cdot < 85 \\
\text{AL} & 55 \le \cdot < 70 \\
\text{BEKLE} & 40 \le \cdot < 55 \\
\text{DİKKAT} & 25 \le \cdot < 40 \\
\text{SAT} & \cdot < 25 \end{cases}
$$

📂 **Kaynak**: `master_score.compute_master_score()`

---

## 2. Triple Barrier Method (Lopez de Prado)

**Akademik Referans**: *Advances in Financial Machine Learning* (Marcos López de Prado, 2018), Bölüm 3.

Klasik stop-loss tek yönlüdür. Triple Barrier üç boyutlu etiketleme yapar:

$$
\text{Barrier}_{u,l}(t_0) \;=\; P_{t_0} \cdot \exp\Big(\pm \phi \cdot \sigma_d \cdot \sqrt{t}\Big)
$$

| Bariyer | Yön | Tetik |
|---|---|---|
| Üst (TP) | yukarı kırılım | $P_t \ge P_{t_0} \cdot e^{+\phi \sigma_d \sqrt{t}}$ → $y = +1$ |
| Alt (SL) | aşağı kırılım | $P_t \le P_{t_0} \cdot e^{-\phi \sigma_d \sqrt{t}}$ → $y = -1$ |
| Zaman | $t \ge T_{\max}$ | yatay → $y = 0$ |

Volatilite-uyarlamalı: NVTS yüksek $\sigma$ → bariyerler geniş, ASML düşük $\sigma$ → dar.

### 2.1 Uygulama Varsayımları (backtest)

- **Giriş yürütmesi**: `AL` sinyali bar kapanışında üretildiyse, işlem bir sonraki barın **Open** fiyatında açılır.
- **Sinyal/zaman çıkışı**: `SAT` ve `TIME` çıkışları da bir sonraki barın **Open** fiyatında yürütülir.
- **Bariyer çıkışı**: `TP` ve `SL`, aynı bar içinde `High/Low` dokunuşuyla anında yürütülir.
- **Çakışma kuralı**: Aynı bar içinde hem `SL` hem `TP` dokunursa, muhafazakâr olarak **SL önce kazanır**.

### 2.2 İşlem maliyeti ve slippage

Uzun pozisyon için yürütme fiyatları maliyetle bozulur:

$$
P_{\text{entry,eff}} = P_{\text{entry,raw}} \cdot \left(1 + \frac{c + s}{10{,}000}\right)
$$

$$
P_{\text{exit,eff}} = P_{\text{exit,raw}} \cdot \left(1 - \frac{c + s}{10{,}000}\right)
$$

Burada $c$ = `commission_bps`, $s$ = `slippage_bps`.
Net trade getirisi:

$$
r_{\text{trade}} = \frac{P_{\text{exit,eff}}}{P_{\text{entry,eff}}} - 1
$$

📂 **Kaynak**: `backtest.backtest_strategy()`

---

## 3. Sharpe & Sortino & Calmar Rasyoları

### 3.1 Sharpe Ratio (Sharpe 1966)

$$
\text{Sharpe} \;=\; \frac{\bar{r} - r_f / N}{\sigma_r} \cdot \sqrt{N}
$$

Burada $N$ = yıldaki gözlem sayısı (252 günlük, 12 aylık).

### 3.2 Sortino Ratio (Sortino & Price 1994)

Sortino, sadece **aşağı yönlü** sapmayı cezalandırır:

$$
\text{Sortino} \;=\; \frac{\bar{r} - r_f / N}{\sigma_{\downarrow}} \cdot \sqrt{N}, \qquad \sigma_{\downarrow} = \sqrt{\frac{1}{|D|} \sum_{r_i < 0} r_i^2}
$$

### 3.3 Calmar Ratio (Young 1991)

$$
\text{Calmar} \;=\; \frac{|\text{CAGR}|}{|\text{MaxDrawdown}|}, \qquad \text{MDD} = \min_t \frac{P_t - \max_{s \le t} P_s}{\max_{s \le t} P_s}
$$

### 3.4 VaR & CVaR (Value at Risk)

Tarihsel kantil yöntemi ($\alpha = 0.05$):

$$
\text{VaR}_\alpha = -Q_\alpha(r), \qquad \text{CVaR}_\alpha = -\mathbb{E}\big[r \mid r \le Q_\alpha(r)\big]
$$

📂 **Kaynak**: `backtest._sharpe_ratio()`, `risk_distribution.classify_outcome()`

---

## 4. Geometric Brownian Motion (Monte Carlo)

**Akademik Referans**: Black-Scholes (1973), Hull (2018).

Hisse fiyatı stokastik diferansiyel denklemi:

$$
dS_t \;=\; \mu S_t\, dt \;+\; \sigma S_t\, dW_t
$$

Analitik (Itô lemması) çözüm:

$$
S_t \;=\; S_0 \cdot \exp\!\left( \big( \mu - \tfrac{1}{2}\sigma^2 \big)\, t \;+\; \sigma\, W_t \right), \qquad W_t \sim \mathcal{N}(0, t)
$$

10K Monte Carlo path için ayrık adım:

$$
S_{t+\Delta t}^{(i)} \;=\; S_t^{(i)} \cdot \exp\!\left( (\mu - \tfrac{1}{2}\sigma^2)\, \Delta t + \sigma\, \sqrt{\Delta t}\, Z^{(i)} \right), \quad Z^{(i)} \sim \mathcal{N}(0, 1)
$$

**Fat-tail clipping** (aşırı uç olayları budama):

$$
S_T^{(i)} \;\leftarrow\; \min\!\Big( S_T^{(i)}, \;\; S_0 \cdot m_{\text{cap}} \Big)
$$
$$
S_T^{(i)} \;\leftarrow\; \max\!\Big( S_T^{(i)}, \;\; 0.01 \Big)
$$

Burada $m_{\text{cap}}$ = `fat_tail_cap_multiplier` (varsayılan 20).

**Çıktı istatistikleri** ($N = 10{,}000$ path):

| Metrik | Formül |
|---|---|
| Median | $\tilde{S}_T = Q_{0.50}(\{S_T^{(i)}\})$ |
| Median CAGR | $\left(\tilde{S}_T / S_0\right)^{1/T} - 1$ |
| 95% güven aralığı | $[Q_{0.025},\; Q_{0.975}]$ |
| VaR 5% | $-(S_0 - Q_{0.05}) / S_0$ |
| CVaR 5% | $-\frac{1}{|\mathcal{A}|}\sum_{i \in \mathcal{A}} \frac{S_T^{(i)} - S_0}{S_0}$, $\mathcal{A} = \{i : S_T^{(i)} \le Q_{0.05}\}$ |
| $P(\text{bust})$ | $\mathbb{P}(S_T < 0.2 \cdot S_0)$ |
| $P(10\text{x})$ | $\mathbb{P}(S_T \ge 10 \cdot S_0)$ |
| Cap-hit oranı | $\mathbb{P}(S_T \ge 0.995 \cdot S_0 \cdot m_{\text{cap}})$ |

📂 **Kaynak**: `monte_carlo.simulate_paths()`, `monte_carlo.summarize()`

---

## 5. Logistic Growth & Market Cap Saturation

**Akademik Referans**: Verhulst (1838), Prophet (Taylor & Letham 2018).

Prophet logistic mode:

$$
\hat{y}(t) \;=\; \frac{C(t)}{1 + \exp\big( -k(t)\big( t - m(t) \big) \big)}
$$

Burada $C(t)$ = capacity (üst sınır), $k(t)$ = büyüme hızı, $m(t)$ = mid-point.

### 5.1 Market Cap Saturation Cap

$$
C_{\text{price}} \;=\; \frac{\min\big( C_{\text{Apple}},\; C_{\text{NVDA}},\; C_{\text{leader}},\; C_{\text{TAM}},\; C_{\text{ticker}} \big)}{N_{\text{shares}}}
$$

| Sınır | Anlam |
|---|---|
| $C_{\text{Apple}}$ | Tarihsel **mutlak** market cap tavanı (~$5T) |
| $C_{\text{NVDA}}$ | Yarı-iletken lider tavanı (~$3.5T) |
| $C_{\text{leader}}$ | Sektör lideri P/S × TAM (ör. ASML $1T) |
| $C_{\text{TAM}}$ | $\text{TAM}_{10y} \times (\text{P/S})_{\text{sector}} \times s_{\text{market}} \times 0.5$ |
| $C_{\text{ticker}}$ | NVTS $100, ATOM $40 gibi hard-cap |

**Global 20x kuralı** (her hisse için):

$$
C_{\text{price}}^{(\text{final})} \;=\; \min\big( C_{\text{price}},\;\; P_0 \cdot 20 \big)
$$

Bu, AXTI senaryosundaki $23K saçma rakamlarını engelleyen kelepçedir.

📂 **Kaynak**: `forecasting._apply_market_cap_saturation()`

---

## 6. Purged K-Fold Cross-Validation

**Akademik Referans**: Lopez de Prado (2018), Bölüm 7.

Standart K-Fold finans verisinde **sızıntı** üretir, çünkü trade label'ı $y_t$ aslında $[t, t+h]$ aralığını kullanır. Bu yüzden:

$$
\mathcal{T}_{\text{train}}^{(k)} \;=\; \mathcal{T} \setminus \Big( \mathcal{T}_{\text{test}}^{(k)} \cup \mathcal{E}^{(k)} \Big)
$$

Burada **embargo** bölgesi:

$$
\mathcal{E}^{(k)} \;=\; \big\{ t : \min(\mathcal{T}_{\text{test}}^{(k)}) - h_e \le t \le \max(\mathcal{T}_{\text{test}}^{(k)}) + h_e \big\}
$$

Tipik $h_e = $ 5-20 bar (etiket horizonu kadar). Pratikte bu repo için
`horizon_days`, backtest'teki `holding_days` ile hizalı tutulmalıdır; aksi
halde ML doğrulaması ile tarihsel sinyal testi farklı gelecek ufukları varsayar.

**Overfitting tanısı**:

$$
\text{Overfit Gap} \;=\; \text{Acc}_{\text{train}} - \text{Acc}_{\text{purged-cv}}
$$

| Gap | Verdict |
|---|---|
| $\le 0.05$ | CLEAN |
| $0.05 < \text{gap} \le 0.15$ | WARNING |
| $> 0.15$ | SEVERE OVERFIT |

📂 **Kaynak**: `purged_cv.purged_kfold_cv_score()`

---

## 7. Feature Importance — MDI & MDA

### 7.1 MDI — Mean Decrease in Impurity (Breiman 2001)

Random Forest / XGBoost'un built-in metriği. Her ağaç $b$ için, özellik $j$'nin tüm split node'larındaki Gini impurity azalmasının ağırlıklı ortalaması:

$$
\text{MDI}(j) \;=\; \frac{1}{B} \sum_{b=1}^{B} \sum_{\nu \in \mathcal{N}_j^{(b)}} \frac{n_\nu}{N} \cdot \Delta\, I(\nu)
$$

Hızlı ama **biased** (high-cardinality özelliklere şişer).

### 7.2 MDA — Mean Decrease in Accuracy (Lopez de Prado 2018, Ch. 8)

"Gold standard". Her özellik $j$ için $n$ kez permutasyon:

$$
\text{MDA}(j) \;=\; \mathrm{Acc}(X, y) \;-\; \frac{1}{n}\sum_{r=1}^{n} \mathrm{Acc}\big( X^{(j \to \pi)}, y \big)
$$

Burada $X^{(j \to \pi)}$ = sadece $j$ kolonu rastgele permute edilmiş veri.

$\text{MDA}(j) \le 0$ → özellik gereksiz/zararlı.

### 7.3 Sentiment vs SMA "Matematiksel İspatı"

Top-5 listesinde MDA(news_sentiment) > MDA(sma_cross) olup olmadığına bakarız. Eğer:

$$
\frac{\text{MDA}(\text{sent})}{\text{MDA}(\text{sma})} > 1.2 \;\;\Rightarrow\;\; \text{Sentiment hakimiyeti}
$$

📂 **Kaynak**: `feature_importance.feature_importance_mda()`, `feature_importance.feature_importance_mdi()`

---

## 8. Black-Litterman Portfolio Optimization

**Akademik Referans**: Black & Litterman (1992), Goldman Sachs.

**Equilibrium prior** (CAPM tersine mühendislik):

$$
\boldsymbol{\Pi} \;=\; \lambda \cdot \Sigma \cdot w_{\text{mkt}}
$$

Burada $\lambda$ risk aversion (~2.5), $\Sigma$ kovaryans matrisi, $w_{\text{mkt}}$ piyasa cap ağırlıkları.

**Yatırımcı görüşleri** $Q$, $P$, $\Omega$ ile birleştirme (Bayesian update):

$$
\hat{\boldsymbol{\mu}}_{\text{BL}} \;=\; \big[ (\tau \Sigma)^{-1} + P^{T} \Omega^{-1} P \big]^{-1} \big[ (\tau \Sigma)^{-1} \boldsymbol{\Pi} + P^{T} \Omega^{-1} Q \big]
$$

Optimal ağırlıklar:

$$
w^* \;=\; \frac{1}{\lambda} \Sigma^{-1} \hat{\boldsymbol{\mu}}_{\text{BL}}
$$

📂 **Kaynak**: `black_litterman.black_litterman_weights()`

---

## 9. Confidence Interval (Wilson Score)

ML olasılık tahmini için bootstrap-free güven aralığı:

$$
\text{CI}_{95}(p) \;=\; \frac{p + \frac{z^2}{2n} \pm z \sqrt{\frac{p(1-p)}{n} + \frac{z^2}{4n^2}}}{1 + \frac{z^2}{n}}, \qquad z = 1.96
$$

📂 **Kaynak**: `master_score._confidence_interval()`

---

## 10. Paper Portfolio — Gerçekçi Senaryo Modeli

**Akademik Referans**: Bessembinder (2018) "Do Stocks Outperform Treasury Bills?" — Hisse senedi getirilerinin uzun-kuyruklu dağılımı; çoğu hisse uzun vadede T-bill'i bile yenmez.

### 10.1 Hisse Bazlı Beklenen Getiri

$$
\mathbb{E}[V_T^{(i)}] \;=\; p_{\text{succ}} \cdot G_i \cdot (1 + g_i)^T \;+\; (1 - p_{\text{succ}}) \cdot I_i \cdot f
$$

Burada:

| Sembol | Anlam |
|---|---|
| $G_i$ | gross future value (CAGR uygulanmış) |
| $g_i$ | hisseye özel yıllık getiri (sektör CAGR × iskonto faktörü) |
| $p_{\text{succ}}$ | başarı olasılığı (spekulatif: 0.30-0.80) |
| $I_i$ | initial investment |
| $f$ | başarısızlık değer oranı (0.10-0.40) |

### 10.2 İskonto Faktörleri (Senaryoya Göre)

| Senaryo | $g_i$ | $p_{\text{succ}}$ (spek) | $f$ |
|---|---|---|---|
| Pessimistic | $-25\%$ | 0.30 | 0.10 |
| Base | $\min(0.35 \cdot g_{\text{sector}}, 12\%)$ | 0.55 | 0.25 |
| Optimistic | $\min(0.55 \cdot g_{\text{sector}}, 22\%)$ | 0.80 | 0.40 |

### 10.3 Hard-Cap (Horizon-Proportional)

$$
S_T^{(i)} \;=\; \min\!\Big( S_T^{(i)}, \;\; S_0^{(i)} \cdot \big( 1 + 19 \cdot \tfrac{T}{10} \big) \Big)
$$

📂 **Kaynak**: `paper_portfolio.portfolio_scenarios()`

---

## 11. Critical Export Filter (Mayıs 2026 Kalibrasyonu)

Ga/Ge/InP/EUV/SiC malzemelerinin ihracat lisansı haberleri için:

$$
w_g^{\text{(geo)}} \;=\; \max\!\Big( -15,\;\; \min\!\big( +10,\; -\!\sum_{k} \mathbb{1}[\text{pattern}_k] - 5 \cdot \mathbb{1}[\text{critical export hit}] \big) \Big)
$$

Hiçbir başka modifier'da yumuşatılmaz; doğrudan Master Score'a yansır.

📂 **Kaynak**: `geopolitics.assess_ticker()`, `geopolitics._detect_critical_export()`

---

## 12. Hesaplama İzlemi (Calculation Trace)

Her hisse için UI'da gösterilen örnek:

```
NVTS Master Score = 67.4

  B (taban)        = T(22) + V(18) + F(12) + S(11)     = 63.0
  κ (research)     = 1.08
  B · κ                                                = 68.04

  M (modifiers):
    sector           +3
    capex            +2
    critical news    +5
    fear             -3
    moat             0
    patent           +2
    geo              -1
    cycle            +1
    macro            +10  (EXPANSION)
    strategic        +18  (NVTS Tier-1 OEM + GaN)
    runway           -5
    moonshot         +14  (J-Curve)
  Σ M                                                  = +46

  Final = clip[0,100]( 68.04 + 46 )                    = 100.00
  → Rating: KRİTİK ALIM
```

📂 **Kaynak**: `app.render_calculation_trace()`

---

## Referans Bibliyografya

1. Black, F., & Litterman, R. (1992). *Global portfolio optimization*. **Financial Analysts Journal**.
2. Bessembinder, H. (2018). *Do stocks outperform Treasury bills?* **Journal of Financial Economics**.
3. Breiman, L. (2001). *Random forests*. **Machine Learning**.
4. Fisher, P. (1958). *Common Stocks and Uncommon Profits*.
5. Hull, J. (2018). *Options, Futures, and Other Derivatives*, 10th ed.
6. López de Prado, M. (2018). *Advances in Financial Machine Learning*. Wiley.
7. Murphy, J. (1999). *Technical Analysis of the Financial Markets*. NYIF.
8. Ng, A. (2018). *Machine Learning Yearning*.
9. Sharpe, W. F. (1966). *Mutual fund performance*. **Journal of Business**.
10. Sortino, F. A., & Price, L. N. (1994). *Performance measurement in a downside risk framework*.
11. Taylor, S. J., & Letham, B. (2018). *Forecasting at scale*. **The American Statistician** (Prophet).
12. Verhulst, P. F. (1838). Logistic growth model.
13. Young, T. (1991). *Calmar ratio: A smoother tool*.

---

*Son güncelleme: Mayıs 2026 — Master Score v9, Critical Export Filter aktif.*
